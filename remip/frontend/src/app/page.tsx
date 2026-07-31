import Link from "next/link";

const features = [
  {
    title: "Analisi di zona",
    body: "Prezzi medi e mediani, €/m², tempi di vendita, rendimenti e variazioni su più periodi per città e quartieri.",
  },
  {
    title: "Storico e versioni degli annunci",
    body: "Ogni variazione di prezzo, stato o descrizione viene tracciata come versione con differenze puntuali.",
  },
  {
    title: "Watchlist e notifiche",
    body: "Osserva annunci e zone: ribassi, rimozioni e ripubblicazioni generano notifiche immediate e senza duplicati.",
  },
  {
    title: "Previsioni trasparenti",
    body: "Scenari negativo/base/positivo con intervalli, driver e limitazioni dichiarate. Mai un numero certo.",
  },
];

export default function LandingPage() {
  return (
    <div className="space-y-12">
      <section className="pt-8 text-center sm:pt-16">
        <p className="mb-3 text-sm font-medium uppercase tracking-wide text-brand-600">
          Real Estate Market Intelligence Platform
        </p>
        <h1 className="mx-auto max-w-2xl text-4xl font-bold sm:text-5xl">
          Capisci il mercato immobiliare prima di muoverti
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-slate-600 dark:text-slate-400">
          Dashboard di zona, storico degli annunci, comparabili e previsioni con scenari — con
          fonti, qualità dei dati e limitazioni sempre visibili.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/register" className="btn-primary">
            Inizia gratis
          </Link>
          <Link href="/dashboard" className="btn-secondary">
            Esplora la demo
          </Link>
        </div>
      </section>
      <section className="grid gap-4 sm:grid-cols-2">
        {features.map((f) => (
          <div key={f.title} className="card">
            <h2 className="font-semibold">{f.title}</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{f.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
