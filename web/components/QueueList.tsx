import { AlertOctagon, FileWarning, GitMerge } from "lucide-react";

import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { QueueItem } from "@/lib/types";

const KIND = {
  extracao: {
    icon: <FileWarning size={16} />,
    tone: "text-warning",
    label: "Extração",
    action: "Corrigir",
  },
  casamento: {
    icon: <GitMerge size={16} />,
    tone: "text-info",
    label: "Casamento",
    action: "Resolver",
  },
  achado_grave: {
    icon: <AlertOctagon size={16} />,
    tone: "text-danger",
    label: "Achado grave",
    action: "Validar",
  },
} as const;

function hrefFor(item: QueueItem): string {
  if (item.kind === "extracao") return `/admin/fila/documento/${item.condominium_id}/${item.id}`;
  if (item.kind === "casamento") return `/admin/fila/casamento/${item.condominium_id}/${item.id}`;
  return `/admin/achados/${item.condominium_id}/${item.id}`;
}

export function QueueList({ items }: { items: QueueItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState title="Nenhum item na fila">
        Tudo em dia: nada aguarda correção ou validação.
      </EmptyState>
    );
  }
  return (
    <ul className="space-y-2" aria-label="Itens da fila de exceções">
      {items.map((item) => {
        const k = KIND[item.kind];
        return (
          <li
            key={`${item.kind}-${item.id}`}
            className="flex items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3"
          >
            <span className={k.tone} aria-hidden>
              {k.icon}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">
                <span className="sr-only">{k.label}: </span>
                {item.title} · {item.condominium_name}
              </p>
              {item.detail && <p className="truncate text-xs text-fg-2">{item.detail}</p>}
            </div>
            <ButtonLink
              href={hrefFor(item)}
              size="sm"
              variant={item.kind === "achado_grave" ? "primary" : "secondary"}
            >
              {k.action}
            </ButtonLink>
          </li>
        );
      })}
    </ul>
  );
}
