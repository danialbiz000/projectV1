"""
Standalone options analyzer.
Usage:
    python analyze_options.py SPY
    python analyze_options.py AAPL --dte-min 10 --dte-max 40
"""

import argparse
import sys
import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from nexus_quant.data.alpaca_client import AlpacaClient
from nexus_quant.math.black_scholes import bs_price, greeks, implied_vol


def analyze(ticker: str, dte_min: int = 10, dte_max: int = 45):
    client = AlpacaClient()

    # 1. Underlying price
    bars = client.get_bars(ticker, "1Day", limit=30)
    if bars.empty:
        print(f"ERROR: no price data for {ticker}")
        return

    spot      = float(bars["close"].iloc[-1])
    close_5d  = bars["close"].tail(5)
    trend     = "bullish" if close_5d.iloc[-1] > close_5d.iloc[0] else "bearish"
    vol_20d   = float(bars["close"].pct_change().std() * (252 ** 0.5))

    print(f"\n{'='*60}")
    print(f"  OPTIONS ANALYSIS — {ticker}")
    print(f"{'='*60}")
    print(f"  Spot price  : ${spot:.2f}")
    print(f"  Trend (5d)  : {trend}")
    print(f"  HV 20d      : {vol_20d:.1%}")

    # 2. Options chain
    exp_gte = (date.today() + timedelta(days=dte_min)).isoformat()
    exp_lte = (date.today() + timedelta(days=dte_max)).isoformat()

    chain = client.get_options_chain(
        ticker,
        expiration_gte=exp_gte,
        expiration_lte=exp_lte,
        limit=500,
    )

    if not chain:
        print(f"\n  No options data returned for {ticker}.")
        print("  (Check that your Alpaca account has options enabled)")
        return

    # 3. Enrich with computed Greeks if Alpaca doesn't provide them
    enriched = []
    r = 0.053  # risk-free rate

    for c in chain:
        snap  = c["snapshot"]
        quote = snap["latestQuote"]
        bid   = float(quote.get("bp", 0) or 0)
        ask   = float(quote.get("ap", 0) or 0)
        if bid <= 0 or ask <= 0:
            continue

        mid        = (bid + ask) / 2
        spread_pct = (ask - bid) / mid
        exp_date   = date.fromisoformat(c["expiration_date"])
        dte        = (exp_date - date.today()).days
        T          = dte / 365.0
        opt_type   = c["type"]  # "call" or "put"
        strike     = c["strike_price"]

        if T <= 0:
            continue

        # IV — use Alpaca's if available, else compute from market price
        iv = snap.get("impliedVolatility")
        if not iv or iv <= 0:
            try:
                iv = implied_vol(mid, spot, strike, T, r, opt_type)
            except Exception:
                iv = None

        if not iv or iv <= 0:
            continue

        # Greeks — use Alpaca's if available, else compute via BS
        g_raw = snap.get("greeks") or {}
        if g_raw.get("delta") is not None:
            delta  = float(g_raw["delta"])
            gamma  = float(g_raw.get("gamma", 0))
            theta  = float(g_raw.get("theta", 0))
            vega   = float(g_raw.get("vega", 0))
        else:
            g = greeks(spot, strike, T, r, iv, opt_type)
            delta = g["delta"]
            gamma = g["gamma"]
            theta = g["theta"] / 365
            vega  = g["vega"] / 100

        # IV/HV ratio
        iv_hv_ratio = iv / vol_20d if vol_20d > 0 else None

        enriched.append({
            "symbol":      c["symbol"],
            "type":        opt_type,
            "strike":      strike,
            "expiration":  c["expiration_date"],
            "dte":         dte,
            "bid":         bid,
            "ask":         ask,
            "mid":         mid,
            "spread_pct":  spread_pct,
            "iv":          iv,
            "iv_hv_ratio": iv_hv_ratio,
            "delta":       delta,
            "gamma":       gamma,
            "theta":       theta,
            "vega":        vega,
            "oi":          quote.get("as", 0) or 0,
        })

    if not enriched:
        print("  No liquid contracts found after filtering.")
        return

    # 4. IV summary
    ivs = [c["iv"] for c in enriched]
    iv_avg = sum(ivs) / len(ivs)
    iv_min = min(ivs)
    iv_max = max(ivs)

    print(f"\n  IV range    : {iv_min:.1%} – {iv_max:.1%}  (avg {iv_avg:.1%})")
    print(f"  IV/HV ratio : {iv_avg/vol_20d:.2f}x  {'← sell premium' if iv_avg/vol_20d > 1.2 else '← buy premium'}")
    print(f"  Contracts   : {len(enriched)} liquid (bid>0, ask>0)")

    # 5. Best candidates by strategy
    print(f"\n{'─'*60}")
    print("  TOP CANDIDATES")
    print(f"{'─'*60}")

    # Short puts ~0.30 delta (income / cash-secured put)
    short_puts = [c for c in enriched if c["type"] == "put" and 0.15 <= abs(c["delta"]) <= 0.40]
    short_puts.sort(key=lambda x: abs(abs(x["delta"]) - 0.30))

    # Short calls ~0.30 delta
    short_calls = [c for c in enriched if c["type"] == "call" and 0.15 <= abs(c["delta"]) <= 0.40]
    short_calls.sort(key=lambda x: abs(abs(x["delta"]) - 0.30))

    def fmt(c):
        return (
            f"  {c['symbol']:28} | {c['type']:4} | K={c['strike']:7.1f} | "
            f"exp={c['expiration']} DTE={c['dte']:2d} | "
            f"mid=${c['mid']:.2f} spread={c['spread_pct']:.1%} | "
            f"IV={c['iv']:.1%} | delta={c['delta']:+.2f} theta={c['theta']:+.4f}"
        )

    if short_puts:
        print("\n  [SHORT PUTS ~Δ0.30 — income / cash-secured put]")
        for c in short_puts[:3]:
            print(fmt(c))

    if short_calls:
        print("\n  [SHORT CALLS ~Δ0.30 — covered call / bear spread]")
        for c in short_calls[:3]:
            print(fmt(c))

    # Iron condor suggestion: best short put + best short call same expiry
    if short_puts and short_calls:
        best_put  = short_puts[0]
        # Match expiry
        matching_calls = [c for c in short_calls if c["expiration"] == best_put["expiration"]]
        if matching_calls:
            best_call = matching_calls[0]
            net_credit = best_put["mid"] + best_call["mid"]
            print(f"\n  [IRON CONDOR CANDIDATE — same expiry]")
            print(f"  Short put  : K={best_put['strike']:.1f}  mid=${best_put['mid']:.2f}")
            print(f"  Short call : K={best_call['strike']:.1f}  mid=${best_call['mid']:.2f}")
            print(f"  Net credit : ${net_credit:.2f} per share  (${net_credit*100:.0f} per contract)")
            print(f"  Expiration : {best_put['expiration']}  DTE={best_put['dte']}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Options analyzer")
    parser.add_argument("ticker", help="Underlying symbol (e.g. SPY)")
    parser.add_argument("--dte-min", type=int, default=10)
    parser.add_argument("--dte-max", type=int, default=45)
    args = parser.parse_args()
    analyze(args.ticker.upper(), args.dte_min, args.dte_max)


if __name__ == "__main__":
    main()
