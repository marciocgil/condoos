import Link from "next/link";

import { ContractForm, EMPTY_CONTRACT } from "@/components/condoos/ContractForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

export default async function NovoContratoPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const { condominio } = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = me.condominiums.filter((c) => c.permissions.includes("configure"));
  if (condos.length === 0) {
    return (
      <>
        <PageHeader title="Novo contrato" />
        <EmptyState title="Sem permissão">Somente o gerente cadastra contratos.</EmptyState>
      </>
    );
  }
  const current = condos.find((c) => c.id === condominio) ?? condos[0]!;
  return (
    <>
      <PageHeader
        title="Novo contrato"
        subtitle="Prefira enviar o PDF do contrato: ele vira contrato sozinho e fica como evidência. Use este formulário quando não houver documento."
      />
      <nav aria-label="Condomínio" className="mb-6 flex flex-wrap gap-2">
        {condos.map((c) => (
          <Link
            key={c.id}
            href={`/admin/contratos/novo?condominio=${c.id}`}
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
      <ContractForm key={current.id} condominiumId={current.id} initial={EMPTY_CONTRACT} />
    </>
  );
}
