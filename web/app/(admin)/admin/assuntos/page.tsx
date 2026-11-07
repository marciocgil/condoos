import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";

import { CaseAttention, CaseStatusBadge } from "@/components/condoos/CaseStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonClass } from "@/components/ui/Button";
import { cx } from "@/components/ui/cx";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { CASE_CATEGORY_LABEL } from "@/lib/labels";
import type { CaseRow, Me } from "@/lib/types";

const VIEWS = [
  { key: "abertos", label: "Abertos", qs: "situacao=abertos" },
  { key: "meus", label: "Meus", qs: "situacao=abertos&responsavel=me" },
  { key: "encerrados", label: "Encerrados", qs: "situacao=encerrados" },
] as const;

/** Cases of the portfolio (D80): attention first, then by due date. */
export default async function AssuntosAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ ver?: string; condominio?: string }>;
}) {
  const { ver, condominio } = await searchParams;
  const view = VIEWS.find((v) => v.key === ver) ?? VIEWS[0];
  const qs = new URLSearchParams(view.qs);
  if (condominio) qs.set("condominium_id", condominio);
  const [rows, me] = await Promise.all([
    apiGet<CaseRow[]>(`/portfolio/cases?${qs.toString()}`),
    apiGet<Me>("/me"),
  ]);
  const canCreate = me.condominiums.some((c) => c.permissions.includes("manage_cases"));
  const keep = condominio ? `&condominio=${condominio}` : "";
  return (
    <>
      <PageHeader
        title="Assuntos"
        subtitle="Cada assunto com responsável, próxima ação e prazo, até a conclusão com evidência."
        actions={
          canCreate ? (
            <Link
              href={`/admin/assuntos/novo${condominio ? `?condominio=${condominio}` : ""}`}
              className={buttonClass("secondary", "sm")}
            >
              <Plus size={14} aria-hidden /> Novo assunto
            </Link>
          ) : undefined
        }
      />
      <nav aria-label="Filtro de assuntos" className="mb-4 flex gap-2">
        {VIEWS.map((v) => (
          <Link
            key={v.key}
            href={`/admin/assuntos?ver=${v.key}${keep}`}
            aria-current={v.key === view.key ? "page" : undefined}
            className={cx(
              "transition-ui inline-flex h-8 items-center rounded-full border px-3 text-[13px]",
              v.key === view.key ? "border-accent bg-accent/10" : "border-control text-fg-2",
            )}
          >
            {v.label}
          </Link>
        ))}
      </nav>
      <DataTable
        caption="Assuntos"
        rows={rows}
        rowKey={(r) => r.id}
        rowHref={(r) => `/admin/assuntos/${r.condominium_id}/${r.id}`}
        empty={
          <EmptyState icon={<FolderKanban size={24} />} title="Nenhum assunto aqui">
            Abra um assunto a partir de um achado ou de um pedido.
          </EmptyState>
        }
        columns={[
          {
            key: "number",
            header: "Nº",
            cell: (r) => <span className="tabular-nums">{r.number}</span>,
          },
          {
            key: "title",
            header: "Assunto",
            cell: (r) => (
              <span>
                <span className="block font-medium">{r.title}</span>
                <span className="text-xs text-muted">
                  {r.condominium_name} · {CASE_CATEGORY_LABEL[r.category] ?? r.category}
                </span>
              </span>
            ),
          },
          {
            key: "status",
            header: "Estado",
            cell: (r) => (
              <span className="flex flex-wrap gap-1">
                <CaseStatusBadge status={r.status} />
                <CaseAttention flags={r.attention} />
              </span>
            ),
          },
          { key: "owner", header: "Responsável", cell: (r) => r.owner?.name ?? "—" },
          {
            key: "next",
            header: "Próxima ação",
            cell: (r) => (
              <span>
                <span className="block">{r.next_action ?? "—"}</span>
                {r.next_action_due_at && (
                  <span className="text-xs text-muted">
                    até {formatDateTime(r.next_action_due_at)}
                  </span>
                )}
              </span>
            ),
          },
        ]}
      />
    </>
  );
}
