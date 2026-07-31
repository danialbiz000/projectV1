"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const goals = [
  { value: "buy", label: "Comprare casa", icon: "🏠" },
  { value: "sell", label: "Vendere casa", icon: "🏷️" },
  { value: "rent", label: "Affittare", icon: "🔑" },
  { value: "invest", label: "Investire", icon: "📈" },
  { value: "monitor", label: "Monitorare una zona", icon: "🔎" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [goal, setGoal] = useState("buy");
  const [busy, setBusy] = useState(false);

  const complete = async () => {
    setBusy(true);
    try {
      await api("/api/v1/auth/onboarding", {
        method: "POST",
        body: { goal, preferred_country: "IT" },
      });
      await refresh();
      router.push("/dashboard");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg pt-10">
      <h1 className="text-2xl font-bold">Benvenuto 👋</h1>
      <p className="mt-1 text-sm text-slate-500">
        Qual è il tuo obiettivo principale? Personalizzeremo la dashboard di conseguenza.
      </p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Obiettivo">
        {goals.map((g) => (
          <button
            key={g.value}
            type="button"
            role="radio"
            aria-checked={goal === g.value}
            onClick={() => setGoal(g.value)}
            className={`card flex items-center gap-3 text-left transition ${
              goal === g.value ? "ring-2 ring-brand-500" : "hover:border-brand-500"
            }`}
          >
            <span className="text-2xl" aria-hidden>
              {g.icon}
            </span>
            <span className="font-medium">{g.label}</span>
          </button>
        ))}
      </div>
      <button type="button" onClick={complete} disabled={busy} className="btn-primary mt-6 w-full">
        {busy ? "Salvataggio…" : "Continua"}
      </button>
    </div>
  );
}
