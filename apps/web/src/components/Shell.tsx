"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { ROLE_LABEL, useAuth } from "@/lib/auth";

const NAV: { href: string; label: string; show?: (p: Record<string, boolean>) => boolean }[] = [
  { href: "/", label: "Overview" },
  { href: "/workspace", label: "Employee Workspace", show: (p) => p.workspace },
  { href: "/coordinator", label: "AI Coordinator", show: (p) => p.workspace },
  { href: "/meetings", label: "Meeting Intelligence", show: (p) => p.workspace },
  { href: "/projects", label: "Project Portfolio" },
  { href: "/risks", label: "Risk Intelligence" },
  { href: "/evidence", label: "Contribution Evidence" },
  { href: "/analysis", label: "Contextual Analysis", show: (p) => p.analysis },
  { href: "/validation", label: "Model Validation", show: (p) => p.validation },
  { href: "/flagship", label: "Flagship Study", show: (p) => p.flagship },
  { href: "/research", label: "Research Laboratory", show: (p) => p.research },
  { href: "/admin", label: "Administration & Privacy" },
];

export function Shell({ children }: { children: ReactNode }) {
  const { me, ready, logout } = useAuth();
  const path = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (ready && !me && path !== "/login") router.replace("/login");
  }, [ready, me, path, router]);

  if (path === "/login") return <>{children}</>;
  if (!ready || !me) return <div className="p-10 text-sm text-muted">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-60 shrink-0 border-r border-line bg-surface md:block">
      <aside className="sticky top-0 flex h-screen flex-col px-3 py-4">
        <Link href="/" className="mb-6 px-2">
          <div className="text-base font-semibold tracking-tight">MeritVector</div>
          <div className="text-[11px] text-muted">Workforce intelligence · v0.2</div>
        </Link>
        <nav className="flex flex-1 flex-col gap-0.5" aria-label="Main">
          {NAV.filter((n) => !n.show || n.show(me.permissions)).map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href}
                className={`rounded-md px-2 py-1.5 text-sm ${active ? "bg-accent/10 font-medium text-accent" : "text-muted hover:bg-bg hover:text-ink"}`}>
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-4 rounded-lg border border-line p-2 text-xs">
          <div className="font-medium">{me.display_name}</div>
          <div className="text-muted">{ROLE_LABEL[me.role]} · {me.tenant.name}</div>
          <button onClick={() => { logout(); router.replace("/login"); }} className="mt-2 text-accent hover:underline">
            Switch user
          </button>
        </div>
      </aside>
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-2 border-b border-line bg-surface px-4 py-2 text-xs md:px-8">
          <span className="rounded-full border border-warn/70 bg-warn/15 px-2 py-0.5 font-semibold uppercase tracking-wide">Synthetic data</span>
          <span className="text-muted">
            Every person, project and number is generated. Decision support only — no rankings, no automated employment decisions.
          </span>
          <span className="ml-auto text-muted">Synthetic clock: {me.tenant.as_of}</span>
          <nav className="flex w-full gap-3 overflow-x-auto md:hidden" aria-label="Main (mobile)">
            {NAV.filter((n) => !n.show || n.show(me.permissions)).map((n) => (
              <Link key={n.href} href={n.href} className="whitespace-nowrap text-accent">{n.label}</Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
