"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Card, ErrorState, Loading, PageHeader, Table, Tabs } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { AnyRec } from "@/lib/types";

type Scope = "past" | "upcoming";

export default function MeetingsPage() {
  const [scope, setScope] = useState<Scope>("past");
  const { data, error, loading } = useApi<AnyRec[]>(`/meetings?scope=${scope}`);
  return (
    <div>
      <PageHeader title="Meeting Intelligence" subtitle="Summaries, decisions, actions, risks and dependencies extracted from meetings you attended. Transcripts are visible only to attendees and are never used for performance assessment." />
      <Tabs<Scope> value={scope} onChange={setScope} tabs={[{ id: "past", label: "Recent meetings" }, { id: "upcoming", label: "Upcoming" }]} />
      {loading ? <Loading /> : error ? <ErrorState error={error} /> : (
        <Card>
          <Table head={["When", "Meeting", "Summary", "Items"]} rows={(data ?? []).slice().reverse().map((m) => [
            m.scheduled_at.replace("T", " ").slice(0, 16),
            <Link key="l" href={`/meetings/${encodeURIComponent(m.id)}`} className="text-accent hover:underline">{m.title}</Link>,
            <span key="s" className="text-xs text-muted">{m.insight?.summary ?? (m.has_transcript ? "Not processed yet" : "No transcript (calendar entry)")}</span>,
            m.insight ? <span key="b" className="flex flex-wrap gap-1"><Badge>{m.insight.actions.length} actions</Badge><Badge>{m.insight.decisions.length} decisions</Badge><Badge>{m.insight.risks.length} risks</Badge></span> : null,
          ])} empty="No meetings." />
        </Card>
      )}
    </div>
  );
}
