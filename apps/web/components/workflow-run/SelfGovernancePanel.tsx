"use client";

import { Badge } from "@/components/primitives/Badge";
import { Hairline } from "@/components/primitives/Hairline";
import { AgentDetail } from "@/components/agent-detail/AgentDetail";
import type { Asset } from "@/lib/api/types";
import { useEventStream } from "@/lib/ws/stream";

/**
 * Two AgentDetail renderings stacked — same component, same hash chain.
 * The workflow agent and the production agent are governed identically.
 */
export function SelfGovernancePanel({
  workflowAgent,
  productionAgent
}: {
  workflowAgent: Pick<Asset, "id" | "urn" | "type" | "name" | "risk_tier" | "lifecycle">;
  productionAgent: Pick<Asset, "id" | "urn" | "type" | "name" | "risk_tier" | "lifecycle">;
}) {
  const left = useEventStream({ kind: "asset", id: workflowAgent.id });
  const right = useEventStream({ kind: "asset", id: productionAgent.id });

  return (
    <section>
      <div className="mb-6 flex items-end justify-between gap-6">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-paper-fade mb-1.5">
            Self-governance · same primitives
          </div>
          <h2 className="text-[16px] font-semibold tracking-tight text-paper">
            Identical supervision surface, both agents.
          </h2>
          <p className="mt-2 max-w-2xl text-[13px] text-paper-dim leading-relaxed">
            The workflow agent does our customer&apos;s compliance work. The production agent is the customer&apos;s own AI. Both are{" "}
            <span className="text-paper">Assets</span>, both write to the same hash chain, and both are evaluated by the same control plane.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Badge tone="gold">live</Badge>
          <span className="font-mono text-[11px] text-paper-fade">two streams · one runtime</span>
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <Tag>Workflow surface</Tag>
          <AgentDetail asset={workflowAgent} events={left.events} compact />
        </div>
        <div>
          <Tag>Production surface</Tag>
          <AgentDetail asset={productionAgent} events={right.events} compact />
        </div>
      </div>

      <Hairline tone="display" className="mt-8" />
      <p className="mt-4 text-center text-[12px] text-paper-fade">
        Same hash chain · same memory inspector · same audit packet treatment · same policy engine
      </p>
    </section>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border border-b-0 border-rule bg-ink-2 px-4 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-paper-dim rounded-t-sm">
      <span>{children}</span>
      <span className="font-mono normal-case tracking-tight text-paper-fade">via &lt;AgentDetail /&gt;</span>
    </div>
  );
}
