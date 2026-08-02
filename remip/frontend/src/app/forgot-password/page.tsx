"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type MessageResponse } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<MessageResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await api<MessageResponse>("/api/v1/auth/forgot-password", {
        method: "POST",
        body: { email },
        auth: false,
      });
      setResult(response);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm pt-10">
      <h1 className="text-2xl font-bold">Password dimenticata</h1>
      {!result ? (
        <form onSubmit={submit} className="card mt-4 space-y-4">
          <div>
            <label className="label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? "Invio…" : "Invia istruzioni"}
          </button>
          <p className="text-center text-sm text-slate-500">
            <Link href="/login" className="text-brand-600 hover:underline">
              ← Torna al login
            </Link>
          </p>
        </form>
      ) : (
        <div className="card mt-4 space-y-3 text-sm">
          <p>{result.detail}</p>
          {result.dev_token && (
            <div className="rounded-lg bg-amber-100 p-3 text-xs text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">
              <p className="font-medium">
                Modalità demo: nessuna email reale è stata inviata (nessun SMTP configurato — vedi
                docs/DEPLOYMENT.md).
              </p>
              <Link
                href={`/reset-password?token=${result.dev_token}`}
                className="mt-1 inline-block underline"
              >
                Continua alla reimpostazione password →
              </Link>
            </div>
          )}
          <Link href="/login" className="text-brand-600 hover:underline">
            ← Torna al login
          </Link>
        </div>
      )}
    </div>
  );
}
