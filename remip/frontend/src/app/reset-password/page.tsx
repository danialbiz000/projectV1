"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, ApiError, type MessageResponse } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api<MessageResponse>("/api/v1/auth/reset-password", {
        method: "POST",
        body: { token, new_password: password },
        auth: false,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di connessione");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <div className="card mt-4 text-sm">
        <p>Link non valido: manca il token di reimpostazione.</p>
        <Link href="/forgot-password" className="mt-2 inline-block text-brand-600 hover:underline">
          Richiedi un nuovo link →
        </Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="card mt-4 text-sm">
        <p>Password aggiornata.</p>
        <Link href="/login" className="mt-2 inline-block text-brand-600 hover:underline">
          Vai al login →
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="card mt-4 space-y-4">
      <div>
        <label className="label" htmlFor="password">
          Nuova password (min 8 caratteri)
        </label>
        <input
          id="password"
          type="password"
          required
          minLength={8}
          className="input"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <button type="submit" className="btn-primary w-full" disabled={busy}>
        {busy ? "Salvataggio…" : "Reimposta password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="mx-auto max-w-sm pt-10">
      <h1 className="text-2xl font-bold">Reimposta password</h1>
      <Suspense fallback={<p className="mt-4 text-sm text-slate-500">Caricamento…</p>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
