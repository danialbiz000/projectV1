"""Market-trend explanation engine (M5).

Implements the brief's "MOTIVAZIONI DELL'ANDAMENTO": explain why a market
looks like it's rising, falling or flat — WITHOUT inventing causality. Every
driver below is a correlation read directly off the observed MarketMetric
series (active listings, days on market, price-reduction share, ...), each
tagged with its own evidence and strength. Anything commonly cited as a real
driver of house prices that we don't actually measure locally — interest
rates, credit conditions, income, employment, construction, migration — is
listed under "uncertain_elements" instead of silently assumed. When a real
national indicator exists (Eurostat HPI, see adapters/eurostat.py), it's
surfaced separately as context, not blended into the area-level drivers.
"""
from __future__ import annotations

from typing import Any

from app.models import EconomicIndicator, MarketMetric

MIN_MONTHS = 6

UNCERTAIN_ELEMENTS = [
    "Tassi di interesse e condizioni di credito (non disponibili in questa piattaforma)",
    "Reddito medio e occupazione locale (non disponibili a livello di area)",
    "Nuove costruzioni e permessi edilizi (non disponibili)",
    "Normativa fiscale e urbanistica (non disponibile)",
    "Flussi migratori e demografia (non disponibili a livello di area)",
]

ALTERNATIVE_EXPLANATIONS = (
    "I segnali sotto sono correlazioni osservate nella serie storica degli annunci, non "
    "relazioni causali verificate: un aumento dei prezzi correlato a una minore offerta "
    "potrebbe riflettere maggiore domanda, ma anche una riduzione temporanea delle "
    "pubblicazioni per motivi stagionali o scelte di prezzo delle agenzie. Non è possibile "
    "distinguere queste ipotesi con i soli dati disponibili."
)


def _pct_change(old: float | None, new: float | None) -> float | None:
    if not old:
        return None
    return round((new - old) / old * 100, 2) if new is not None else None


def _driver(name: str, direction: str, strength: str, evidence: str, source: str) -> dict[str, str]:
    return {
        "name": name,
        "direction": direction,
        "strength": strength,
        "evidence": evidence,
        "source": source,
    }


def _inventory_driver(first: MarketMetric, last: MarketMetric) -> dict[str, str] | None:
    change = _pct_change(first.active_listings, last.active_listings)
    if change is None:
        return None
    if change < -5:
        return _driver(
            "Riduzione dell'offerta attiva",
            "positive",
            "moderate" if change < -15 else "weak",
            f"Annunci attivi: {change:+.1f}% negli ultimi {MIN_MONTHS} mesi",
            "MarketMetric.active_listings",
        )
    if change > 10:
        return _driver(
            "Aumento dell'offerta attiva",
            "negative",
            "moderate" if change > 25 else "weak",
            f"Annunci attivi: {change:+.1f}% negli ultimi {MIN_MONTHS} mesi",
            "MarketMetric.active_listings",
        )
    return _driver(
        "Offerta attiva stabile",
        "neutral",
        "weak",
        f"Annunci attivi: {change:+.1f}%",
        "MarketMetric.active_listings",
    )


def _days_on_market_driver(first: MarketMetric, last: MarketMetric) -> dict[str, str] | None:
    change = _pct_change(first.avg_days_on_market, last.avg_days_on_market)
    if change is None or -10 <= change <= 10:
        return None
    direction = "positive" if change < 0 else "negative"
    return _driver(
        "Tempi di vendita in diminuzione" if change < 0 else "Tempi di vendita in aumento",
        direction,
        "moderate" if abs(change) > 20 else "weak",
        f"Giorni medi sul mercato: {first.avg_days_on_market:.0f} → "
        f"{last.avg_days_on_market:.0f} ({change:+.1f}%)",
        "MarketMetric.avg_days_on_market",
    )


def _price_reduction_driver(last: MarketMetric) -> dict[str, str] | None:
    if last.price_reduction_share > 0.30:
        return _driver(
            "Ampia quota di annunci con ribasso",
            "negative",
            "moderate" if last.price_reduction_share > 0.40 else "weak",
            f"{last.price_reduction_share * 100:.0f}% degli annunci attivi ha subito un "
            f"ribasso (sconto medio {last.avg_discount_pct:.1f}%)",
            "MarketMetric.price_reduction_share",
        )
    if last.price_reduction_share < 0.15:
        return _driver(
            "Pochi ribassi di prezzo",
            "positive",
            "weak",
            f"Solo il {last.price_reduction_share * 100:.0f}% degli annunci attivi ha subito "
            "un ribasso",
            "MarketMetric.price_reduction_share",
        )
    return None


def _absorption_indicator(last: MarketMetric) -> dict[str, str]:
    return _driver(
        "Bilancio nuovi annunci / rimossi (assorbimento)",
        "neutral",
        "weak",
        f"Ultimo mese: {last.new_listings} nuovi, {last.removed_listings} rimossi",
        "MarketMetric.new_listings/removed_listings",
    )


def _national_context(latest_hpi: EconomicIndicator | None) -> dict[str, Any] | None:
    if latest_hpi is None:
        return None
    return {
        "indicator": latest_hpi.indicator_name,
        "period": latest_hpi.period,
        "value": latest_hpi.value,
        "unit": latest_hpi.unit,
        "source": latest_hpi.source_code,
        "is_demo_data": False,
        "note": "Contesto nazionale da fonte live (Eurostat), non un driver dell'area — "
        "confrontalo con il trend locale sotto, non sommarlo.",
    }


def explain_trend(
    series: list[MarketMetric], latest_national_hpi: EconomicIndicator | None = None
) -> dict[str, Any]:
    if len(series) < MIN_MONTHS:
        return {
            "available": False,
            "reason": f"Servono almeno {MIN_MONTHS} mesi di dati per un'analisi affidabile "
            f"(disponibili: {len(series)}).",
        }

    first, last = series[-MIN_MONTHS], series[-1]
    price_change_pct = _pct_change(first.avg_price_sqm, last.avg_price_sqm)
    if price_change_pct is None or -2 <= price_change_pct <= 2:
        observed_trend = "stabile"
    else:
        observed_trend = "in crescita" if price_change_pct > 0 else "in calo"

    drivers = [
        d
        for d in (
            _inventory_driver(first, last),
            _days_on_market_driver(first, last),
            _price_reduction_driver(last),
        )
        if d is not None
    ]
    drivers.append(_absorption_indicator(last))

    positives = [d for d in drivers if d["direction"] == "positive"]
    negatives = [d for d in drivers if d["direction"] == "negative"]
    neutrals = [d for d in drivers if d["direction"] == "neutral"]

    if positives and negatives:
        evidence_strength = "mista/contrastante"
    elif any(d["strength"] == "moderate" for d in positives + negatives):
        evidence_strength = "moderata"
    elif positives or negatives:
        evidence_strength = "debole"
    else:
        evidence_strength = "insufficiente"

    return {
        "available": True,
        "period_months": MIN_MONTHS,
        "observed_trend": observed_trend,
        "price_change_pct": price_change_pct,
        "positive_drivers": positives,
        "negative_drivers": negatives,
        "neutral_indicators": neutrals,
        "evidence_strength": evidence_strength,
        "sources": sorted({d["source"] for d in drivers}),
        "national_context": _national_context(latest_national_hpi),
        "uncertain_elements": UNCERTAIN_ELEMENTS,
        "alternative_explanations": ALTERNATIVE_EXPLANATIONS,
    }
