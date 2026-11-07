import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { ActionForm } from "@/components/condoos/ActionForm";
import { apiGet } from "@/lib/api";
import type { ActionTypes, CaseDetail } from "@/lib/types";

export default async function NovaAprovacaoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ assunto?: string }>;
}) {
  const { id } = await params;
  const { assunto } = await searchParams;
  const [types, kase] = await Promise.all([
    apiGet<ActionTypes>("/action-types"),
    assunto ? apiGet<CaseDetail>(`/condominiums/${id}/cases/${assunto}`) : Promise.resolve(null),
  ]);
  const back = kase ? `/condominio/${id}/assuntos/${kase.id}` : `/condominio/${id}/aprovacoes`;
  return (
    <>
      <Link href={back} className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg">
        <ChevronLeft size={16} aria-hidden /> {kase ? `Assunto ${kase.number}` : "Aprovações"}
      </Link>
      <h1 className="text-xl font-semibold">Pedir ação com aprovação</h1>
      {kase && <p className="text-[13px] text-fg-2">Vinculada ao assunto: {kase.title}</p>}
      <ActionForm
        condominiumId={id}
        types={types.types}
        caseId={kase?.id}
        detailPath={`/condominio/${id}/aprovacoes/{id}`}
      />
    </>
  );
}
