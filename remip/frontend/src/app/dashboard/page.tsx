"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  formatPct,
  formatPrice,
  type Area,
  type AreaCompareRow,
  type DataContext,
  type ExplanationResult,
  type ForecastItem,
  type MarketMetricPoint,
  type MarketSummary,
} from "@/lib/api";
import { AreaPicker } from "@/components/AreaPicker";
import { DataContextFooter } from "@/components/DataContextFooter";
import { PriceTrendChart, VolumeChart } from "@/components/charts";

const directionTone: Record<string, string> = {
  positive: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  negative: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  neutral: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

function ExplanationPanel({ areaId }: { areaId: string }) {
  const [result, setResult] = useState<ExplanationResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<{ data: ExplanationResult; data_context: DataContext }>(
      `/api/v1/market/explanation?area_id=${areaId}`,
      { auth: false },
    )
      .then((r) => !cancelled && setResult(r.data))
      .catch(() => !cancelled && setResult(null));
    return () => {
      cancelled = true;
    };
  }, [areaId]);

  if (!result) return null;
  if (!result.available) {
    return (
      <div className="card text-sm text-slate-500" aria-label="Motivazioni dell'andamento">
        {result.reason}
      </div>
    );
  }

  const allDrivers = [
    ...(result.positive_drivers ?? []),
    ...(result.negative_drivers ?? []),
    ...(result.neutral_indicators ?? []),
  ];

  return (
    <div className="card space-y-3" aria-label="Motivazioni dell'andamento">
      <div>
        <h2 className="font-semibold">
          Perché il mercato è {result.observed_trend}
          {result.price_change_pct !== null && result.price_change_pct !== undefined && (
            <span className="ml-1 text-sm font-normal text-slate-500">
              ({formatPct(result.price_change_pct)} in {result.period_months} mesi)
            </span>
          )}
        </h2>
        <p className="text-xs text-slate-500">
          Robustezza delle evidenze: {result.evidence_strength}
        </p>
      </div>
      <ul className="space-y-1.5">
        {allDrivers.map((d) => (
          <li key={d.name} className="flex items-start gap-2 text-sm">
            <span
              className={`mt-0.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${directionTone[d.direction]}`}
            >
              {d.direction === "positive" ? "▲" : d.direction === "negative" ? "▼" : "●"}
            </span>
            <span>
              <span className="font-medium">{d.name}</span> — {d.evidence}
            </span>
          </li>
        ))}
      </ul>
      {result.national_context && (
        <div className="rounded-lg bg-slate-100 p-2.5 text-xs dark:bg-slate-800/60">
          <p className="font-medium">
            Contesto nazionale (fonte live): {result.national_context.indicator} —{" "}
            {result.national_context.value}
            {result.national_context.unit === "pct_change_yoy" ? "%" : ""} (
            {result.national_context.period})
          </p>
          <p className="mt-1 text-slate-500">{result.national_context.note}</p>
        </div>
      )}
      <details className="text-xs text-slate-500">
        <summary className="cursor-pointer font-medium">
          Limiti e fattori non misurati / spiegazioni alternative
        </summary>
        <ul className="mt-1 list-inside list-disc space-y-0.5">
          {(result.uncertain_elements ?? []).map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
        <p className="mt-2">{result.alternative_explanations}</p>
      </details>
    </div>
  );
}

