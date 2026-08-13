"""Zone market-quality score (M7).

Deliberately *not* a livability/safety/schools score — REMIP has no
authorized dataset for that (see docs/INTEGRATIONS.md) and fabricating one
would violate the platform's core transparency principle. Instead this is a
composite read of the same correlational drivers already computed by
services/explanation.py (inventory, days-on-market, price-reduction share),
converted into a single 0-100 number so zones/listings can be ranked and
compared at a glance — with the drivers that produced it always attached,
never presented as an opaque black box.
"""
from __future__ import annotations

from typing import Any

from app.models import EconomicIndicator, MarketMetric
from app.services.explanation import explain_trend

_STRENGTH_WEIGHT = {"weak": 8, "moderate": 16}
_BASELINE = 50


def _driver_weight(driver: dict[str, str]) -> int:
    return _STRENGTH_WEIGHT.get(driver["strength"], 5)


def compute_market_score(
    series: list[MarketMetric], latest_national_hpi: EconomicIndicator | None = None
) -> dict[str, Any] | None:
    """None when there isn't enough history (same threshold as
    explain_trend) — no score is better than a score computed on noise."""
    explanation = explain_trend(series, latest_national_hpi)
    if not explanation["available"]:
        return None

    score = _BASELINE
    score += sum(_driver_weight(d) for d in explanation["positive_drivers"])
    score -= sum(_driver_weight(d) for d in explanation["negative_drivers"])
    score = max(0, min(100, score))

    if score >= 65:
        label = "mercato forte"
    elif score <= 35:
        label = "mercato debole"
    else:
        label = "mercato nella media"

    return {
        "score": score,
        "label": label,
        "observed_trend": explanation["observed_trend"],
        "evidence_strength": explanation["evidence_strength"],
        "positive_drivers": explanation["positive_drivers"],
        "negative_drivers": explanation["negative_drivers"],
        "methodology": "Punteggio composito derivato dagli stessi driver del motore di "
        "spiegazione (offerta, tempi di vendita, quota ribassi): +16/-16 per driver "
        "'moderate', +8/-8 per 'weak', partendo da una base neutra di 50.",
        "limitations": "Misura la dinamica del mercato immobiliare osservata nei dati, non "
        "la qualità della vita, la sicurezza o i servizi della zona — nessuna di queste "
        "informazioni è disponibile su questa piattaforma (vedi docs/INTEGRATIONS.md).",
    }
