"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, ErrorState, Loading } from "@/components/ui";
import { ApiError, useApi } from "@/lib/api";
import { ROLE_LABEL, useAuth } from "@/lib/auth";

type Persona = { user_id: string; display_name: string; role: string; tenant_id: string; label: string; description: string };
type U = { user_id: string; display_name: string; role: string; tenant_id: string };

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const { data, error, loading } = useApi<Persona[]>("/auth/demo-personas");
  const [q, setQ] = useState("");
  const search = useApi<U[]>(q.length >= 2 ? `/auth/demo-users?q=${encodeURIComponent(q)}` : null);
  const [err, setErr] = useState<ApiError | null>(null);

  const go = async (id: string) => {
    try {
      await login(id);
      router.replace("/");
    } catch (e) {
      setErr(e as ApiError);
    }
  };

  const tenants = Array.from(new Set((data ?? []).map((p) => p.tenant_id)));
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">MeritVector</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Evidence-based workforce intelligence. This demonstration runs entirely on a <strong>synthetic</strong> organisation.
        Demo sign-in has no passwords and must be replaced by single sign-on before any real use.
      </p>
      {loading && <Loading />}
      <ErrorState error={error ?? err} />
      {tenants.map((t) => (
        <section key={t} className="mt-8">
          <h2 className="mb-1 text-sm font-semibold">{t === "synthetic-pmo" ? "Synthetic PMO — assessment approved" : "Synthetic sandbox — assessment not approved"}</h2>
          <p className="mb-3 text-xs text-muted">
            {t === "synthetic-pmo"
              ? "300 synthetic programme, project and technical project managers; 24 months of history."
              : "A second tenant used to demonstrate tenant separation and the governance gate."}
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(data ?? []).filter((p) => p.tenant_id === t).map((p) => (
              <button key={p.user_id} onClick={() => go(p.user_id)}
                className="rounded-xl border border-line bg-surface p-4 text-left shadow-sm transition hover:border-accent">
                <Badge tone="accent">{p.label}</Badge>
                <div className="mt-2 text-sm font-medium">{p.display_name}</div>
                <div className="mt-1 text-xs text-muted">{p.description}</div>
              </button>
            ))}
          </div>
        </section>
      ))}
      <section className="mt-10">
        <label className="text-sm font-semibold" htmlFor="user-search">Sign in as any synthetic user</label>
        <input id="user-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or ID"
          className="mt-2 w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm" />
        <div className="mt-2 divide-y divide-line rounded-lg border border-line bg-surface">
          {(search.data ?? []).map((u) => (
            <button key={u.user_id} onClick={() => go(u.user_id)} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-bg">
              <span>{u.display_name}</span>
              <span className="text-xs text-muted">{ROLE_LABEL[u.role]} · {u.tenant_id}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