function AreaCompareSection({ mainArea }: { mainArea: Area }) {
  const [extra1, setExtra1] = useState<Area | null>(null);
  const [extra2, setExtra2] = useState<Area | null>(null);
  const [extra3, setExtra3] = useState<Area | null>(null);
  const [rows, setRows] = useState<AreaCompareRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Each picker defaults to the same first city on load, so de-dupe against
  // the main area and against each other rather than requiring the user to
  // manually pick 3 distinct extra zones before the button ever enables.
  const seen = new Set([mainArea.id]);
  const uniqueExtras: Area[] = [];
  for (const extra of [extra1, extra2, extra3]) {
    if (extra && !seen.has(extra.id)) {
      seen.add(extra.id);
      uniqueExtras.push(extra);
    }
  }
  const areaIds = [mainArea.id, ...uniqueExtras.map((a) => a.id)];
  const canCompare = areaIds.length >= 2;

  const compare = () => {
    setError(null);
    const params = new URLSearchParams();
    areaIds.forEach((id) => params.append("area_ids", id));
    api<AreaCompareRow[]>(`/api/v1/market/compare-areas?${params}`, { auth: false })
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Errore nel confronto"));
  };

  return (
    <section className="card space-y-3" aria-label="Confronta aree">
      <h2 className="font-semibold">Confronta con altre zone</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <AreaPicker onChange={setExtra1} />
        <AreaPicker onChange={setExtra2} />
        <AreaPicker onChange={setExtra3} />
      </div>
      <button type="button" className="btn-secondary" disabled={!canCompare} onClick={compare}>
        Confronta {mainArea.name} con le zone selezionate
      </button>
      {!canCompare && (
        <p className="text-xs text-slate-500">
          Seleziona almeno una zona diversa da {mainArea.name} nei campi sopra.
        </p>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {rows && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] border-separate border-spacing-y-1 text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th>Zona</th>
                <th>€/m² medio</th>
                <th>Annunci attivi</th>
                <th>Giorni sul mercato</th>
                <th>Rendimento lordo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.area_id} className="rounded-lg bg-slate-50 dark:bg-slate-800/50">
                  <td className="px-2 py-1.5 font-medium">{r.area_name ?? r.area_id}</td>
                  <td className="px-2 py-1.5">
                    {r.available && r.avg_price_sqm
                      ? `${r.avg_price_sqm.toLocaleString("it-IT")} €`
                      : "n/d"}
                  </td>
                  <td className="px-2 py-1.5">{r.available ? r.active_listings : "n/d"}</td>
                  <td className="px-2 py-1.5">
                    {r.available && r.avg_days_on_market ? Math.round(r.avg_days_on_market) : "n/d"}
                  </td>
                  <td className="px-2 py-1.5">
                    {r.available && r.gross_yield_pct !== null
                      ? `${r.gross_yield_pct?.toFixed(1)}%`
                      : "n/d"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

interface Envelope<T> {
  data: T;
  data_context: DataContext;
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function ChangeChip({ label, value }: { label: string; value: number | null }) {
  const tone =
    value === null
      ? "bg-slate-100 text-slate-500 dark:bg-slate-800"
      : value >= 0
        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
        : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300";
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>
      {label}: {formatPct(value)}
    </span>
  );
}

const horizonLabel: Record<number, string> = {
  3: "3 mesi",
  6: "6 mesi",
  12: "12 mesi",
  60: "5 anni",
  120: "10 anni",
};

export default function DashboardPage() {
  const [area, setArea] = useState<Area | null>(null);
  const [summary, setSummary] = useState<Envelope<MarketSummary> | null>(null);
  const [metrics, setMetrics] = useState<MarketMetricPoint[]>([]);
  const [forecast, setForecast] = useState<Envelope<ForecastItem[]> | null>(null);
  const [loading, setLoading] = useState(false);

  const onAreaChange = useCallback((a: Area | null) => setArea(a), []);

  useEffect(() => {
    if (!area) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api<Envelope<MarketSummary>>(`/api/v1/market/summary?area_id=${area.id}`, { auth: false }),
      api<Envelope<MarketMetricPoint[]>>(`/api/v1/market/metrics?area_id=${area.id}&months=36`, {
        auth: false,
      }),
      api<Envelope<ForecastItem[]>>(`/api/v1/market/forecast?area_id=${area.id}`, { auth: false }),
    ])
      .then(([s, m, f]) => {
        if (cancelled) return;
        setSummary(s);
        setMetrics(m.data);
        setForecast(f);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [area]);

  const s = summary?.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Dashboard di zona</h1>
          <p className="text-sm text-slate-500">
            Stato del mercato immobiliare (vendita) nell&apos;area selezionata
          </p>
        </div>
        {area && (
          <Link href={`/listings?area_id=${area.id}`} className="btn-secondary">
            Vedi annunci in {area.name} →
          </Link>
        )}
      </div>

      <div className="card">
        <AreaPicker onChange={onAreaChange} />
      </div>

      {loading && <p className="text-sm text-slate-500">Caricamento…</p>}

      {s && s.available && (
        <>
          <section aria-label="Indicatori principali">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Kpi label="Prezzo medio" value={formatPrice(s.avg_price, s.currency)} />
              <Kpi label="Prezzo mediano" value={formatPrice(s.median_price, s.currency)} />
              <Kpi
                label="€/m² medio"
                value={`${s.avg_price_sqm.toLocaleString("it-IT")} €`}
                hint={`mediano ${s.median_price_sqm.toLocaleString("it-IT")} €`}
              />
              <Kpi
                label="Rendimento lordo"
                value={`${s.gross_yield_pct.toFixed(1)}%`}
                hint={`canone ${s.rent_avg_sqm.toFixed(1)} €/m²/mese`}
              />
              <Kpi label="Annunci attivi" value={String(s.active_listings)} />
              <Kpi
                label="Nuovi / rimossi (mese)"
                value={`${s.new_listings} / ${s.removed_listings}`}
              />
              <Kpi label="Giorni sul mercato" value={`${Math.round(s.avg_days_on_market)}`} />
              <Kpi
                label="Annunci con ribasso"
                value={`${Math.round(s.price_reduction_share * 100)}%`}
                hint={`sconto medio ${s.avg_discount_pct.toFixed(1)}%`}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2" aria-label="Variazioni di prezzo">
              {(["1m", "3m", "6m", "12m", "5y", "10y"] as const).map((k) => (
                <ChangeChip key={k} label={k} value={s.changes_pct[k] ?? null} />
              ))}
            </div>
            {summary && <DataContextFooter context={summary.data_context} />}
          </section>

          <section className="grid gap-4 lg:grid-cols-2" aria-label="Grafici">
            <div className="card">
              <h2 className="mb-2 font-semibold">Trend €/m² (36 mesi)</h2>
              <PriceTrendChart series={metrics} />
            </div>
            <div className="card">
              <h2 className="mb-2 font-semibold">Volume annunci</h2>
              <VolumeChart series={metrics} />
            </div>
          </section>

          {forecast && (
            <section aria-label="Previsioni">
              <h2 className="mb-2 font-semibold">Previsioni (variazione €/m² attesa)</h2>
              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {forecast.data.map((f) => (
                  <div key={f.horizon_months} className="card">
                    <p className="text-xs text-slate-500">
                      {horizonLabel[f.horizon_months] ?? `${f.horizon_months} mesi`}
                    </p>
                    <p className="mt-1 text-lg font-semibold">{formatPct(f.scenarios.base)}</p>
                    <p className="text-xs text-slate-500">
                      da {formatPct(f.scenarios.negative)} a {formatPct(f.scenarios.positive)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      confidenza {Math.round(f.confidence * 100)}% ·{" "}
                      {f.method === "linear_trend" ? "trend statistico" : "scenario strutturale"}
                    </p>
                  </div>
                ))}
              </div>
              <DataContextFooter context={forecast.data_context} />
            </section>
          )}

          {area && <ExplanationPanel areaId={area.id} />}
          {area && <AreaCompareSection mainArea={area} />}
        </>
      )}
    </div>
  );
}
