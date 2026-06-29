"""
Alpaca REST client for NexusQuant.

Covers:
  - Stock bars (single + multi symbol)
  - Options chain with snapshots and Greeks
  - Account and positions
  - Order submission

All credentials are read from environment variables (loaded via .env).
Paper trading by default; set ALPACA_BASE_URL to live endpoint to switch.
"""

import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")
_API_KEY  = os.getenv("ALPACA_API_KEY", "")
_SECRET   = os.getenv("ALPACA_SECRET_KEY", "")


class AlpacaClient:
    """
    Thin wrapper around Alpaca REST API v2 (broker) and v2/v1beta1 (data).
    Thread-safe via per-call requests (no shared session state between calls).
    """

    def __init__(
        self,
        api_key: str = _API_KEY,
        secret_key: str = _SECRET,
        base_url: str = _BASE_URL,
        data_url: str = _DATA_URL,
    ):
        if not api_key or not secret_key:
            raise ValueError(
                "Alpaca credentials missing. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY in your .env file."
            )
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
        }
        self._base = base_url.rstrip("/")
        self._data = data_url.rstrip("/")

    # ─── Account ──────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        return self._get(self._base, "/v2/account")

    def get_positions(self) -> list[dict]:
        data = self._get(self._base, "/v2/positions")
        return data if isinstance(data, list) else []

    # ─── Stock bars ───────────────────────────────────────────────────────────

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        limit: int = 300,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars for a single symbol.
        Returns a DataFrame indexed by datetime with columns:
        open, high, low, close, volume, vwap, trade_count.
        """
        params = {
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "split",
            "feed": "iex",
        }
        data = self._get(self._data, f"/v2/stocks/{symbol}/bars", params=params)
        bars = data.get("bars", [])
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.set_index("t").rename(columns={
            "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume",
            "vw": "vwap", "n": "trade_count",
        })
        return df.sort_index()

    def get_bars_multi(
        self,
        symbols: list[str],
        timeframe: str = "1Day",
        limit: int = 300,
    ) -> dict[str, pd.DataFrame]:
        """Fetch bars for multiple symbols in a single request."""
        params = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "split",
            "feed": "iex",
        }
        data = self._get(self._data, "/v2/stocks/bars", params=params)
        result: dict[str, pd.DataFrame] = {}
        for sym, bars in data.get("bars", {}).items():
            if not bars:
                continue
            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"])
            df = df.set_index("t").rename(columns={
                "o": "open", "h": "high", "l": "low",
                "c": "close", "v": "volume",
                "vw": "vwap", "n": "trade_count",
            })
            result[sym] = df.sort_index()
        return result

    def get_latest_quote(self, symbol: str) -> dict:
        """Return latest bid/ask quote for a stock."""
        data = self._get(self._data, f"/v2/stocks/{symbol}/quotes/latest",
                         params={"feed": "iex"})
        return data.get("quote", {})

    # ─── Options ──────────────────────────────────────────────────────────────

    def get_options_chain(
        self,
        underlying: str,
        expiration: Optional[str] = None,
        expiration_gte: Optional[str] = None,
        expiration_lte: Optional[str] = None,
        option_type: Optional[str] = None,
        strike_gte: Optional[float] = None,
        strike_lte: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch options chain for an underlying symbol.

        Returns a list of dicts, each containing:
          - contract metadata (symbol, type, strike, expiration)
          - snapshot (latestQuote, latestTrade, greeks, impliedVolatility)

        Greeks are included when available on the indicative feed.

        Args:
            underlying:     Ticker symbol (e.g. "SPY")
            expiration:     Exact expiration date "YYYY-MM-DD" (takes priority)
            expiration_gte: Earliest expiration date "YYYY-MM-DD"
            expiration_lte: Latest expiration date "YYYY-MM-DD"
            option_type:    "call" or "put" (None = both)
            strike_gte:     Minimum strike price filter
            strike_lte:     Maximum strike price filter
            limit:          Max contracts to return (Alpaca max = 1000 per page)
        """
        params: dict = {"feed": "indicative", "limit": min(limit, 1000)}

        if expiration:
            params["expiration_date"] = expiration
        else:
            if expiration_gte:
                params["expiration_date_gte"] = expiration_gte
            if expiration_lte:
                params["expiration_date_lte"] = expiration_lte

        if option_type in ("call", "put"):
            params["type"] = option_type
        if strike_gte is not None:
            params["strike_price_gte"] = strike_gte
        if strike_lte is not None:
            params["strike_price_lte"] = strike_lte

        snapshots_raw = self._get(
            self._data,
            f"/v1beta1/options/snapshots/{underlying}",
            params=params,
        )

        snapshots = snapshots_raw.get("snapshots", {})
        if not snapshots:
            logger.debug(f"No options snapshots for {underlying} with params={params}")
            return []

        # Parse OCC symbol into contract metadata + attach snapshot
        results: list[dict] = []
        for occ_symbol, snap in snapshots.items():
            contract = _parse_occ_symbol(occ_symbol)
            if contract is None:
                continue

            quote = snap.get("latestQuote", {})
            bid = float(quote.get("bp", 0) or 0)
            ask = float(quote.get("ap", 0) or 0)

            if bid <= 0 and ask <= 0:
                continue  # no market data

            greeks_raw = snap.get("greeks", {})
            results.append({
                "symbol":             occ_symbol,
                "underlying_symbol":  underlying,
                "type":               contract["type"],
                "strike_price":       contract["strike"],
                "expiration_date":    contract["expiration"],
                "snapshot": {
                    "latestQuote": quote,
                    "latestTrade": snap.get("latestTrade", {}),
                    "impliedVolatility": snap.get("impliedVolatility"),
                    "greeks": greeks_raw,
                },
            })

        return results

    def get_options_expirations(
        self,
        underlying: str,
        min_dte: int = 7,
        max_dte: int = 60,
    ) -> list[str]:
        """
        Return available expiration dates for an underlying within a DTE range,
        sorted ascending. Derived from the snapshots endpoint (no dedicated
        expirations endpoint on Alpaca free tier).
        """
        today = date.today()
        exp_gte = (today + timedelta(days=min_dte)).isoformat()
        exp_lte = (today + timedelta(days=max_dte)).isoformat()

        params = {
            "feed": "indicative",
            "limit": 1000,
            "expiration_date_gte": exp_gte,
            "expiration_date_lte": exp_lte,
        }
        data = self._get(
            self._data,
            f"/v1beta1/options/snapshots/{underlying}",
            params=params,
        )
        expirations = set()
        for occ_symbol in data.get("snapshots", {}):
            c = _parse_occ_symbol(occ_symbol)
            if c:
                expirations.add(c["expiration"])

        return sorted(expirations)

    # ─── Order submission ─────────────────────────────────────────────────────

    def submit_order(self, order: dict) -> dict:
        """
        Submit an order to Alpaca.

        Expected keys in `order`:
          symbol        : OCC symbol for options, ticker for equities
          qty           : number of contracts / shares
          side          : "buy" or "sell"
          type          : "market" or "limit"
          time_in_force : "day" or "gtc"
          limit_price   : (optional) required for limit orders
          order_class   : (optional) "mleg" for multi-leg
          legs          : (optional) list of leg dicts for multi-leg orders
        """
        resp = self._post(self._base, "/v2/orders", order)
        return resp

    # ─── Internal HTTP helpers ────────────────────────────────────────────────

    def _get(
        self,
        base: str,
        path: str,
        params: Optional[dict] = None,
        retries: int = 3,
    ) -> dict | list:
        url = f"{base}{path}"
        for attempt in range(retries):
            try:
                resp = requests.get(
                    url, headers=self._headers, params=params, timeout=15
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited on {path}, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    logger.error(f"GET {path} failed after {retries} attempts: {e}")
                    return {}
                time.sleep(2 ** attempt)
        return {}

    def _post(
        self,
        base: str,
        path: str,
        payload: dict,
        retries: int = 3,
    ) -> dict:
        url = f"{base}{path}"
        headers = {**self._headers, "Content-Type": "application/json"}
        for attempt in range(retries):
            try:
                resp = requests.post(
                    url, headers=headers, json=payload, timeout=15
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited on {path}, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    logger.error(f"POST {path} failed after {retries} attempts: {e}")
                    return {}
                time.sleep(2 ** attempt)
        return {}


# ─── OCC Symbol parser ────────────────────────────────────────────────────────

def _parse_occ_symbol(occ: str) -> Optional[dict]:
    """
    Parse an OCC option symbol into its components.
    Format: <TICKER><YY><MM><DD><C|P><8-digit-strike>
    Example: SPY250131C00590000 → SPY, 2025-01-31, call, 590.00

    Returns None if the symbol doesn't match the expected format.
    """
    try:
        # Find where the date starts (6 digits after the ticker)
        # Ticker can be 1-5 characters
        for i in range(1, 6):
            if len(occ) >= i + 15 and occ[i:i+6].isdigit():
                ticker = occ[:i]
                date_str = occ[i:i+6]
                cp = occ[i+6]
                strike_raw = occ[i+7:]
                break
        else:
            return None

        if cp not in ("C", "P"):
            return None

        expiration = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
        strike = int(strike_raw) / 1000.0
        option_type = "call" if cp == "C" else "put"

        return {
            "ticker":     ticker,
            "expiration": expiration,
            "type":       option_type,
            "strike":     strike,
        }
    except Exception:
        return None
