import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "REMIP — Real Estate Market Intelligence",
  description:
    "Analisi del mercato immobiliare: prezzi di zona, storico annunci, watchlist e previsioni. Dati demo.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it" suppressHydrationWarning>
      <body>
        <AuthProvider>
          <Navbar />
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <footer className="mx-auto max-w-6xl px-4 py-8 text-xs text-slate-500">
            REMIP — piattaforma dimostrativa. Tutti i dati sono sintetici e ogni metrica riporta
            fonte, periodo e qualità. Le stime e le previsioni non costituiscono consulenza
            finanziaria.
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
