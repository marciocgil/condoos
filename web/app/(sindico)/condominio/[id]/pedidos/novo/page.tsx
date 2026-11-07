import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { DelegationForm } from "@/components/condoos/DelegationForm";
import { apiGet } from "@/lib/api";
import type { DelegationItem } from "@/lib/types";

export default async function NovoPedidoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const suggestions = await apiGet<DelegationItem[]>(`/condominiums/${id}/delegations/suggestions`);
  return (
    <>
      <Link
        href={`/condominio/${id}/pedidos`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Pedidos
      </Link>
      <h1 className="text-xl font-semibold">Pedir documentos</h1>
      <DelegationForm
        condominiumId={id}
        suggestions={suggestions}
        defaultDue={new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10)}
      />
    </>
  );
}
