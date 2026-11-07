import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { DelegationDetailView } from "@/components/condoos/DelegationDetailView";
import { apiGet } from "@/lib/api";
import type { DelegationDetail } from "@/lib/types";

export default async function PedidoPage({
  params,
}: {
  params: Promise<{ id: string; reqId: string }>;
}) {
  const { id, reqId } = await params;
  const request = await apiGet<DelegationDetail>(`/condominiums/${id}/delegations/${reqId}`);
  return (
    <>
      <Link
        href={`/condominio/${id}/pedidos`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Pedidos
      </Link>
      <DelegationDetailView condominiumId={id} request={request} />
    </>
  );
}
