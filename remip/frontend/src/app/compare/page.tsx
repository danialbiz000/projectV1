"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, formatPct, formatPrice, type ListingCompareRow } from "@/lib/api";
import { getCompareIds, removeFromCompare, clearCompare, MAX_COMPARE } from "@/lib/compare";

function fmt(row: ListingCompareRow, key: keyof ListingCompareRow): string {
  const value = row[key];
  if (value === null || value === undefined) return "n/d";
  if (key === "price_per_sqm" && typeof value === "number") {
    return `${value.toLocaleString("it-IT")} €/m²`;
  }
  if (key === "size_sqm" && typeof value === "number") return `${value} m²`;
  return String(value);
}

const rowLabels: { key: keyof ListingCompareRow; label: string }[] = [
  { key: "area_name", label: "Zona" },
  { key: "property_type", label: "Tipologia" },
  { key: "size_sqm", label: "Superficie" },
  { key: "rooms", label: "Locali" },
  { key: "price_per_sqm", label: "€/m²" },
  { key: "days_on_market", label: "Giorni sul mercato" },
  { key: "energy_class", label: "Classe energetica" },
];

export default function ComparePage() {
  const [ids, setIds] = useState<string[]>([]);
  const [rows, setRows] = useState<ListingCompareRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback((currentIds: string[]) => {
    if (currentIds.length < 2) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError(null);
    api<ListingCompareRow[]>("/api/v1/listings/compare", {
      method: "POST",
      body: { listing_ids: currentIds },
      auth: false,
    })
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Errore nel confronto"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const current = getCompareIds();
    setIds(current);
    reload(current);
  }, [reload]);

  const remove = (id: string) => {
    const next = removeFromCompare(id);
    setIds(next);
    reload(next);
  };

  const clear = () => {
    clearCompare();
    setIds([]);
    setRows([]);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Confronta annunci</h1>
          <p className="text-sm text-slate-500">
            Fino a {MAX_COMPARE} annunci selezionati dalla ricerca (“+ Confronta”).
          </p>
        </div>
        {ids.length > 0 && (
          <button type="button" className="btn-secondary" onClick={clear}>
            Svuota confronto
          </button>
        )}
      </div>

      {ids.length === 0 && (
        <div className="card text-center text-sm text-slate-500">
          Nessun annuncio selezionato.{" "}
          <Link href="/listings" className="text-brand-600 hover:underline">
            Cerca immobili
          </Link>{" "}
          e usa “+ Confronta” su almeno due annunci.
        </div>
      )}
      {ids.length === 1 && (
        <div className="card text-center text-sm text-slate-500">
          Serve almeno un secondo annuncio per confrontare.
        </div>
      )}
      {loading && <p className="text-sm text-slate-500">Caricamento…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-separate border-spacing-y-2 text-sm">
            <thead>
              <tr>
                <th className="text-left text-xs font-medium text-slate-500">Caratteristica</th>
                {rows.map((r) => (
                  <th key={r.id} className="card px-3 py-2 text-left align-top">
                    <Link
                      href={`/listings/${r.id}`}
                      className="font-semibold text-brand-600 hover:underline"
                    >
                      {r.title}
                    </Link>
                    <p className="mt-1 text-lg font-bold">
                      {formatPrice(r.current_price, r.currency)}
                    </p>
                    <button
                      type="button"
                      className="mt-1 text-xs text-slate-500 hover:underline"
                      onClick={() => remove(r.id)}
                    >
                      Rimuovi
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowLabels.map(({ key, label }) => (
                <tr key={key}>
                  <td className="text-xs font-medium text-slate-500">{label}</td>
                  {rows.map((r) => (
                    <td key={r.id} className="px-3 py-1">
                      {fmt(r, key)}
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <td className="text-xs font-medium text-slate-500">Scostamento vs zona</td>
                {rows.map((r) => (
                  <td key={r.id} className="px-3 py-1">
                    {formatPct(r.deviation_from_area_pct)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="text-xs font-medium text-slate-500">Stima (intervallo)</td>
                {rows.map((r) => (
                  <td key={r.id} className="px-3 py-1">
                    {r.estimate
                      ? `${formatPrice(r.estimate.range_low, r.currency)} – ${formatPrice(
                          r.estimate.range_high,
                          r.currency,
                        )}`
                      : "comparabili insufficienti"}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
