import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { DelegationDetailView } from "@/components/condoos/DelegationDetailView";
import { apiGet } from "@/lib/api";
import type { DelegationDetail } from "@/lib/types";

export default async function PedidoAdminPage({
  params,
}: {
  params: Promise<{ condoId: string; reqId: string }>;
}) {
  const { condoId, reqId } = await params;
  const request = await apiGet<DelegationDetail>(`/condominiums/${condoId}/delegations/${reqId}`);
  return (
    <div className="max-w-2xl space-y-4">
      <Link
        href={`/admin/pedidos?condominio=${condoId}`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Pedidos
      </Link>
      <DelegationDetailView condominiumId={condoId} request={request} />
    </div>
  );
}
