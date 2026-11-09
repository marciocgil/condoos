import { ChevronRight, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { CapabilityReadinessCard } from "@/components/condoos/CapabilityReadiness";
import { AutomationPausesCard } from "@/components/condoos/AutomationPausesCard";
import { InboundEmailCard } from "@/components/condoos/InboundEmailCard";
import { ReviewPolicyCard } from "@/components/condoos/ReviewPolicyCard";
import { apiGet } from "@/lib/api";
import type { AutomationPauses, InboundChannel, Launch, ReviewPolicy } from "@/lib/types";

/** Síndico's settings on the phone (CB-019, D74, D83): who reviews findings before the board
 * sees them, the inbound e-mail (D101), the pause of automations, and what already works (Launch readiness, D89). Registry data stays with the management. */
export default async function AjustesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [policy, pauses, launch, inbound] = await Promise.all([
    apiGet<ReviewPolicy>(`/condominiums/${id}/review-policy`),
    apiGet<AutomationPauses>(`/condominiums/${id}/automation-pauses`),
    apiGet<Launch>(`/condominiums/${id}/launch`),
    apiGet<InboundChannel>(`/condominiums/${id}/inbound`),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold">Ajustes</h1>
      <Link
        href={`/condominio/${id}/conformidade`}
        className="transition-ui flex items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-control"
      >
        <ShieldCheck size={20} aria-hidden className="text-fg-2" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">Conformidade e vencimentos</span>
          <span className="block text-[13px] text-fg-2">AVCB, seguro, laudos e manutenções</span>
        </span>
        <ChevronRight size={16} aria-hidden className="text-muted" />
      </Link>
      <CapabilityReadinessCard items={launch.readiness} />
      <InboundEmailCard condominiumId={id} channel={inbound} />
      <ReviewPolicyCard condominiumId={id} policy={policy} />
      <AutomationPausesCard condominiumId={id} pauses={pauses} />
    </>
  );
}
