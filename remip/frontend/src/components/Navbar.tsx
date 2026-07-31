"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { DemoBadge } from "@/components/DemoBadge";
import { ThemeToggle } from "@/components/ThemeToggle";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/listings", label: "Ricerca" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/notifications", label: "Notifiche" },
];

export function Navbar() {
  const { user, logout } = useAuth();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!user) return;
    api<{ unread: number }>("/api/v1/notifications?limit=1")
      .then((data) => setUnread(data.unread))
      .catch(() => setUnread(0));
  }, [user]);

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      <nav
        className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3"
        aria-label="Navigazione principale"
      >
        <Link href="/" className="text-lg font-bold text-brand-600 dark:text-brand-500">
          REMIP
        </Link>
        <DemoBadge />
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {user ? (
            <>
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-lg px-2.5 py-1.5 text-sm font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  {link.label}
                  {link.href === "/notifications" && unread > 0 && (
                    <span className="ml-1 rounded-full bg-brand-600 px-1.5 text-xs text-white">
                      {unread}
                    </span>
                  )}
                </Link>
              ))}
              <span className="hidden text-xs text-slate-500 sm:inline">{user.email}</span>
              <button type="button" onClick={logout} className="btn-secondary">
                Esci
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-secondary">
                Accedi
              </Link>
              <Link href="/register" className="btn-primary">
                Registrati
              </Link>
            </>
          )}
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
