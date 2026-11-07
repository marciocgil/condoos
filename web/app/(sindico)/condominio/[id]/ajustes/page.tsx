import { AutomationPausesCard } from "@/components/condoos/AutomationPausesCard";
import { ReadinessCard } from "@/components/condoos/ReadinessCard";
import { ReviewPolicyCard } from "@/components/condoos/ReviewPolicyCard";
import { apiGet } from "@/lib/api";
import type { AutomationPauses, Launch, ReviewPolicy } from "@/lib/types";

/** Síndico's settings on the phone (CB-019, D74, D83): who reviews findings before the board
 * sees them, and the pause of automations. Registry data stays with the management. Also what
 * each capability can do now and what is missing (LB-011, D92). */
export default async function AjustesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [policy, pauses, launch] = await Promise.all([
    apiGet<ReviewPolicy>(`/condominiums/${id}/review-policy`),
    apiGet<AutomationPauses>(`/condominiums/${id}/automation-pauses`),
    apiGet<Launch>(`/condominiums/${id}/launch`),
  ]);
  const send = { href: `/condominio/${id}/enviar`, label: "Enviar documentos" };
  return (
    <>
      <h1 className="text-xl font-semibold">Ajustes</h1>
      <ReadinessCard
        readiness={launch.readiness}
        resolve={{
          documento_lido: send,
          contrato_recebido: send,
          contratos_com_documento: send,
          faturas_casadas: send,
          canal_de_entrada: send,
          notas_do_mes_recebidas: send,
        }}
      />
      <ReviewPolicyCard condominiumId={id} policy={policy} />
      <AutomationPausesCard condominiumId={id} pauses={pauses} />
    </>
  );
}
