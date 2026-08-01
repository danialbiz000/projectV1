"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type AdminStats,
  type AdminUserRow,
  type DataSource,
  type IngestionJob,
  type Paginated,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function StatsSection() {
  const [stats, setStats] = useState<AdminStats | null>(null);

  useEffect(() => {
    api<AdminStats>("/api/v1/admin/stats")
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  if (!stats) return null;

  return (
    <section className="card" aria-label="Statistiche piattaforma">
      <h2 className="mb-2 font-semibold">Statistiche</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div>
          <p className="text-xs text-slate-500">Utenti</p>
          <p className="text-lg font-semibold">{stats.users}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Aree</p>
          <p className="text-lg font-semibold">{stats.areas}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Annunci</p>
          <p className="text-lg font-semibold">{stats.listings}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Versioni annunci</p>
          <p className="text-lg font-semibold">{stats.listing_versions}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Notifiche</p>
          <p className="text-lg font-semibold">{stats.notifications}</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Annunci per stato:{" "}
        {Object.entries(stats.listings_by_status)
          .map(([status, count]) => `${status}: ${count}`)
          .join(" · ")}
      </p>
    </section>
  );
}

function UsersSection() {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const reload = useCallback(() => {
    api<Paginated<AdminUserRow>>("/api/v1/admin/users?limit=100")
      .then((r) => {
        setUsers(r.items);
        setTotal(r.total);
      })
      .catch(() => setUsers([]));
  }, []);

  useEffect(reload, [reload]);

  const setActive = async (user: AdminUserRow, active: boolean) => {
    setMessage(null);
    try {
      await api(`/api/v1/admin/users/${user.id}/${active ? "reactivate" : "deactivate"}`, {
        method: "POST",
      });
      reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Errore");
    }
  };

  return (
    <section className="card" aria-label="Utenti">
      <h2 className="mb-2 font-semibold">Utenti ({total})</h2>
      {message && <p className="mb-2 text-sm text-red-600">{message}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="py-1">Email</th>
              <th className="py-1">Ruolo</th>
              <th className="py-1">Stato</th>
              <th className="py-1">Registrato il</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="py-1.5">{u.email}</td>
                <td className="py-1.5">{u.role}</td>
                <td className="py-1.5">
                  <span
                    className={
                      u.is_active
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-red-700 dark:text-red-400"
                    }
                  >
                    {u.is_active ? "attivo" : "disattivato"}
                  </span>
                </td>
                <td className="py-1.5 text-xs text-slate-500">
                  {new Date(u.created_at).toLocaleDateString("it-IT")}
                </td>
                <td className="py-1.5 text-right">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setActive(u, !u.is_active)}
                  >
                    {u.is_active ? "Disattiva" : "Riattiva"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SourcesSection() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  const reload = useCallback(() => {
    api<DataSource[]>("/api/v1/sources", { auth: false })
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  useEffect(reload, [reload]);

  const toggle = async (source: DataSource) => {
    setMessage(null);
    try {
      await api(`/api/v1/admin/sources/${source.code}/toggle?enabled=${!source.enabled}`, {
        method: "POST",
      });
      reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Errore");
    }
  };

  const runIngestion = async (source: DataSource) => {
    setMessage(null);
    setRunning(source.code);
    try {
      const result = await api<{ mode: string; status?: string; job_id?: string }>(
        `/api/v1/admin/ingestion/run/${source.code}`,
        { method: "POST" },
      );
      setMessage(
        result.mode === "queued"
          ? `${source.code}: job messo in coda`
          : `${source.code}: ${result.status}`,
      );
      reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Errore");
    } finally {
      setRunning(null);
    }
  };

  return (
    <section className="card" aria-label="Fonti dati">
      <h2 className="mb-2 font-semibold">Fonti dati</h2>
      {message && <p className="mb-2 text-sm text-slate-500">{message}</p>}
      <ul className="space-y-2">
        {sources.map((s) => (
          <li
            key={s.code}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 p-2.5 text-sm dark:bg-slate-800/50"
          >
            <div>
              <p className="font-medium">
                {s.name} <span className="text-xs text-slate-500">({s.code})</span>
              </p>
              <p className="text-xs text-slate-500">
                {s.kind} · {s.is_demo ? "dati demo" : "dati live"} ·{" "}
                {s.tos_compliant ? "ToS conforme" : "⚠ non conforme (non attivabile)"}
                {s.last_ingested_at &&
                  ` · ultima ingestion ${new Date(s.last_ingested_at).toLocaleString("it-IT")}`}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={running === s.code}
                onClick={() => runIngestion(s)}
              >
                {running === s.code ? "In corso…" : "Esegui ora"}
              </button>
              <button
                type="button"
                className={`rounded-lg px-3 py-2 text-sm font-medium ${
                  s.enabled
                    ? "border border-slate-300 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
                    : "bg-brand-600 text-white hover:bg-brand-700"
                }`}
                disabled={!s.enabled && !s.tos_compliant}
                onClick={() => toggle(s)}
              >
                {s.enabled ? "Disattiva" : "Attiva"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

const jobStatusTone: Record<string, string> = {
  success: "text-emerald-700 dark:text-emerald-400",
  failed: "text-red-700 dark:text-red-400",
  running: "text-amber-700 dark:text-amber-400",
};

function IngestionJobsSection() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);

  useEffect(() => {
    api<IngestionJob[]>("/api/v1/admin/ingestion/jobs?limit=20")
      .then(setJobs)
      .catch(() => setJobs([]));
  }, []);

  return (
    <section className="card" aria-label="Job di ingestion">
      <h2 className="mb-2 font-semibold">Ultimi job di ingestion</h2>
      {jobs.length === 0 && <p className="text-sm text-slate-500">Nessun job registrato.</p>}
      <ul className="space-y-1.5">
        {jobs.map((j) => (
          <li key={j.id} className="text-sm">
            <span className={`font-medium ${jobStatusTone[j.status] ?? ""}`}>{j.status}</span>{" "}
            {j.provider_code} ({j.trigger}) — {new Date(j.started_at).toLocaleString("it-IT")}
            {j.records_created !== null && ` · +${j.records_created} creati`}
            {j.error_message && (
              <span className="block text-xs text-red-600">{j.error_message}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function AdminPage() {
  const { user, loading } = useAuth();

  if (loading) return <p className="text-sm text-slate-500">Caricamento…</p>;
  if (!user)
    return (
      <div className="pt-10 text-center">
        <p>Accedi per vedere il pannello amministratore.</p>
        <Link href="/login" className="btn-primary mt-4">
          Accedi
        </Link>
      </div>
    );
  if (user.role !== "admin")
    return (
      <div className="pt-10 text-center">
        <p>Accesso riservato agli amministratori.</p>
      </div>
    );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Pannello amministratore</h1>
      <StatsSection />
      <UsersSection />
      <SourcesSection />
      <IngestionJobsSection />
    </div>
  );
}
