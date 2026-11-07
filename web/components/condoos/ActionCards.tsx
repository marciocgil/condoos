import Link from "next/link";

import { formatBRL, formatDateTime } from "@/lib/format";
import type { ActionRow } from "@/lib/types";

import { ActionStatusBadge } from "./ActionStatusBadge";

/** Action requests as cards (mobile). ``detailPath`` has "{id}" replaced. */
export function ActionCards({ rows, detailPath }: { rows: ActionRow[]; detailPath: string }) {
  return (
    <ul className="space-y-3" aria-label="Pedidos de ação">
      {rows.map((r) => (
        <li key={r.id}>
          <Link
            href={detailPath.replace("{id}", r.id)}
            className="transition-ui block rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-control"
          >
            <span className="flex flex-wrap items-center gap-2">
              <ActionStatusBadge status={r.status} />
              <span className="text-xs text-muted">{r.type_label}</span>
            </span>
            <span className="mt-1 block font-medium">{r.title}</span>
            <span className="mt-1 block text-[13px] text-fg-2">
              Teto <span className="text-fg tabular-nums">{formatBRL(r.cost_cap)}</span>
              {r.case_number && ` · assunto ${r.case_number}`}
            </span>
            <span className="mt-0.5 block text-xs text-muted">
              Pedido por {r.requested_by} em {formatDateTime(r.created_at)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
