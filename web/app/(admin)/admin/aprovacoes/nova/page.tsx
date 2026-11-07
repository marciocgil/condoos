import Link from "next/link";

import { ActionForm } from "@/components/condoos/ActionForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { ActionTypes, CaseDetail, Me } from "@/lib/types";

export default async function NovaAprovacaoAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; assunto?: string }>;
}) {
  const { condominio, assunto } = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = me.condominiums.filter((c) => c.permissions.includes("manage_cases"));
  if (condos.length === 0)
    return (
      <EmptyState title="Sem permissão">Seu papel não pede ações neste condomínio.</EmptyState>
    );
  const current = condos.find((c) => c.id === condominio) ?? condos[0]!;
  const [types, kase] = await Promise.all([
    apiGet<ActionTypes>("/action-types"),
    assunto
      ? apiGet<CaseDetail>(`/condominiums/${current.id}/cases/${assunto}`)
      : Promise.resolve(null),
  ]);
  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Pedir ação com aprovação"
        subtitle={kase ? `Vinculada ao assunto ${kase.number}: ${kase.title}` : current.name}
      />
      {!kase && condos.length > 1 && (
        <nav aria-label="Condomínio" className="mb-4 flex flex-wrap gap-2">
          {condos.map((c) => (
            <Link
              key={c.id}
              href={`/admin/aprovacoes/nova?condominio=${c.id}`}
              aria-current={c.id === current.id ? "page" : undefined}
              className={cx(
                "transition-ui inline-flex h-8 items-center rounded-full border px-3 text-[13px]",
                c.id === current.id
                  ? "border-accent bg-accent/10"
                  : "border-control text-fg-2 hover:text-fg",
              )}
            >
              {c.name}
            </Link>
          ))}
        </nav>
      )}
      <ActionForm
        key={current.id}
        condominiumId={current.id}
        types={types.types}
        caseId={kase?.id}
        detailPath={`/admin/aprovacoes/${current.id}/{id}`}
      />
    </div>
  );
}
