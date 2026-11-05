import Link from "next/link";

import { QueueList } from "@/components/QueueList";
import { apiGet } from "@/lib/api";
import type { QueueItem } from "@/lib/types";

export default async function FilaPage() {
  const items = await apiGet<QueueItem[]>("/queue");
  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Fila de exceções</h1>
          <p className="text-sm text-gray-500">
            {items.length} {items.length === 1 ? "item" : "itens"} · documentos com leitura incerta
            e achados graves aguardando validação
          </p>
        </div>
        <Link
          href="/admin/enviar"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Enviar documentos
        </Link>
      </div>
      <div className="mt-6">
        <QueueList items={items} />
      </div>
    </>
  );
}
