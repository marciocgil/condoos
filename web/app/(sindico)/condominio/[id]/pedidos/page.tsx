import { ChevronLeft, Plus } from "lucide-react";
import Link from "next/link";

import { DelegationStatusBadge } from "@/components/condoos/DelegationStatusBadge";
import { buttonClass } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { DelegationSummary } from "@/lib/types";

/** Document requests to people without a login (D95): the CondoOS makes the link and the
 * text; the síndico sends them. */
export default async function PedidosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const requests = await apiGet<DelegationSummary[]>(`/condominiums/${id}/delegations`);
  return (
    <>
      <Link
        href={`/condominio/${id}/enviar`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Enviar documentos
      </Link>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Pedidos de documentos</h1>
        <Link href={`/condominio/${id}/pedidos/novo`} className={buttonClass("primary", "sm")}>
          <Plus size={14} aria-hidden /> Novo pedido
        </Link>
      </div>
      <p className="text-sm text-fg-2">
        Peça a quem tem os documentos. Eu preparo um link só para envio e o texto; você manda pelo
        seu WhatsApp ou e-mail.
      </p>
      {requests.length === 0 ? (
        <EmptyState title="Nenhum pedido ainda">
          Comece pelos documentos que faltam: eu sugiro os itens.
        </EmptyState>
      ) : (
        <ul className="space-y-2" aria-label="Pedidos">
          {requests.map((r) => (
            <li key={r.id}>
              <Link
                href={`/condominio/${id}/pedidos/${r.id}`}
                className="transition-ui block rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-control"
              >
                <span className="flex items-start justify-between gap-3">
                  <span className="font-medium">{r.recipient_name}</span>
                  <DelegationStatusBadge status={r.status} />
                </span>
                <span className="mt-1 block text-[13px] text-fg-2">
                  {r.progress.attended} de {r.progress.total} recebidos · prazo{" "}
                  {formatDate(r.due_date)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
