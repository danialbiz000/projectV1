"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, formatPrice, type WatchlistOut } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function WatchlistPage() {
  const { user, loading } = useAuth();
  const [watchlists, setWatchlists] = useState<WatchlistOut[]>([]);

  const reload = useCallback(() => {
    api<WatchlistOut[]>("/api/v1/watchlists").then(setWatchlists).catch(() => setWatchlists([]));
  }, []);

  useEffect(() => {
    if (user) reload();
  }, [user, reload]);

  const removeItem = async (watchlistId: string, itemId: string) => {
    await api(`/api/v1/watchlists/${watchlistId}/items/${itemId}`, { method: "DELETE" });
    reload();
  };

  if (loading) return <p className="text-sm text-slate-500">Caricamento…</p>;
  if (!user)
    return (
      <div className="pt-10 text-center">
        <p>Accedi per vedere la tua watchlist.</p>
        <Link href="/login" className="btn-primary mt-4">
          Accedi
        </Link>
      </div>
    );

  const totalItems = watchlists.reduce((n, w) => n + w.items.length, 0);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Watchlist</h1>
      {totalItems === 0 && (
        <div className="card text-center">
          <p className="text-sm text-slate-500">
            Nessun elemento osservato. Apri un annuncio e usa “Aggiungi alla watchlist”.
          </p>
          <Link href="/listings" className="btn-primary mt-3">
            Cerca immobili
          </Link>
        </div>
      )}
      {watchlists.map((watchlist) =>
        watchlist.items.length === 0 ? null : (
          <section key={watchlist.id} className="card" aria-label={watchlist.name}>
            <h2 className="font-semibold">{watchlist.name}</h2>
            <ul className="mt-2 divide-y divide-slate-200 dark:divide-slate-800">
              {watchlist.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div>
                    {item.kind === "listing" && item.listing_id ? (
                      <Link
                        href={`/listings/${item.listing_id}`}
                        className="font-medium text-brand-600 hover:underline"
                      >
                        Annuncio osservato
                      </Link>
                    ) : (
                      <span className="font-medium">Zona osservata</span>
                    )}
                    <p className="text-xs text-slate-500">
                      dal {new Date(item.created_at).toLocaleDateString("it-IT")}
                      {item.initial_price !== null &&
                        ` · prezzo iniziale ${formatPrice(item.initial_price)}`}
                      {item.notify ? " · notifiche attive" : " · notifiche disattivate"}
                    </p>
                    {item.note && <p className="text-xs text-slate-500">Nota: {item.note}</p>}
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => removeItem(watchlist.id, item.id)}
                    aria-label="Rimuovi dalla watchlist"
                  >
                    Rimuovi
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ),
      )}
    </div>
  );
}
