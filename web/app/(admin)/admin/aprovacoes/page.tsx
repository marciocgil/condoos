import { CheckSquare, Plus } from "lucide-react";
import Link from "next/link";

import { ActionStatusBadge } from "@/components/condoos/ActionStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonClass } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatBRL, formatDateTime } from "@/lib/format";
import type { ActionRow } from "@/lib/types";

/** Action requests of the portfolio (D83). Only the síndico approves; nothing is sent. */
export default async function AprovacoesAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; situacao?: string }>;
}) {
  const { condominio, situacao } = await searchParams;
  const all = situacao === "todas";
  const query = new URLSearchParams();
  if (condominio) query.set("condominium_id", condominio);
  if (all) query.set("situacao", "todas");
  const rows = await apiGet<ActionRow[]>(`/portfolio/actions?${query.toString()}`);
  const toggle = new URLSearchParams();
  if (condominio) toggle.set("condominio", condominio);
  if (!all) toggle.set("situacao", "todas");
  return (
    <>
      <PageHeader
        title="Aprovações"
        subtitle="Pedidos de ação com escopo congelado. O síndico aprova; nada é enviado pelo sistema."
        actions={
          <div className="flex gap-2">
            <Link
              href={`/admin/aprovacoes?${toggle.toString()}`}
              className={buttonClass("ghost", "sm")}
            >
              {all ? "Ver só as abertas" : "Ver todas"}
            </Link>
            <Link
              href={`/admin/aprovacoes/nova${condominio ? `?condominio=${condominio}` : ""}`}
              className={buttonClass("secondary", "sm")}
            >
              <Plus size={14} aria-hidden /> Pedir ação
            </Link>
          </div>
        }
      />
      <DataTable
        caption="Pedidos de ação"
        rows={rows}
        rowKey={(r) => r.id}
        rowHref={(r) => `/admin/aprovacoes/${r.condominium_id}/${r.id}`}
        empty={
          <EmptyState icon={<CheckSquare size={24} />} title="Nenhum pedido aberto">
            Peça uma ação a partir de um assunto; ela aparece aqui até ser executada.
          </EmptyState>
        }
        columns={[
          {
            key: "title",
            header: "Ação",
            cell: (r) => (
              <span>
                <span className="block font-medium">{r.title}</span>
                <span className="text-xs text-muted">
                  {r.condominium_name} · {r.type_label}
                  {r.case_number && ` · assunto ${r.case_number}`}
                </span>
              </span>
            ),
          },
          {
            key: "status",
            header: "Estado",
            cell: (r) => <ActionStatusBadge status={r.status} />,
          },
          {
            key: "who",
            header: "Pedido",
            cell: (r) => (
              <span className="text-[13px]">
                {r.requested_by}
                <span className="block text-xs text-muted">{formatDateTime(r.created_at)}</span>
              </span>
            ),
          },
          {
            key: "cap",
            header: "Teto",
            align: "right",
            cell: (r) => <span className="tabular-nums">{formatBRL(r.cost_cap)}</span>,
          },
        ]}
      />
    </>
  );
}
