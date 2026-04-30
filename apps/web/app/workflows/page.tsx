import Link from "next/link";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { DataTable } from "@/components/primitives/DataTable";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { StatusDot } from "@/components/primitives/StatusDot";
import { Urn } from "@/components/data/Urn";
import { Timestamp } from "@/components/data/Timestamp";
import { ArrowUpRight, Pencil, Plus } from "lucide-react";

export const dynamic = "force-dynamic";

/**
 * Workflows page — templates + recent runs.
 *
 * Templates render as a grid of typeset cards: framework chips along the
 * top, the workflow's name in Fraunces, a one-paragraph description, and
 * the required hooks/corpora as small-caps metadata. The "instantiate"
 * action lives on hover (revealed on the right edge of each card).
 */
export default async function WorkflowsPage() {
  const [workflows, runs] = await Promise.all([
    api.workflows.list(),
    api.workflowRuns.list()
  ]);

  return (
    <div>
      <PageHeader
        number="03"
        kicker="Workflow runtime · templates"
        title={<>Run AI agents to do <span className="ed-display-italic">your</span> compliance work.</>}
        subtitle="Each workflow is a typed DAG of sandboxed agentic steps with declared inputs, outputs, hooks, and policies. The agent on each step is itself a governed Asset."
        aside={
          <Link
            href="/workflows/new"
            className="inline-flex items-center gap-2 border border-gold px-3 py-2 text-[12px] text-gold hover:bg-gold hover:text-ink transition-colors rounded-sm"
          >
            <Plus size={13} strokeWidth={1.75} />
            New workflow
          </Link>
        }
      />

      <Section number="03·1" eyebrow="Templates" title="Choose a workflow">
        <ul className="grid gap-px bg-rule lg:grid-cols-2">
          {workflows.map((w, i) => (
            <li key={w.id} className="bg-ink p-6 hover:bg-ink-2 transition-colors group relative">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10.5px] text-paper-fade tabular-nums">
                      §03·t·{String(i + 1).padStart(2, "0")}
                    </span>
                    <Badge tone="muted">{w.trigger}</Badge>
                  </div>
                  <h3 className="mt-2 ed-h2 text-paper text-[20px]">{w.name}</h3>
                  <p className="mt-2 text-[12.5px] text-paper-dim leading-snug max-w-md">
                    {w.description}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[10.5px] uppercase tracking-[0.16em] text-paper-fade">
                    {w.required_hooks.length > 0 && (
                      <span className="inline-flex items-center gap-2">
                        <span>hooks</span>
                        <span className="font-mono normal-case tracking-tight text-paper-dim">
                          {w.required_hooks.join(", ")}
                        </span>
                      </span>
                    )}
                    <span className="inline-flex items-center gap-2">
                      <span>corpora</span>
                      <span className="font-mono normal-case tracking-tight text-paper-dim">
                        {w.required_corpora.join(", ") || "any"}
                      </span>
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {w.template_origin === "user-defined" && (
                    <Link href={`/workflows/${w.id}/edit`}>
                      <Button size="sm" variant="ghost">
                        <Pencil size={10} strokeWidth={1.75} />
                        edit
                      </Button>
                    </Link>
                  )}
                  <Link href={`/workflows/${w.id}`} aria-label={`Open ${w.name}`}>
                    <Button size="sm" variant="primary">
                      open
                      <ArrowUpRight size={11} strokeWidth={1.5} />
                    </Button>
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section number="03·2" eyebrow="Runs" title="Recent runs">
        <DataTable
          rows={runs}
          rowHref={(r) => `/workflow-runs/${r.id}`}
          columns={[
            { key: "status", header: "Status", width: "150px", render: (r) => (
              <span className="inline-flex items-center gap-2">
                <StatusDot tone={r.status === "running" ? "gold" : r.status === "succeeded" ? "ok" : r.status === "failed" ? "crit" : "neutral"} live={r.status === "running"} />
                <span className="font-mono text-[11.5px]">{r.status}</span>
              </span>
            ) },
            { key: "id", header: "Run", width: "1.2fr", render: (r) => (
              <div>
                <div className="text-paper">{r.id}</div>
                <div className="mt-0.5"><Urn urn={r.urn} /></div>
              </div>
            ) },
            { key: "by", header: "Triggered by", width: "1fr", render: (r) => <span className="font-mono text-[11.5px] text-paper-dim">{r.triggered_by}</span> },
            { key: "started", header: "Started", width: "120px", render: (r) => <Timestamp ts={r.triggered_at} /> },
            { key: "finished", header: "Finished", width: "120px", render: (r) => r.finished_at ? <Timestamp ts={r.finished_at} /> : <span className="text-paper-fade">— in flight —</span> }
          ]}
        />
      </Section>
    </div>
  );
}
