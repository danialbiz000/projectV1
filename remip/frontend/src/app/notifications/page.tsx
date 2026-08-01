"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type NotificationDigest,
  type NotificationOut,
  type NotificationPreferenceOut,
} from "@/lib/api";
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
  status_change: "🔄",
  photos_change: "📷",
  listing_update: "✏️",
};

const typeLabels: Record<string, string> = {
  price_drop: "Prezzo ridotto",
  price_increase: "Prezzo aumentato",
  listing_removed: "Annuncio rimosso",
  listing_relisted: "Annuncio ripubblicato",
  possible_sale: "Possibile vendita",
  status_change: "Stato annuncio cambiato",
  photos_change: "Fotografie aggiornate",
  listing_update: "Annuncio aggiornato",
};

function PreferencesPanel() {
  const [prefs, setPrefs] = useState<NotificationPreferenceOut | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const reload = useCallback(() => {
    api<NotificationPreferenceOut>("/api/v1/notifications/preferences")
      .then(setPrefs)
      .catch(() => setPrefs(null));
  }, []);

  useEffect(reload, [reload]);

  const save = async (next: NotificationPreferenceOut) => {
    setPrefs(next);
    setSaving(true);
    setSaved(false);
    try {
      const updated = await api<NotificationPreferenceOut>("/api/v1/notifications/preferences", {
        method: "PUT",
        body: { frequency: next.frequency, muted_types: next.muted_types },
      });
      setPrefs(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const toggleMuted = (type: string) => {
    if (!prefs) return;
    const muted = prefs.muted_types.includes(type)
      ? prefs.muted_types.filter((t) => t !== type)
      : [...prefs.muted_types, type];
    void save({ ...prefs, muted_types: muted });
  };

  if (!prefs) return null;

  return (
    <details className="card" open>
      <summary className="cursor-pointer font-semibold">Preferenze notifiche</summary>
      <div className="mt-3 space-y-3">
        <div>
          <label className="label" htmlFor="frequency">
            Frequenza
          </label>
          <select
            id="frequency"
            className="input max-w-xs"
            value={prefs.frequency}
            onChange={(e) => void save({ ...prefs, frequency: e.target.value })}
          >
            <option value="instant">Immediata</option>
            <option value="daily_digest">Riepilogo giornaliero</option>
            <option value="weekly_digest">Riepilogo settimanale</option>
          </select>
        </div>
        <div>
          <p className="label">Tipi silenziati</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(typeLabels).map(([type, label]) => {
              const muted = prefs.muted_types.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={muted}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                    muted
                      ? "bg-slate-300 text-slate-700 line-through dark:bg-slate-700 dark:text-slate-300"
                      : "bg-slate-100 dark:bg-slate-800"
                  }`}
                  onClick={() => toggleMuted(type)}
                >
                  {typeIcons[type] ?? "🔔"} {label}
                </button>
              );
            })}
          </div>
        </div>
        <p className="text-xs text-slate-500">
          {saving ? "Salvataggio…" : saved ? "Preferenze salvate ✓" : ""}
        </p>
      </div>
    </details>
  );
}

export default function NotificationsPage() {
  const { user, loading } = useAuth();
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [digest, setDigest] = useState<NotificationDigest | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const reload = useCallback(() => {
    api<NotificationsResponse>(`/api/v1/notifications?unread_only=${unreadOnly}`)
      .then(setData)
      .catch(() => setData(null));
    api<NotificationDigest>("/api/v1/notifications/digest")
      .then(setDigest)
      .catch(() => setDigest(null));
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

      <PreferencesPanel />

      {digest && digest.unread_total > 0 && (
        <div className="card" aria-label="Riepilogo notifiche non lette">
          <h2 className="mb-2 text-sm font-semibold">
            In sintesi: {digest.unread_total} notifiche non lette
          </h2>
          <div className="flex flex-wrap gap-2">
            {digest.by_type.map((t) => (
              <span
                key={t.type}
                className="rounded-full bg-slate-100 px-2.5 py-1 text-xs dark:bg-slate-800"
              >
                {typeIcons[t.type] ?? "🔔"} {t.label}: {t.count}
              </span>
            ))}
          </div>
        </div>
      )}

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
