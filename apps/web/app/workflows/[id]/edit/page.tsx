"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { Workflow } from "@/lib/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { WorkflowFormEditor } from "@/components/workflow-graph/WorkflowFormEditor";

export default function EditWorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [workflow, setWorkflow] = useState<Workflow | null | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    void api.workflows.get(id).then((wf) => {
      if (alive) setWorkflow(wf);
    });
    return () => { alive = false; };
  }, [id]);

  if (workflow === undefined) {
    return <div className="pt-12 text-center text-[12px] text-paper-fade">Loading…</div>;
  }
  if (workflow === null) return notFound();

  return (
    <div>
      <Link
        href={`/workflows/${id}`}
        className="inline-flex items-center gap-1.5 text-[12px] text-paper-fade hover:text-paper transition-colors mb-3"
      >
        <ArrowLeft size={13} strokeWidth={1.75} />
        Back to workflow
      </Link>

      <PageHeader
        kicker={workflow.template_origin === "user-defined" ? "Edit · custom workflow" : "Edit · template (read-only)"}
        title={`Edit · ${workflow.name}`}
        subtitle={workflow.description}
      />

      <div className="mt-8">
        <WorkflowFormEditor
          mode="edit"
          workflowId={workflow.id}
          initial={{
            name: workflow.name,
            description: workflow.description,
            required_corpora: workflow.required_corpora,
            required_hooks: workflow.required_hooks,
            graph: workflow.graph
          }}
        />
      </div>
    </div>
  );
}
