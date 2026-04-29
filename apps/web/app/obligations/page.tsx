import { ObligationManager } from "@/components/obligation-graph/ObligationManager";

export const dynamic = "force-dynamic";

/**
 * Obligations page — the obligation/control/asset graph at the top, the
 * obligation ledger at the bottom, plus create/edit/delete + YAML import.
 */
export default function ObligationsPage() {
  return <ObligationManager />;
}
