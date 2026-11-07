import { AutomationPausesCard } from "@/components/condoos/AutomationPausesCard";
import { ReviewPolicyCard } from "@/components/condoos/ReviewPolicyCard";
import { apiGet } from "@/lib/api";
import type { AutomationPauses, ReviewPolicy } from "@/lib/types";

/** Síndico's settings on the phone (CB-019, D74, D83): who reviews findings before the board
 * sees them, and the pause of automations. Registry data stays with the management. */
export default async function AjustesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [policy, pauses] = await Promise.all([
    apiGet<ReviewPolicy>(`/condominiums/${id}/review-policy`),
    apiGet<AutomationPauses>(`/condominiums/${id}/automation-pauses`),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold">Ajustes</h1>
      <ReviewPolicyCard condominiumId={id} policy={policy} />
      <AutomationPausesCard condominiumId={id} pauses={pauses} />
    </>
  );
}
