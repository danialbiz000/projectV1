"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  api,
  formatPct,
  formatPrice,
  type ListingDetail,
  type ValuationOut,
  type WatchlistOut,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { isInCompare, toggleCompare, MAX_COMPARE } from "@/lib/compare";

const featureLabels: Record<string, string> = {
  elevator: "Ascensore",
  balcony: "Balcone",
  garage: "Garage",
  garden: "Giardino",
};

const diffLabels: Record<string, string> = {
  price: "Prezzo",
  title: "Titolo",
  description: "Descrizione",
  photos_count: "Fotografie",
  size_sqm: "Superficie",
  rooms: "Locali",
  energy_class: "Classe energetica",
  status: "Stato",
};

export default function ListingDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const [detail, setDetail] = useState<ListingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watchMessage, setWatchMessage] = useState<string | null>(null);
  const [inCompare, setInCompare] = useState(false);
  const [valuations, setValuations] = useState<ValuationOut[]>([]);
  const [valuationMessage, setValuationMessage] = useState<string | null>(null);

  const loadValuations = useCallback(() => {
    if (!params?.id) return;
    api<ValuationOut[]>(`/api/v1/listings/${params.id}/valuations`, { auth: false })
      .then(setValuations)
      .catch(() => setValuations([]));
  }, [params?.id]);

  useEffect(() => {
    if (!params?.id) return;
    setInCompare(isInCompare(params.id));
    api<ListingDetail>(`/api/v1/listings/${params.id}`, { auth: false })
      .then(setDetail)
      .catch(() => setError("Annuncio non trovato"));
    loadValuations();
  }, [params?.id, loadValuations]);

  const requestValuation = async () => {
    if (!params?.id) return;
    setValuationMessage(null);
    try {
      await api<ValuationOut>(`/api/v1/listings/${params.id}/valuations`, { method: "POST" });
      setValuationMessage("Valutazione salvata ✓");
      loadValuations();
    } catch (err) {
      setValuationMessage(err instanceof Error ? err.message : "Errore: riprova");
    }
  };

  const addToWatchlist = async () => {
    if (!detail) return;
    try {
      const watchlists = await api<WatchlistOut[]>("/api/v1/watchlists");
      const target =
        watchlists[0] ??
        (await api<WatchlistOut>("/api/v1/watchlists", { method: "POST" }));
      await api(`/api/v1/watchlists/${target.id}/items`, {
        method: "POST",
        body: { kind: "listing", listing_id: detail.id },
      });
      setWatchMessage("Aggiunto alla watchlist ✓");
    } catch {
      setWatchMessage("Errore: riprova");
    }
  };

  if (error) {
    return (
      <div className="pt-10 text-center">
        <p>{error}</p>
        <Link href="/listings" className="btn-secondary mt-4">
          ← Torna alla ricerca
        </Link>
      </div>
    );
  }
  if (!detail) return <p className="text-sm text-slate-500">Caricamento…</p>;

  const chartData = detail.price_history.map((p) => ({
    date: p.observed_at.slice(0, 10),
    price: p.price,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{detail.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {detail.address_text} · {detail.area_name} · fonte {detail.source_name}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-brand-600">
            {formatPrice(detail.current_price, detail.currency)}
            {detail.listing_type === "rent" && (
              <span className="text-sm font-normal">/mese</span>
            )}
          </p>
          {detail.price_per_sqm && (
            <p className="text-sm text-slate-500">
              {detail.price_per_sqm.toLocaleString("it-IT")} €/m²
              {detail.deviation_from_area_pct !== null &&
                ` · ${formatPct(detail.deviation_from_area_pct)} vs zona`}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {user ? (
          <button type="button" onClick={addToWatchlist} className="btn-primary">
            ☆ Aggiungi alla watchlist
          </button>
        ) : (
          <Link href="/login" className="btn-secondary">
            Accedi per salvare nella watchlist
          </Link>
        )}
        {watchMessage && <p className="self-center text-sm text-slate-500">{watchMessage}</p>}
        <button
          type="button"
          className="btn-secondary"
          aria-pressed={inCompare}
          onClick={() => setInCompare(toggleCompare(detail.id).includes(detail.id))}
        >
          {inCompare ? "✓ In confronto" : `+ Aggiungi al confronto (max ${MAX_COMPARE})`}
        </button>
      </div>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <h2 className="font-semibold">Caratteristiche</h2>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">Superficie</dt>
              <dd>{detail.size_sqm} m²</dd>
            </div>
            <div>
              <dt className="text-slate-500">Locali / bagni</dt>
              <dd>
                {detail.rooms} / {detail.bathrooms}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Piano</dt>
              <dd>{detail.floor ?? "n/d"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Anno</dt>
              <dd>{detail.year_built ?? "n/d"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Classe energetica</dt>
              <dd>{detail.energy_class ?? "n/d"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Giorni sul mercato</dt>
              <dd>{detail.days_on_market}</dd>
            </div>
          </dl>
          <p className="mt-2 flex flex-wrap gap-2 text-xs">
            {Object.entries(detail.features)
              .filter(([, v]) => v)
              .map(([k]) => (
                <span
                  key={k}
                  className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800"
                >
                  {featureLabels[k] ?? k}
                </span>
              ))}
          </p>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">{detail.description}</p>
          <p className="mt-2 text-xs text-slate-500">
            Agenzia: {detail.agency_name ?? "n/d"} · pubblicato il{" "}
            {new Date(detail.published_at).toLocaleDateString("it-IT")} · ultimo aggiornamento{" "}
            {new Date(detail.last_seen_at).toLocaleDateString("it-IT")}
          </p>
        </div>

        <div className="card">
          <h2 className="font-semibold">Stima indicativa</h2>
          {detail.estimate ? (
            <>
              <p className="mt-2 text-xl font-semibold">
                {formatPrice(detail.estimate.range_low)} –{" "}
                {formatPrice(detail.estimate.range_high)}
              </p>
              <p className="text-sm text-slate-500">
                valore centrale {formatPrice(detail.estimate.estimated_value)} · confidenza{" "}
                {Math.round(detail.estimate.confidence * 100)}% ·{" "}
                {detail.estimate.n_comparables} comparabili
              </p>
              <p className="mt-2 text-xs text-slate-500">{detail.estimate.assumptions}</p>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-500">
              Comparabili insufficienti per una stima affidabile: nessun valore viene mostrato
              piuttosto che un numero non fondato.
            </p>
          )}
          {user && (
            <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-800">
              <button type="button" className="btn-secondary" onClick={requestValuation}>
                Salva valutazione ora
              </button>
              {valuationMessage && (
                <p className="mt-1 text-xs text-slate-500">{valuationMessage}</p>
              )}
              {valuations.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-slate-500">
                  {valuations.slice(0, 5).map((v) => (
                    <li key={v.id}>
                      {new Date(v.computed_at).toLocaleString("it-IT")}:{" "}
                      {formatPrice(v.estimated_value, v.currency)} ({formatPrice(v.range_low, v.currency)}–
                      {formatPrice(v.range_high, v.currency)})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="card" aria-label="Storico prezzi">
        <h2 className="mb-2 font-semibold">Storico prezzi</h2>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid stroke="rgba(148,163,184,0.25)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              width={64}
              domain={["auto", "auto"]}
              tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`}
            />
            <Tooltip formatter={(value) => [formatPrice(Number(value)), "Prezzo"]} />
            <Line type="stepAfter" dataKey="price" stroke="#2a7de1" strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section className="card" aria-label="Cronologia versioni">
        <h2 className="mb-2 font-semibold">Cronologia dell&apos;annuncio</h2>
        <ol className="space-y-2">
          {[...detail.versions].reverse().map((v) => (
            <li key={v.version_number} className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/50">
              <p className="font-medium">
                Versione {v.version_number} —{" "}
                {new Date(v.captured_at).toLocaleDateString("it-IT")}
              </p>
              {Object.keys(v.diff).length === 0 ? (
                <p className="text-xs text-slate-500">Prima rilevazione dell&apos;annuncio</p>
              ) : (
                <ul className="mt-1 space-y-0.5 text-xs text-slate-600 dark:text-slate-400">
                  {Object.entries(v.diff).map(([field, change]) => (
                    <li key={field}>
                      {diffLabels[field] ?? field}: {String(change.old ?? "n/d")} →{" "}
                      {String(change.new ?? "n/d")}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      </section>

      {detail.duplicate_listings.length > 0 && (
        <section className="card" aria-label="Altri annunci per questo immobile">
          <h2 className="mb-2 font-semibold">Altri annunci per questo immobile</h2>
          <p className="mb-2 text-xs text-slate-500">
            Stesso immobile fisico pubblicato da agenzie diverse (rilevato dal sistema di
            deduplicazione, non dichiarato dalle agenzie).
          </p>
          <ul className="space-y-2">
            {detail.duplicate_listings.map((d) => (
              <li key={d.listing_id} className="flex items-center justify-between text-sm">
                <Link
                  href={`/listings/${d.listing_id}`}
                  className="text-brand-600 hover:underline"
                >
                  {d.agency_name ?? "Agenzia sconosciuta"}
                </Link>
                <span className="text-slate-500">
                  {formatPrice(d.price, d.currency)} · {d.status} · confidenza corrispondenza{" "}
                  {Math.round(d.dedup_confidence * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {detail.comparables.length > 0 && (
        <section aria-label="Immobili comparabili">
          <h2 className="mb-2 font-semibold">Immobili comparabili</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {detail.comparables.map((c) => (
              <Link
                key={c.listing_id}
                href={`/listings/${c.listing_id}`}
                className="card block text-sm transition hover:border-brand-500"
              >
                <p className="font-medium">{c.title}</p>
                <p className="mt-1 text-slate-500">
                  {formatPrice(c.price, c.currency)} · {c.size_sqm} m² ·{" "}
                  {c.price_per_sqm.toLocaleString("it-IT")} €/m²
                </p>
                <p className="text-xs text-slate-500">
                  similarità {Math.round(c.similarity * 100)}%
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
