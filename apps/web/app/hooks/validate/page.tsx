import Link from "next/link";
import { PageHeader } from "@/components/shell/PageHeader";
import { Section } from "@/components/primitives/Section";
import { ManifestValidator } from "@/components/hook-config/ManifestValidator";
import { ArrowLeft } from "lucide-react";

export default function ValidateManifestPage() {
  return (
    <div>
      <Link
        href="/hooks"
        className="inline-flex items-center gap-1.5 text-[12px] text-paper-fade hover:text-paper transition-colors mb-3"
      >
        <ArrowLeft size={13} strokeWidth={1.75} />
        Back to hooks
      </Link>

      <PageHeader
        kicker="Hooks · validate"
        title="Validate JSON Stack manifest."
        subtitle="Paste a manifest to check shape, auth references, and operation structure. Inline secrets are rejected — use auth_ref instead."
      />

      <Section eyebrow="Manifest" title="JSON input">
        <ManifestValidator />
      </Section>
    </div>
  );
}
