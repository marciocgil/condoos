import Link from "next/link";

import { formatDateTime } from "@/lib/format";
import { CASE_CATEGORY_LABEL } from "@/lib/labels";
import type { CaseRow } from "@/lib/types";

import { CaseAttention, CaseStatusBadge } from "./CaseStatusBadge";

/** Case list for the phone: one card per case, attention first (order comes from the API). */
export function CaseCards({ rows, hrefFor }: { rows: CaseRow[]; hrefFor: (r: CaseRow) => string }) {
  return (
    <ul className="space-y-3" aria-label="Assuntos">
      {rows.map((r) => (
        <li key={r.id}>
          <Link
            href={hrefFor(r)}
            className="transition-ui block rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-control"
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted tabular-nums">{r.number}</span>
              <CaseStatusBadge status={r.status} />
              <CaseAttention flags={r.attention} />
            </span>
            <span className="mt-1 block font-medium">{r.title}</span>
            <span className="mt-1 block text-[13px] text-fg-2">
              {r.next_action ?? "—"}
              {r.next_action_due_at && ` · até ${formatDateTime(r.next_action_due_at)}`}
            </span>
            <span className="mt-0.5 block text-xs text-muted">
              {CASE_CATEGORY_LABEL[r.category] ?? r.category} · {r.owner?.name ?? "sem responsável"}
              {r.open_tasks > 0 && ` · ${r.open_tasks} tarefa(s) aberta(s)`}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
