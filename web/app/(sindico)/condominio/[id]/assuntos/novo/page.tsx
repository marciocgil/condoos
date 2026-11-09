import { CaseForm } from "@/components/condoos/CaseForm";
import { apiGet } from "@/lib/api";
import type { Condominium, FindingDetail, OpportunityDetail } from "@/lib/types";

export default async function NovoAssuntoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ achado?: string; oportunidade?: string; titulo?: string }>;
}) {
  const { id } = await params;
  const { achado, oportunidade, titulo } = await searchParams;
  const [condo, finding, opp] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    achado
      ? apiGet<FindingDetail>(`/condominiums/${id}/findings/${achado}`)
      : Promise.resolve(null),
    oportunidade
      ? apiGet<OpportunityDetail>(`/condominiums/${id}/opportunities/${oportunidade}`)
      : Promise.resolve(null),
  ]);
  return (
    <CaseForm
      condos={[{ id: condo.id, name: condo.name }]}
      finding={finding ? { id: finding.id, title: finding.title, condominiumId: id } : undefined}
      opportunity={opp ? { id: opp.id, title: opp.title, condominiumId: id } : undefined}
      detailPath="/condominio/{condo}/assuntos/{case}"
      initialTitle={titulo}
    />
  );
}
