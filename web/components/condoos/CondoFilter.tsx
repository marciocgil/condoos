import { Building2 } from "lucide-react";
import Link from "next/link";

import { cx } from "@/components/ui/cx";

/** "Which condominium" filter of the management company screens. Plain links (?condominio=),
 * so it works without JavaScript; the side menu keeps the choice between screens. */
export function CondoFilter({
  pathname,
  condos,
  selected,
  extra = {},
}: {
  pathname: string;
  condos: { id: string; name: string }[];
  selected: string | null;
  extra?: Record<string, string>;
}) {
  if (condos.length < 2) return null;
  const href = (id: string | null) => {
    const params = new URLSearchParams(extra);
    if (id) params.set("condominio", id);
    const q = params.toString();
    return q ? `${pathname}?${q}` : pathname;
  };
  const chip = (active: boolean) =>
    cx(
      "transition-ui inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px]",
      active
        ? "border-accent bg-accent/10 font-medium text-fg"
        : "border-control text-fg-2 hover:text-fg",
    );
  return (
    <nav aria-label="Filtrar por condomínio" className="mb-6 flex flex-wrap items-center gap-2">
      <span className="mr-1 inline-flex items-center gap-1.5 text-xs font-medium tracking-wide text-fg-2 uppercase">
        <Building2 size={14} aria-hidden /> Condomínio
      </span>
      <Link
        href={href(null)}
        aria-current={selected === null ? "page" : undefined}
        className={chip(selected === null)}
      >
        Todos
      </Link>
      {condos.map((c) => (
        <Link
          key={c.id}
          href={href(c.id)}
          aria-current={selected === c.id ? "page" : undefined}
          className={chip(selected === c.id)}
        >
          {c.name.replace(/^Condomínio\s+(Residencial\s+|Edifício\s+)?/, "")}
        </Link>
      ))}
    </nav>
  );
}
