"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  formatPct,
  formatPrice,
  type Area,
  type DataContext,
  type ForecastItem,
  type MarketMetricPoint,
  type MarketSummary,
} from "@/lib/api";
import { AreaPicker } from "@/components/AreaPicker";
import { DataContextFooter } from "@/components/DataContextFooter";
import { PriceTrendChart, VolumeChart } from "@/components/charts";

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
        </>
      )}
    </div>
  );
}
