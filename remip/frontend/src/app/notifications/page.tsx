"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type NotificationOut } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface NotificationsResponse {
  items: NotificationOut[];
  total: number;
  unread: number;
}

const typeIcons: Record<string, string> = {
  price_drop: "📉",
  price_increase: "📈",
  listing_removed: "🚫",
  listing_relisted: "🔁",
  possible_sale: "🤝",
  photos_change: "📷",
};

export default function NotificationsPage() {
  const { user, loading } = useAuth();
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const reload = useCallback(() => {
    api<NotificationsResponse>(`/api/v1/notifications?unread_only=${unreadOnly}`)
      .then(setData)
      .catch(() => setData(null));
  }, [unreadOnly]);

  useEffect(() => {
    if (user) reload();
  }, [user, reload]);

  const markRead = async (id: string) => {
    await api(`/api/v1/notifications/${id}/read`, { method: "POST" });
    reload();
  };

  const markAllRead = async () => {
    await api("/api/v1/notifications/read-all", { method: "POST" });
    reload();
  };

  if (loading) return <p className="text-sm text-slate-500">Caricamento…</p>;
  if (!user)
    return (
      <div className="pt-10 text-center">
        <p>Accedi per vedere le notifiche.</p>
        <Link href="/login" className="btn-primary mt-4">
          Accedi
        </Link>
      </div>
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">
          Centro notifiche
          {data && data.unread > 0 && (
            <span className="ml-2 rounded-full bg-brand-600 px-2 py-0.5 text-sm text-white">
              {data.unread} non lette
            </span>
          )}
        </h1>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setUnreadOnly((v) => !v)}
            aria-pressed={unreadOnly}
          >
            {unreadOnly ? "Mostra tutte" : "Solo non lette"}
          </button>
          <button type="button" className="btn-secondary" onClick={markAllRead}>
            Segna tutte come lette
          </button>
        </div>
      </div>

      {data && data.items.length === 0 && (
        <div className="card text-center text-sm text-slate-500">
          Nessuna notifica. Aggiungi annunci alla watchlist: le variazioni simulate genereranno
          notifiche qui.
        </div>
      )}

      <ul className="space-y-2">
        {data?.items.map((n) => (
          <li
            key={n.id}
            className={`card flex items-start justify-between gap-3 ${
              n.is_read ? "opacity-70" : "border-brand-500/50"
            }`}
          >
            <div>
              <p className="font-medium">
                <span aria-hidden className="mr-1">
                  {typeIcons[n.type] ?? "🔔"}
                </span>
                {n.title}
                {!n.is_read && (
                  <span className="ml-2 rounded-full bg-brand-100 px-2 text-xs text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
                    nuova
                  </span>
                )}
              </p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{n.body}</p>
              <p className="mt-1 text-xs text-slate-500">
                {new Date(n.created_at).toLocaleString("it-IT")}
                {n.payload.listing_id && (
                  <>
                    {" · "}
                    <Link
                      href={`/listings/${n.payload.listing_id}`}
                      className="text-brand-600 hover:underline"
                    >
                      vai all&apos;annuncio
                    </Link>
                  </>
                )}
              </p>
            </div>
            {!n.is_read && (
              <button type="button" className="btn-secondary" onClick={() => markRead(n.id)}>
                Letta
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
