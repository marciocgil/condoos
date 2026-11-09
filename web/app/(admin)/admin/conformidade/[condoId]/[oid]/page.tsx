import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { ComplianceDetailView } from "@/components/condoos/ComplianceDetailView";
import { apiGet } from "@/lib/api";
import type { ComplianceDetail } from "@/lib/types";

export default async function ObrigacaoAdminPage({
  params,
}: {
  params: Promise<{ condoId: string; oid: string }>;
}) {
  const { condoId, oid } = await params;
  const ob = await apiGet<ComplianceDetail>(`/condominiums/${condoId}/compliance/${oid}`);
  return (
    <div className="max-w-2xl space-y-4">
      <Link
        href={`/admin/conformidade?condominio=${condoId}`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Conformidade
      </Link>
      <ComplianceDetailView
        condominiumId={condoId}
        ob={ob}
        requestHref={`/admin/pedidos/novo?condominio=${condoId}`}
        caseHref={`/admin/assuntos/novo?condominio=${condoId}`}
      />
    </div>
  );
}
