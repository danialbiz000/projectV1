"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, ApiError, type MessageResponse } from "@/lib/api";

function VerifyEmailStatus() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"checking" | "done" | "error">("checking");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Link non valido: manca il token di verifica.");
      return;
    }
    api<MessageResponse>("/api/v1/auth/verify-email/confirm", {
      method: "POST",
      body: { token },
      auth: false,
    })
      .then((response) => {
        setStatus("done");
        setMessage(response.detail);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : "Errore di connessione");
      });
  }, [token]);

  return (
    <div className="card mt-4 space-y-2 text-sm">
      {status === "checking" && <p>Verifica in corso…</p>}
      {status !== "checking" && <p>{message}</p>}
      {status !== "checking" && (
        <Link href="/dashboard" className="inline-block text-brand-600 hover:underline">
          Vai alla dashboard →
        </Link>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto max-w-sm pt-10">
      <h1 className="text-2xl font-bold">Verifica email</h1>
      <Suspense fallback={<p className="mt-4 text-sm text-slate-500">Caricamento…</p>}>
        <VerifyEmailStatus />
      </Suspense>
    </div>
  );
}
