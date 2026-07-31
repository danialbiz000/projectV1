"""Baseline forecasting.

Deliberately simple and fully interpretable (see PLAN.md — "baseline robuste
prima di modelli complessi"):

- Short/medium horizons (3, 6, 12 months): ordinary least-squares linear trend
  on the last 24 monthly avg_price_sqm observations, projected forward. The
  low/high scenarios widen with the residual standard deviation and the horizon.
- Long horizons (60, 120 months): NOT a statistical extrapolation. They are
  structural scenarios anchored to a conservative long-run real-estate drift,
  with wide bands and low confidence, clearly labelled as such.

Different horizons intentionally use different methods (brief requirement).
"""
from __future__ import annotations

from statistics import mean, pstdev

from app.models import MarketMetric

MODEL_VERSION = "baseline-0.1"
TREND_WINDOW = 24
SHORT_HORIZONS = (3, 6, 12)
STRUCTURAL_HORIZONS = (60, 120)
# Conservative long-run nominal drift assumption (% / year) for structural scenarios.
STRUCTURAL_ANNUAL_DRIFT_PCT = 1.5


def _linear_trend(values: list[float]) -> tuple[float, float, float]:
    """OLS fit y = a + b*x. Returns (a, b, residual_std)."""
    n = len(values)
    xs = list(range(n))
    x_mean, y_mean = mean(xs), mean(values)
    denom = sum((x - x_mean) ** 2 for x in xs) or 1.0
    b = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values, strict=True)) / denom
    a = y_mean - b * x_mean
    residuals = [y - (a + b * x) for x, y in zip(xs, values, strict=True)]
    return a, b, pstdev(residuals) if n > 1 else 0.0


def compute_forecasts(series: list[MarketMetric]) -> list[dict]:
    """Return forecast dicts (one per horizon) from a monthly metric series."""
    if len(series) < 6:
        return []
    values = [m.avg_price_sqm for m in series[-TREND_WINDOW:]]
    a, b, resid_std = _linear_trend(values)
    n = len(values)
    last = values[-1]
    monthly_trend_pct = (b / last * 100) if last else 0.0

    results: list[dict] = []
    for horizon in SHORT_HORIZONS:
        projected = a + b * (n - 1 + horizon)
        base = (projected - last) / last * 100 if last else 0.0
        # Band = residual noise scaled by sqrt(horizon), floor of ±1%/quarter.
        band = max((resid_std / last * 100 if last else 1.0) * (horizon**0.5), horizon / 3)
        results.append(
            {
                "horizon_months": horizon,
                "method": "linear_trend",
                "base_change_pct": round(base, 2),
                "low_change_pct": round(base - band, 2),
                "high_change_pct": round(base + band, 2),
                "confidence": round(max(0.2, 0.75 - 0.02 * horizon), 2),
                "drivers": [
                    {
                        "name": "trend storico prezzi (24 mesi)",
                        "direction": "up" if b > 0 else ("down" if b < 0 else "flat"),
                        "evidence": "observed",
                        "detail": f"trend medio {monthly_trend_pct:+.2f}%/mese",
                    },
                ],
                "limitations": (
                    "Estrapolazione lineare del solo trend storico su dati demo: non "
                    "considera tassi, credito, demografia o shock. Non è una consulenza "
                    "finanziaria."
                ),
            }
        )
    for horizon in STRUCTURAL_HORIZONS:
        years = horizon / 12
        drift = STRUCTURAL_ANNUAL_DRIFT_PCT * years
        results.append(
            {
                "horizon_months": horizon,
                "method": "structural_scenario",
                "base_change_pct": round(drift, 2),
                "low_change_pct": round(drift - 8 * years, 2),
                "high_change_pct": round(drift + 8 * years, 2),
                "confidence": 0.15,
                "drivers": [
                    {
                        "name": "deriva nominale di lungo periodo (assunzione)",
                        "direction": "up",
                        "evidence": "assumption",
                        "detail": f"{STRUCTURAL_ANNUAL_DRIFT_PCT}%/anno, scenario strutturale",
                    },
                ],
                "limitations": (
                    "Scenario strutturale, NON previsione statistica: bande molto ampie, "
                    "nessun potere predittivo puntuale a 5-10 anni."
                ),
            }
        )
    return results
