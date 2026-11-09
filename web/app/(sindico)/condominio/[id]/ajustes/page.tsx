import { CapabilityReadinessCard } from "@/components/condoos/CapabilityReadiness";
import { AutomationPausesCard } from "@/components/condoos/AutomationPausesCard";
import { EvolutionCard } from "@/components/condoos/EvolutionCard";
import { HealthAlertCard } from "@/components/condoos/HealthAlertCard";
import { InboundEmailCard } from "@/components/condoos/InboundEmailCard";
import { ReviewPolicyCard } from "@/components/condoos/ReviewPolicyCard";
import { apiGet } from "@/lib/api";
import {
  ALERT_KINDS,
  type AutomationPauses,
  type CapabilityChange,
  type DataIssue,
  type EvolutionSuggestion,
  type InboundChannel,
  type Launch,
  type ReviewPolicy,
} from "@/lib/types";

/** Síndico's settings on the phone (CB-019, D74, D83): who reviews findings before the board
 * sees them, the inbound e-mail (D101), the pause of automations, and what already works (Launch readiness, D89). Registry data stays with the management. */
export default async function AjustesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [policy, pauses, launch, inbound, history, evolution, issues] = await Promise.all([
    apiGet<ReviewPolicy>(`/condominiums/${id}/review-policy`),
    apiGet<AutomationPauses>(`/condominiums/${id}/automation-pauses`),
    apiGet<Launch>(`/condominiums/${id}/launch`),
    apiGet<InboundChannel>(`/condominiums/${id}/inbound`),
    apiGet<CapabilityChange[]>(`/condominiums/${id}/launch/history`),
    apiGet<{ items: EvolutionSuggestion[]; can_manage: boolean }>(
      `/condominiums/${id}/launch/evolution`,
    ),
    apiGet<DataIssue[]>(`/condominiums/${id}/data-issues?status=aberto`),
  ]);
  // The health alerts this síndico may see (D110): only those for the condominium.
  const alerts = issues.filter((i) => ALERT_KINDS.has(i.kind));
  return (
    <>
      <h1 className="text-xl font-semibold">Ajustes</h1>
      {alerts.map((a) => (
        <HealthAlertCard key={a.id} issue={a} />
      ))}
      <EvolutionCard
        condominiumId={id}
        items={evolution.items}
        canManage={evolution.can_manage}
        base={`/condominio/${id}`}
      />
      <CapabilityReadinessCard items={launch.readiness} history={history} />
      <InboundEmailCard condominiumId={id} channel={inbound} />
      <ReviewPolicyCard condominiumId={id} policy={policy} />
      <AutomationPausesCard condominiumId={id} pauses={pauses} />
    </>
  );
}
