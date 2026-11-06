import { Upload } from "lucide-react";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { PageHeader } from "@/components/layout/PageHeader";
import { QueueList } from "@/components/QueueList";
import { ButtonLink } from "@/components/ui/Button";
import { apiGet } from "@/lib/api";
import type { Portfolio, QueueItem } from "@/lib/types";

export default async function FilaPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const { condominio } = await searchParams;
  const [all, portfolio] = await Promise.all([
    apiGet<QueueItem[]>("/queue"),
    apiGet<Portfolio>("/portfolio"),
  ]);
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === condominio) ? condominio! : null;
  const items = selected ? all.filter((i) => i.condominium_id === selected) : all;
  return (
    <>
      <PageHeader
        title="Fila de exceções"
        subtitle={`${items.length} ${items.length === 1 ? "item" : "itens"} · leituras incertas, casamentos ambíguos e achados graves aguardando validação`}
        actions={
          <ButtonLink
            href="/admin/enviar"
            variant="primary"
            icon={<Upload size={16} aria-hidden />}
          >
            Enviar documentos
          </ButtonLink>
        }
      />
      <CondoFilter pathname="/admin/fila" condos={condos} selected={selected} />
      <QueueList items={items} />
    </>
  );
}
