import { ChevronRight, type LucideIcon } from "lucide-react";
import Link from "next/link";

/** One of the few options of a guided screen (D127): an icon, what it does, one line of
 * context. */
export function GuidedChoice({
  href,
  icon: Icon,
  title,
  detail,
  quiet = false,
  testId,
}: {
  href: string;
  icon: LucideIcon;
  title: string;
  detail: string;
  quiet?: boolean;
  testId?: string;
}) {
  return (
    <Link
      href={href}
      data-testid={testId}
      className={`transition-ui grid grid-cols-[36px_1fr_16px] items-center gap-3 rounded-[var(--radius-card)] border border-line p-4 hover:border-control ${quiet ? "" : "bg-surface"}`}
    >
      <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-elevated">
        <Icon size={18} aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block text-[15px] font-semibold">{title}</span>
        <span className="mt-0.5 block text-[12.5px] leading-snug text-fg-2">{detail}</span>
      </span>
      <ChevronRight size={16} aria-hidden className="text-muted" />
    </Link>
  );
}
