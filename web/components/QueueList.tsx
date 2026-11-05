import Link from "next/link";

import type { QueueItem } from "@/lib/types";

export function QueueList({ items }: { items: QueueItem[] }) {
  if (items.length === 0) {
    return (
      <p className="rounded-xl bg-white p-5 text-sm text-gray-500 shadow-sm">
        Nenhum item na fila. Tudo em dia.
      </p>
    );
  }
  return (
    <ul className="space-y-2" aria-label="Itens da fila de exceções">
      {items.map((item) => (
        <li
          key={`${item.kind}-${item.id}`}
          className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3"
        >
          <span
            aria-hidden
            className={`h-2.5 w-2.5 shrink-0 rounded-full ${
              item.kind === "extracao" ? "bg-amber-400" : "bg-sev-alta"
            }`}
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm">
              {item.title} · {item.condominium_name}
            </p>
            {item.detail && <p className="truncate text-xs text-gray-500">{item.detail}</p>}
          </div>
          {item.kind === "extracao" ? (
            <Link
              href={`/admin/fila/documento/${item.condominium_id}/${item.id}`}
              className="rounded-lg border border-brand-600 bg-brand-50 px-4 py-1.5 text-sm font-medium text-brand-700"
            >
              Corrigir
            </Link>
          ) : (
            <span
              title="A validação de achados chega no Marco 4"
              className="rounded-lg border border-gray-300 px-4 py-1.5 text-sm text-gray-400"
            >
              Validar
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
