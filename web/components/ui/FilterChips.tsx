import { X } from "lucide-react";
import Link from "next/link";

import { cx } from "./cx";

export interface ChipOption {
  value: string;
  label: string;
}

/**
 * Filter bar in chips (DS §5.9). Works without JavaScript: each chip is a link that toggles
 * the value in the URL; active chips are visible and removable.
 */
export function FilterChips({
  name,
  label,
  options,
  selected,
  pathname,
  params,
}: {
  name: string;
  label: string;
  options: ChipOption[];
  selected: string[];
  pathname: string;
  params: Record<string, string[]>;
}) {
  function href(value: string): string {
    const next = new URLSearchParams();
    for (const [k, vs] of Object.entries(params)) {
      if (k === name) continue;
      vs.forEach((v) => next.append(k, v));
    }
    const current = new Set(selected);
    if (current.has(value)) current.delete(value);
    else current.add(value);
    current.forEach((v) => next.append(name, v));
    const qs = next.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  }
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted">{label}</span>
      {options.map((o) => {
        const active = selected.includes(o.value);
        return (
          <Link
            key={o.value}
            href={href(o.value)}
            aria-pressed={active}
            className={cx(
              "transition-ui inline-flex h-8 items-center gap-1 rounded-full border px-3 text-[13px]",
              active
                ? "border-accent bg-accent/10 text-fg"
                : "border-control text-fg-2 hover:text-fg",
            )}
          >
            {o.label}
            {active && <X size={14} aria-label="remover filtro" />}
          </Link>
        );
      })}
    </div>
  );
}
