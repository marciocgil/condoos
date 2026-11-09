import { CapabilityReadinessCard } from "@/components/condoos/CapabilityReadiness";
import { AutomationPausesCard } from "@/components/condoos/AutomationPausesCard";
import { InboundEmailCard } from "@/components/condoos/InboundEmailCard";
import { ReviewPolicyCard } from "@/components/condoos/ReviewPolicyCard";
import { apiGet } from "@/lib/api";
import type {
  AutomationPauses,
  CapabilityChange,
  InboundChannel,
  Launch,
  ReviewPolicy,
} from "@/lib/types";

/** Síndico's settings on the phone (CB-019, D74, D83): who reviews findings before the board
 * sees them, the inbound e-mail (D101), the pause of automations, and what already works (Launch readiness, D89). Registry data stays with the management. */
export default async function AjustesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [policy, pauses, launch, inbound, history] = await Promise.all([
    apiGet<ReviewPolicy>(`/condominiums/${id}/review-policy`),
    apiGet<AutomationPauses>(`/condominiums/${id}/automation-pauses`),
    apiGet<Launch>(`/condominiums/${id}/launch`),
    apiGet<InboundChannel>(`/condominiums/${id}/inbound`),
    apiGet<CapabilityChange[]>(`/condominiums/${id}/launch/history`),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold">Ajustes</h1>
      <CapabilityReadinessCard items={launch.readiness} history={history} />
      <InboundEmailCard condominiumId={id} channel={inbound} />
      <ReviewPolicyCard condominiumId={id} policy={policy} />
      <AutomationPausesCard condominiumId={id} pauses={pauses} />
    </>
  );
}
