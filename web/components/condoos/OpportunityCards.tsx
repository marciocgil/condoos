import Link from "next/link";

import { formatBRL } from "@/lib/format";
import { OPPORTUNITY_TYPE_LABEL, SAVINGS_STAGE_LABEL } from "@/lib/labels";
import type { OpportunityRow } from "@/lib/types";

import { OpportunityStatusBadge } from "./OpportunityStatusBadge";

/** Opportunities as cards. The value shown is the most advanced stage the viewer may see,
 * always with that stage's name (never a total across stages). */
export function OpportunityCards({
  rows,
  hrefFor,
}: {
  rows: OpportunityRow[];
  hrefFor: (r: OpportunityRow) => string;
}) {
  return (
    <ul className="space-y-3" aria-label="Oportunidades">
      {rows.map((r) => (
        <li key={r.id}>
          <Link
            href={hrefFor(r)}
            className="transition-ui block rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-control"
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted tabular-nums">{r.number}</span>
              <OpportunityStatusBadge status={r.status} />
            </span>
            <span className="mt-1 block font-medium">{r.title}</span>
            {r.headline_stage && r.headline_annualized && (
              <span className="mt-1 block text-[13px] text-fg-2">
                {SAVINGS_STAGE_LABEL[r.headline_stage]}:{" "}
                <span className="font-medium text-fg tabular-nums">
                  {formatBRL(r.headline_annualized)} por ano
                </span>
              </span>
            )}
            <span className="mt-0.5 block text-xs text-muted">
              {OPPORTUNITY_TYPE_LABEL[r.opportunity_type] ?? r.opportunity_type}
              {r.supplier_name && ` · ${r.supplier_name}`}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
