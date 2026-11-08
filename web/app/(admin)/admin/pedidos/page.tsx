import { Plus } from "lucide-react";
import Link from "next/link";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { DelegationStatusBadge } from "@/components/condoos/DelegationStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonClass } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Portfolio, PortfolioDelegation } from "@/lib/types";

/** The team's desktop (LB-044): document requests of every condominium, open ones first by
 * due date. The team prepares; only the síndico authorises and sends the link (D95). */
export default async function PedidosAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const sp = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const rows = await apiGet<PortfolioDelegation[]>(
    `/portfolio/delegations${selected ? `?condominium_id=${selected}` : ""}`,
  );
  const target = selected ?? (condos.length === 1 ? (condos[0]?.id ?? null) : null);
  const open = rows.filter((r) =>
    ["rascunho", "autorizado", "aguardando_envio", "recebendo"].includes(r.status),
  ).length;
  return (
    <>
      <PageHeader
        title="Pedidos de documentos"
        subtitle={`${open} ${open === 1 ? "pedido aberto" : "pedidos abertos"}`}
        actions={
          target ? (
            <Link
              href={`/admin/pedidos/novo?condominio=${target}`}
              className={buttonClass("primary", "sm")}
            >
              <Plus size={14} aria-hidden /> Preparar pedido
            </Link>
          ) : undefined
        }
      />
      <CondoFilter pathname="/admin/pedidos" condos={condos} selected={selected} />
      <p className="mb-6 text-sm text-fg-2">
        A equipe prepara o pedido; o síndico autoriza, gera o link e envia pelo canal dele. Nada sai
        do sistema.{!target && " Escolha um condomínio para preparar um pedido."}
      </p>
      <DataTable
        caption="Pedidos de documentos"
        rows={rows}
        rowKey={(r) => r.id}
        rowHref={(r) => `/admin/pedidos/${r.condominium_id}/${r.id}`}
        empty={
          <EmptyState title="Nenhum pedido">
            Os pedidos preparados pela equipe ou pelo síndico aparecem aqui.
          </EmptyState>
        }
        columns={[
          { key: "condo", header: "Condomínio", cell: (r) => r.condominium },
          { key: "who", header: "Para quem", cell: (r) => r.recipient_name },
          {
            key: "status",
            header: "Estado",
            cell: (r) => <DelegationStatusBadge status={r.status} />,
          },
          {
            key: "progress",
            header: "Recebidos",
            align: "right",
            cell: (r) => `${r.progress.attended} de ${r.progress.total}`,
          },
          { key: "due", header: "Prazo", cell: (r) => formatDate(r.due_date) },
        ]}
      />
    </>
  );
}
