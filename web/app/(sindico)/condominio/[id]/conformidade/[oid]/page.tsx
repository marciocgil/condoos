import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { ComplianceDetailView } from "@/components/condoos/ComplianceDetailView";
import { apiGet } from "@/lib/api";
import type { ComplianceDetail } from "@/lib/types";

export default async function ObrigacaoPage({
  params,
}: {
  params: Promise<{ id: string; oid: string }>;
}) {
  const { id, oid } = await params;
  const ob = await apiGet<ComplianceDetail>(`/condominiums/${id}/compliance/${oid}`);
  return (
    <>
      <Link
        href={`/condominio/${id}/conformidade`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Conformidade
      </Link>
      <ComplianceDetailView
        condominiumId={id}
        ob={ob}
        requestHref={`/condominio/${id}/pedidos/novo`}
        caseHref={`/condominio/${id}/assuntos/novo`}
      />
    </>
  );
}
