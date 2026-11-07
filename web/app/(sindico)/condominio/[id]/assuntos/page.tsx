import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";

import { CaseCards } from "@/components/condoos/CaseCards";
import { buttonClass } from "@/components/ui/Button";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { CaseRow, Me } from "@/lib/types";

const VIEWS = [
  { key: "abertos", label: "Abertos", qs: "situacao=abertos" },
  { key: "meus", label: "Meus", qs: "situacao=abertos&responsavel=me" },
  { key: "encerrados", label: "Encerrados", qs: "situacao=encerrados" },
] as const;

export default async function AssuntosPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ ver?: string }>;
}) {
  const { id } = await params;
  const { ver } = await searchParams;
  const view = VIEWS.find((v) => v.key === ver) ?? VIEWS[0];
  const [rows, me] = await Promise.all([
    apiGet<CaseRow[]>(`/condominiums/${id}/cases?${view.qs}`),
    apiGet<Me>("/me"),
  ]);
  const canCreate = me.condominiums.find((c) => c.id === id)?.permissions.includes("manage_cases");
  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Assuntos</h1>
        {canCreate && (
          <Link href={`/condominio/${id}/assuntos/novo`} className={buttonClass("secondary", "sm")}>
            <Plus size={14} aria-hidden /> Novo assunto
          </Link>
        )}
      </div>
      <nav aria-label="Filtro de assuntos" className="flex gap-2">
        {VIEWS.map((v) => (
          <Link
            key={v.key}
            href={`/condominio/${id}/assuntos?ver=${v.key}`}
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
      {rows.length === 0 ? (
        <EmptyState icon={<FolderKanban size={24} />} title="Nenhum assunto aqui">
          Abra um assunto para acompanhar um problema até a conclusão, com responsável, prazo e
          evidência.
        </EmptyState>
      ) : (
        <CaseCards rows={rows} hrefFor={(r) => `/condominio/${id}/assuntos/${r.id}`} />
      )}
    </>
  );
}
