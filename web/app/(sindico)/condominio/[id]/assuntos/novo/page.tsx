import { CaseForm } from "@/components/condoos/CaseForm";
import { apiGet } from "@/lib/api";
import type { Condominium, FindingDetail } from "@/lib/types";

export default async function NovoAssuntoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ achado?: string }>;
}) {
  const { id } = await params;
  const { achado } = await searchParams;
  const [condo, finding] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    achado
      ? apiGet<FindingDetail>(`/condominiums/${id}/findings/${achado}`)
      : Promise.resolve(null),
  ]);
  return (
    <CaseForm
      condos={[{ id: condo.id, name: condo.name }]}
      finding={finding ? { id: finding.id, title: finding.title, condominiumId: id } : undefined}
      detailPath="/condominio/{condo}/assuntos/{case}"
    />
  );
}
