"""
Options Engine: selects option contracts, prices them with BS, computes Greeks.

Strategy: sell premium in low/normal vol, buy protection in crisis.
Uses Alpaca paper options API + math/black_scholes.py.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import numpy as np
import pandas as pd

from ..math.black_scholes import bs_price, greeks, implied_vol, iv_surface_point
from ..data.alpaca_client import AlpacaClient
from .regime_engine import RegimeState
from .volatility_engine import VolatilityEstimate


@dataclass
class OptionCandidate:
    symbol: str             # Alpaca option symbol (e.g. AAPL240119C00190000)
    underlying: str
    option_type: str        # "call" or "put"
    strike: float
    expiration: str         # YYYY-MM-DD
    dte: int                # days to expiration
    # BS model values
    bs_price: float
    market_mid: float       # (bid + ask) / 2
    mispricing_pct: float   # (market - bs) / bs
    iv: float               # implied vol from market price
    # Greeks
    delta: float
    gamma: float
    vega: float
    theta: float
    # Strategy metadata
    strategy: str           # covered_call / protective_put / cash_secured_put / iron_condor
    rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class OptionsEngine:
    def __init__(self, config: dict, alpaca: AlpacaClient):
        cfg = config.get("options", {})
        self.alpaca           = alpaca
        self.risk_free        = cfg.get("risk_free_rate", 0.043)
        self.min_dte          = cfg.get("min_dte", 14)
        self.max_dte          = cfg.get("max_dte", 60)
        self.target_delta     = cfg.get("target_delta_short", 0.30)
        self.max_bid_ask_pct  = cfg.get("max_bid_ask_spread_pct", 0.15)
        self.min_open_int     = cfg.get("min_open_interest", 50)
        self.max_mispricing   = cfg.get("max_bs_mispricing_pct", 0.25)

    def find_candidates(
        self,
        underlying: str,
        spot_price: float,
        vol_estimate: VolatilityEstimate,
        regime: RegimeState,
        expiration: str,
    ) -> list[OptionCandidate]:
        """
        Fetch option chain and return scored candidates filtered by BS criteria.
        """
        chain = self.alpaca.get_options_chain(underlying, expiration, limit=100)
        if not chain:
            return []

        candidates = []
        for contract in chain:
            snap = contract.get("snapshot", {})
            c = self._evaluate_contract(
                contract, snap, spot_price, vol_estimate, regime
            )
            if c is not None:
                candidates.append(c)

        # Sort: lowest mispricing first (closest to fair value)
        candidates.sort(key=lambda x: abs(x.mispricing_pct))
        return candidates

    def select_strategy(
        self,
        underlying: str,
        spot_price: float,
        vol_estimate: VolatilityEstimate,
        regime: RegimeState,
    ) -> str:
        """Determine which options strategy fits the current regime."""
        r = regime.regime
        if r == "crisis":
            return "protective_put"
        elif r == "high_vol":
            return "cash_secured_put"  # sell vol premium
        elif r == "low_vol":
            return "covered_call"      # sell upside, collect theta
        elif r == "bull_trend":
            return "covered_call"
        elif r == "bear_trend":
            return "protective_put"
        else:
            return "cash_secured_put"  # sideways → collect theta

    def price_contract(
        self,
        option_type: str,
        spot: float,
        strike: float,
        dte: int,
        iv: float,
        dividend_yield: float = 0.0,
    ) -> dict:
        """Price a single option contract using Black-Scholes."""
        T = dte / 365.0
        if T <= 0:
            return {}
        price = bs_price(spot, strike, T, self.risk_free, iv, option_type, dividend_yield)
        g = greeks(spot, strike, T, self.risk_free, iv, option_type, dividend_yield)
        return {
            "bs_price": round(price, 4),
            "delta":    round(g["delta"], 4),
            "gamma":    round(g["gamma"], 6),
            "vega":     round(g["vega"], 4),
            "theta":    round(g["theta"], 4),
            "rho":      round(g["rho"], 4),
        }

    def compute_iv(
        self,
        market_price: float,
        option_type: str,
        spot: float,
        strike: float,
        dte: int,
    ) -> Optional[float]:
        """Compute implied vol from market price via Brent's method."""
        T = dte / 365.0
        if T <= 0 or market_price <= 0:
            return None
        try:
            return implied_vol(market_price, spot, strike, T, self.risk_free, option_type)
        except Exception:
            return None

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _evaluate_contract(
        self,
        contract: dict,
        snap: dict,
        spot: float,
        vol_est: VolatilityEstimate,
        regime: RegimeState,
    ) -> Optional[OptionCandidate]:
        """Filter and evaluate a single contract from the chain."""
        opt_type = contract.get("type", "")
        strike   = float(contract.get("strike_price", 0))
        exp_str  = contract.get("expiration_date", "")
        sym      = contract.get("symbol", "")
        underlying = contract.get("underlying_symbol", "")

        if not sym or not exp_str or strike <= 0 or opt_type not in ("call", "put"):
            return None

        try:
            exp_date = date.fromisoformat(exp_str)
        except ValueError:
            return None

        dte = (exp_date - date.today()).days
        if dte < self.min_dte or dte > self.max_dte:
            return None

        # Extract bid/ask from snapshot
        latest_quote = snap.get("latestQuote", {})
        bid = float(latest_quote.get("bp", 0) or 0)
        ask = float(latest_quote.get("ap", 0) or 0)
        if bid <= 0 or ask <= 0:
            return None

        mid = (bid + ask) / 2.0
        spread_pct = (ask - bid) / mid if mid > 0 else 1.0
        if spread_pct > self.max_bid_ask_pct:
            return None  # Too wide a spread

        T = dte / 365.0
        iv_market = self.compute_iv(mid, opt_type, spot, strike, dte)
        if iv_market is None or iv_market <= 0:
            return None

        # Use model vol for BS price (IV from market data for comparison)
        model_vol = vol_est.spot_vol
        bs_p = bs_price(spot, strike, T, self.risk_free, model_vol, opt_type)
        if bs_p <= 0:
            return None

        mispricing = (mid - bs_p) / bs_p

        g = greeks(spot, strike, T, self.risk_free, model_vol, opt_type)
        delta_abs = abs(g.get("delta", 0))

        # Delta filter (for premium-selling strategies, target ~0.30 delta)
        if abs(delta_abs - self.target_delta) > 0.20:
            return None

        strategy = self.select_strategy(underlying, spot, vol_est, regime)

        rationale = (
            f"DTE={dte}, delta={delta_abs:.2f}, IV={iv_market:.1%}, "
            f"model_vol={model_vol:.1%}, mispricing={mispricing:+.1%}"
        )

        return OptionCandidate(
            symbol=sym,
            underlying=underlying,
            option_type=opt_type,
            strike=strike,
            expiration=exp_str,
            dte=dte,
            bs_price=round(bs_p, 4),
            market_mid=round(mid, 4),
            mispricing_pct=round(mispricing, 4),
            iv=round(iv_market, 4),
            delta=round(g.get("delta", 0), 4),
            gamma=round(g.get("gamma", 0), 6),
            vega=round(g.get("vega", 0), 4),
            theta=round(g.get("theta", 0), 4),
            strategy=strategy,
            rationale=rationale,
        )
