import Link from "next/link";

import { SettingsForm } from "@/components/condoos/SettingsForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardTitle } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/labels";
import type { Me, Settings } from "@/lib/types";

export default async function ConfiguracoesPage({
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
        <PageHeader title="Configurações" />
        <EmptyState title="Sem permissão">Somente o gerente configura os condomínios.</EmptyState>
      </>
    );
  }
  const current = condos.find((c) => c.id === condominio) ?? condos[0]!;
  const settings = await apiGet<Settings>(`/condominiums/${current.id}/settings`);
  return (
    <>
      <PageHeader
        title="Configurações"
        subtitle="Alçadas, parâmetros das regras, categorias e membros, por condomínio."
      />
      <nav aria-label="Condomínio" className="mb-6 flex flex-wrap gap-2">
        {condos.map((c) => (
          <Link
            key={c.id}
            href={`/admin/configuracoes?condominio=${c.id}`}
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
      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <SettingsForm key={current.id} condominiumId={current.id} settings={settings} />
        <div className="space-y-6">
          <Card>
            <CardTitle>Membros com acesso</CardTitle>
            <ul className="divide-y divide-line text-sm">
              {settings.members.map((m) => (
                <li key={`${m.email}-${m.role}`} className="py-2">
                  <p>{m.name}</p>
                  <p className="text-xs text-muted">
                    {ROLE_LABEL[m.role] ?? m.role} ·{" "}
                    {m.scope === "administradora" ? "toda a carteira" : "este condomínio"}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardTitle>Corpo diretivo</CardTitle>
            <p className="mb-2 text-xs text-muted">
              Usado na regra de conflito de interesse (R08).
            </p>
            <ul className="divide-y divide-line text-sm">
              {settings.board.map((b) => (
                <li key={`${b.full_name}-${b.position}`} className="flex justify-between py-2">
                  <span>{b.full_name}</span>
                  <span className="text-xs text-muted">{ROLE_LABEL[b.position] ?? b.position}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
