"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, type DataExport, type MessageResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function VerificationStatus() {
  const { user, refresh } = useAuth();
  const [result, setResult] = useState<MessageResponse | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  const resend = async () => {
    setBusy(true);
    try {
      const response = await api<MessageResponse>("/api/v1/auth/verify-email/request", {
        method: "POST",
      });
      setResult(response);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card" aria-label="Verifica email">
      <h2 className="font-semibold">Email</h2>
      <p className="mt-1 text-sm">
        {user.email}{" "}
        {user.email_verified ? (
          <span className="ml-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            verificata
          </span>
        ) : (
          <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
            non verificata
          </span>
        )}
      </p>
      {!user.email_verified && (
        <div className="mt-2">
          <button type="button" className="btn-secondary" disabled={busy} onClick={resend}>
            {busy ? "Invio…" : "Invia email di verifica"}
          </button>
          {result && <p className="mt-2 text-xs text-slate-500">{result.detail}</p>}
          {result?.dev_token && (
            <div className="mt-2 rounded-lg bg-amber-100 p-3 text-xs text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">
              <p className="font-medium">Modalità demo: nessuna email reale è stata inviata.</p>
              <Link
                href={`/verify-email?token=${result.dev_token}`}
                className="mt-1 inline-block underline"
                onClick={() => void refresh()}
              >
                Verifica ora →
              </Link>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function DataExportSection() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api<DataExport>("/api/v1/users/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `remip-dati-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di connessione");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card" aria-label="Esporta i tuoi dati">
      <h2 className="font-semibold">Esporta i tuoi dati</h2>
      <p className="mt-1 text-sm text-slate-500">
        Scarica un file JSON con profilo, watchlist, notifiche e preferenze (diritto alla
        portabilità dei dati, GDPR art. 20).
      </p>
      <button type="button" className="btn-secondary mt-2" disabled={busy} onClick={download}>
        {busy ? "Preparazione…" : "Scarica i miei dati (.json)"}
      </button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </section>
  );
}

function DeleteAccountSection() {
  const { logout } = useAuth();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteAccount = async () => {
    setBusy(true);
    setError(null);
    try {
      await api<MessageResponse>("/api/v1/users/me", { method: "DELETE" });
      logout();
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di connessione");
      setBusy(false);
    }
  };

  return (
    <section className="card border-red-200 dark:border-red-900/50" aria-label="Elimina account">
      <h2 className="font-semibold text-red-700 dark:text-red-400">Elimina account</h2>
      <p className="mt-1 text-sm text-slate-500">
        Rimuove watchlist, notifiche e preferenze; anonimizza il profilo (diritto alla
        cancellazione, GDPR art. 17). Azione irreversibile.
      </p>
      {!confirming ? (
        <button
          type="button"
          className="btn-secondary mt-2 border-red-300 text-red-700 dark:border-red-900 dark:text-red-400"
          onClick={() => setConfirming(true)}
        >
          Elimina account
        </button>
      ) : (
        <div className="mt-2 space-y-2">
          <p className="text-sm font-medium">Confermi l&apos;eliminazione definitiva?</p>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              disabled={busy}
              onClick={deleteAccount}
            >
              {busy ? "Eliminazione…" : "Sì, elimina definitivamente"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Annulla
            </button>
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </section>
  );
}

export default function AccountPage() {
  const { user, loading } = useAuth();

  if (loading) return <p className="text-sm text-slate-500">Caricamento…</p>;
  if (!user)
    return (
      <div className="pt-10 text-center">
        <p>Accedi per gestire il tuo account.</p>
        <Link href="/login" className="btn-primary mt-4">
          Accedi
        </Link>
      </div>
    );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Il tuo account</h1>
      <VerificationStatus />
      <DataExportSection />
      <DeleteAccountSection />
    </div>
  );
}
