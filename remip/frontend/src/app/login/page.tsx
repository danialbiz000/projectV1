"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type OAuthAuthorizeResponse, type OAuthProvidersResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const providerLabels: Record<string, string> = { google: "Google" };

function OAuthButtons() {
  const [providers, setProviders] = useState<string[]>([]);

  useEffect(() => {
    api<OAuthProvidersResponse>("/api/v1/auth/oauth/providers", { auth: false })
      .then((r) => setProviders(r.providers))
      .catch(() => setProviders([]));
  }, []);

  if (providers.length === 0) return null;

  const start = async (provider: string) => {
    const { authorize_url } = await api<OAuthAuthorizeResponse>(
      `/api/v1/auth/oauth/${provider}/authorize`,
      { auth: false },
    );
    window.location.href = authorize_url;
  };

  return (
    <div className="space-y-2">
      {providers.map((provider) => (
        <button
          key={provider}
          type="button"
          className="btn-secondary w-full"
          onClick={() => start(provider)}
        >
          Continua con {providerLabels[provider] ?? provider}
        </button>
      ))}
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        oppure
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
      </div>
    </div>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(email, password);
      router.push(user.onboarding_completed ? "/dashboard" : "/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di connessione");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm pt-10">
      <h1 className="text-2xl font-bold">Accedi</h1>
      <p className="mt-1 text-sm text-slate-500">
        Demo: <code>demo@example.com</code> / <code>demo1234</code>
      </p>
      <div className="card mt-4 space-y-4">
        <OAuthButtons />
        <form onSubmit={submit} className="space-y-4">
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
          <div>
            <label className="label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {error}
            </p>
          )}
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? "Accesso…" : "Accedi"}
          </button>
          <p className="text-center text-sm">
            <Link href="/forgot-password" className="text-brand-600 hover:underline">
              Password dimenticata?
            </Link>
          </p>
          <p className="text-center text-sm text-slate-500">
            Non hai un account?{" "}
            <Link href="/register" className="text-brand-600 hover:underline">
              Registrati
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
