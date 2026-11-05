import { Upload } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { QueueList } from "@/components/QueueList";
import { ButtonLink } from "@/components/ui/Button";
import { apiGet } from "@/lib/api";
import type { QueueItem } from "@/lib/types";

export default async function FilaPage() {
  const items = await apiGet<QueueItem[]>("/queue");
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
      <QueueList items={items} />
    </>
  );
}
