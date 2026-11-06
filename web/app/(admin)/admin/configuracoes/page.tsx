import Link from "next/link";

import { BoardCard, MembersCard, ProfileCard } from "@/components/condoos/RegistryCards";
import { SettingsForm } from "@/components/condoos/SettingsForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
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
        subtitle="Dados do condomínio, corpo diretivo, acessos, alçadas e parâmetros das regras."
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
          <ProfileCard
            key={`p-${current.id}`}
            condominiumId={current.id}
            profile={settings.profile}
          />
          <BoardCard key={`b-${current.id}`} condominiumId={current.id} board={settings.board} />
          <MembersCard
            key={`m-${current.id}`}
            condominiumId={current.id}
            members={settings.members}
          />
        </div>
      </div>
    </>
  );
}
