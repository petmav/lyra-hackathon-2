import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { WorkflowFormEditor } from "@/components/workflow-graph/WorkflowFormEditor";

export const dynamic = "force-dynamic";

export default function NewWorkflowPage() {
  return (
    <div>
      <Link
        href="/workflows"
        className="inline-flex items-center gap-1.5 text-[12px] text-paper-fade hover:text-paper transition-colors mb-3"
      >
        <ArrowLeft size={13} strokeWidth={1.75} />
        Back to workflows
      </Link>

      <PageHeader
        kicker="Workflow runtime · author"
        title="Compose a new workflow."
        subtitle="Pick prefab nodes per phase, wire dependencies, and select uploaded corpora to bundle into the agent's sandbox at run time."
      />

      <div className="mt-8">
        <WorkflowFormEditor mode="create" />
      </div>
    </div>
  );
}
