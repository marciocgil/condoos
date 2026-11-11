import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { cx } from "@/components/ui/cx";
import { shiftMonth } from "@/lib/audit";
import { formatMonthTitle } from "@/lib/format";

/** Condominium and month of the audit screens (plain links, works without JavaScript). */
export function AuditToolbar({
  pathname,
  condos,
  selected,
  competencia,
}: {
  pathname: string;
  condos: { id: string; name: string }[];
  selected: string;
  competencia: string;
}) {
  const href = (ym: string) => `${pathname}?condominio=${selected}&competencia=${ym}`;
  return (
    <div className="mb-2">
      {condos.length > 1 && (
        <nav aria-label="Condomínio" className="mb-4 flex flex-wrap gap-2">
          {condos.map((c) => (
            <Link
              key={c.id}
              href={`${pathname}?condominio=${c.id}&competencia=${competencia}`}
              aria-current={c.id === selected ? "page" : undefined}
              className={cx(
                "inline-flex h-8 items-center rounded-full border px-3 text-[13px]",
                c.id === selected
                  ? "border-accent bg-accent/10 font-medium"
                  : "border-control text-fg-2 hover:text-fg",
              )}
            >
              {c.name}
            </Link>
          ))}
        </nav>
      )}
      <nav aria-label="Competência" className="mb-6 flex items-center gap-2 text-sm">
        <Link
          href={href(shiftMonth(competencia, -1))}
          className="rounded-full border border-control p-1 text-fg-2 hover:text-fg"
          aria-label="Mês anterior"
        >
          <ChevronLeft size={16} aria-hidden />
        </Link>
        <span className="min-w-[160px] text-center font-medium">
          {formatMonthTitle(`${competencia}-01`)}
        </span>
        <Link
          href={href(shiftMonth(competencia, 1))}
          className="rounded-full border border-control p-1 text-fg-2 hover:text-fg"
          aria-label="Mês seguinte"
        >
          <ChevronRight size={16} aria-hidden />
        </Link>
      </nav>
    </div>
  );
}
