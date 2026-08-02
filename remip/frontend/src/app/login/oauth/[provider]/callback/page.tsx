"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, ApiError, type TokenResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function OAuthCallbackHandler() {
  const params = useParams<{ provider: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { loginWithToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const provider = params?.provider;
    if (!code || !provider) {
      setError("Risposta del provider incompleta (manca il parametro 'code').");
      return;
    }
    api<TokenResponse>(
      `/api/v1/auth/oauth/${provider}/callback?code=${encodeURIComponent(code)}`,
      { auth: false },
    )
      .then(async ({ access_token }) => {
        const user = await loginWithToken(access_token);
        router.push(user.onboarding_completed ? "/dashboard" : "/onboarding");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Errore di accesso"));
  }, [searchParams, params, router, loginWithToken]);

  if (error) {
    return (
      <div className="card mt-4 space-y-2 text-sm">
        <p role="alert" className="text-red-600 dark:text-red-400">
          {error}
        </p>
        <Link href="/login" className="inline-block text-brand-600 hover:underline">
          ← Torna al login
        </Link>
      </div>
    );
  }
  return <p className="mt-4 text-sm text-slate-500">Accesso in corso…</p>;
}

export default function OAuthCallbackPage() {
  return (
    <div className="mx-auto max-w-sm pt-10">
      <h1 className="text-2xl font-bold">Accesso</h1>
      <Suspense fallback={<p className="mt-4 text-sm text-slate-500">Caricamento…</p>}>
        <OAuthCallbackHandler />
      </Suspense>
    </div>
  );
}
