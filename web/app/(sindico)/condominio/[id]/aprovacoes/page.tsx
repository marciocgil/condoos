import { CheckSquare, Plus } from "lucide-react";
import Link from "next/link";

import { ActionCards } from "@/components/condoos/ActionCards";
import { AutomationPausesCard } from "@/components/condoos/AutomationPausesCard";
import { buttonClass } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { ActionRow, AutomationPauses, Me } from "@/lib/types";

export default async function AprovacoesPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ situacao?: string }>;
}) {
  const { id } = await params;
  const { situacao } = await searchParams;
  const all = situacao === "todas";
  const [rows, pauses, me] = await Promise.all([
    apiGet<ActionRow[]>(`/condominiums/${id}/actions${all ? "?situacao=todas" : ""}`),
    apiGet<AutomationPauses>(`/condominiums/${id}/automation-pauses`),
    apiGet<Me>("/me"),
  ]);
  const canRequest = me.condominiums.find((c) => c.id === id)?.permissions.includes("manage_cases");
  return (
    <>
      <h1 className="text-xl font-semibold">Aprovações</h1>
      <p className="text-[13px] text-fg-2">
        Pedidos de ação com escopo e teto definidos. Nada é enviado pelo sistema: depois de
        aprovado, uma pessoa executa e registra.
      </p>
      <div className="flex flex-wrap gap-2">
        <Link
          href={`/condominio/${id}/aprovacoes${all ? "" : "?situacao=todas"}`}
          className={buttonClass("ghost", "sm")}
        >
          {all ? "Ver só as abertas" : "Ver todas"}
        </Link>
        {canRequest && (
          <Link
            href={`/condominio/${id}/aprovacoes/nova`}
            className={buttonClass("secondary", "sm")}
          >
            <Plus size={14} aria-hidden /> Pedir ação
          </Link>
        )}
      </div>
      {rows.length === 0 ? (
        <EmptyState icon={<CheckSquare size={24} />} title="Nenhum pedido aberto">
          Pedidos de ação aparecem aqui para a sua aprovação.
        </EmptyState>
      ) : (
        <ActionCards rows={rows} detailPath={`/condominio/${id}/aprovacoes/{id}`} />
      )}
      <AutomationPausesCard condominiumId={id} pauses={pauses} />
    </>
  );
}
