import { FindingDetailView } from "@/components/condoos/FindingDetailView";
import { apiGet } from "@/lib/api";
import type { CaseRef, Finding, FindingDetail, Me } from "@/lib/types";

export default async function FindingPage({
  params,
}: {
  params: Promise<{ id: string; findingId: string }>;
}) {
  const { id, findingId } = await params;
  const [finding, cases, opportunities, me, waiting] = await Promise.all([
    apiGet<FindingDetail>(`/condominiums/${id}/findings/${findingId}`),
    apiGet<CaseRef[]>(`/condominiums/${id}/findings/${findingId}/cases`),
    apiGet<CaseRef[]>(`/condominiums/${id}/findings/${findingId}/opportunities`),
    apiGet<Me>("/me"),
    apiGet<Finding[]>(`/condominiums/${id}/findings?status=publicado`),
  ]);
  // The next point waiting for the síndico, largest amount first (LB-086, D108).
  const next = waiting.find((w) => w.id !== findingId);
  const canOpen = me.condominiums.find((c) => c.id === id)?.permissions.includes("manage_cases");
  return (
    <FindingDetailView
      finding={finding}
      condominiumId={id}
      backHref={`/condominio/${id}/achados`}
      backLabel="Achados"
      cases={cases}
      casePath={`/condominio/${id}/assuntos/{id}`}
      newCaseHref={canOpen ? `/condominio/${id}/assuntos/novo?achado=${findingId}` : undefined}
      opportunities={opportunities}
      opportunityPath={`/condominio/${id}/oportunidades/{id}`}
      nextHref={next ? `/condominio/${id}/achados/${next.id}` : null}
      homeHref={`/condominio/${id}/resumo`}
    />
  );
}
