import type { DataContext } from "@/lib/api";

/** Mandatory transparency block: source, period, observations, quality, limits. */
export function DataContextFooter({ context }: { context: DataContext }) {
  return (
    <details className="mt-3 rounded-lg bg-slate-100 p-3 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-400">
      <summary className="cursor-pointer font-medium">
        Fonte: {context.sources.join(", ") || "n/d"} · Periodo: {context.period ?? "n/d"} ·{" "}
        {context.observations ?? 0} osservazioni
        {context.is_demo_data && " · ⚠ dati demo"}
      </summary>
      <dl className="mt-2 space-y-1">
        {context.methodology && (
          <div>
            <dt className="inline font-medium">Metodologia: </dt>
            <dd className="inline">{context.methodology}</dd>
          </div>
        )}
        {context.quality !== null && (
          <div>
            <dt className="inline font-medium">Qualità del dato: </dt>
            <dd className="inline">{Math.round((context.quality ?? 0) * 100)}%</dd>
          </div>
        )}
        {context.updated_at && (
          <div>
            <dt className="inline font-medium">Ultimo aggiornamento: </dt>
            <dd className="inline">{new Date(context.updated_at).toLocaleString("it-IT")}</dd>
          </div>
        )}
        {context.limitations && (
          <div>
            <dt className="inline font-medium">Limitazioni: </dt>
            <dd className="inline">{context.limitations}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}
