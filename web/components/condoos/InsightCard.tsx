import { ChevronRight, Sparkles } from "lucide-react";
import Link from "next/link";

import { formatBRLShort } from "@/lib/format";
import type { Finding } from "@/lib/types";

import { FindingStatusBadge } from "./FindingStatusBadge";
import { SeverityBadge } from "./SeverityBadge";

/** AI Insight Card (DS §5.5), compact: a finding in a list, leading to its evidence. */
export function InsightCard({
  finding,
  href,
  showStatus = false,
}: {
  finding: Finding;
  href: string;
  showStatus?: boolean;
}) {
  return (
    <Link
      href={href}
      className="transition-ui flex items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 hover:border-control hover:bg-elevated"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{finding.title}</p>
        <p className="tabular mt-0.5 truncate text-[13px] text-fg-2">
          {finding.supplier_name ?? finding.category_label ?? "—"} ·{" "}
          {formatBRLShort(finding.amount_at_risk)}
        </p>
        {/* Severity always in words and icon, never only a colour (LB-084, D108). */}
        <div className="mt-2 flex flex-wrap gap-2">
          <SeverityBadge severity={finding.severity} />
          {showStatus && <FindingStatusBadge status={finding.status} />}
          {finding.ai_assisted && (
            <span className="inline-flex items-center gap-1 text-xs text-fg-2">
              <Sparkles size={12} aria-hidden /> Assistido por IA
            </span>
          )}
        </div>
      </div>
      <ChevronRight size={16} className="shrink-0 text-muted" aria-hidden />
    </Link>
  );
}
