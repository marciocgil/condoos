import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DelegationForm } from "@/components/condoos/DelegationForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { apiGet } from "@/lib/api";
import type { DelegationItem, Portfolio } from "@/lib/types";

/** The team prepares a request (LB-044); it stays a draft until the síndico authorises. */
export default async function NovoPedidoAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; item?: string; para?: string; papel?: string }>;
}) {
  const { condominio, item, para, papel } = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condo = portfolio.condominiums.find((c) => c.id === condominio);
  if (!condo) notFound();
  const suggestions = await apiGet<DelegationItem[]>(
    `/condominiums/${condo.id}/delegations/suggestions`,
  );
  return (
    <div className="max-w-2xl space-y-4">
      <Link
        href={`/admin/pedidos?condominio=${condo.id}`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Pedidos
      </Link>
      <PageHeader
        title="Preparar pedido"
        subtitle={`${condo.name} · fica como rascunho até o síndico autorizar`}
      />
      <DelegationForm
        condominiumId={condo.id}
        suggestions={suggestions}
        defaultDue={new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10)}
        initial={{ item, name: para, role: papel }}
        detailBase={`/admin/pedidos/${condo.id}`}
      />
    </div>
  );
}
