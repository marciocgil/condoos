"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cx } from "@/components/ui/cx";
import { locate } from "@/lib/sindicoNav";

/** Sections of the current tab on the síndico's phone (D115), shown on the list screens of
 * tabs with more than one section; detail screens keep their own "back" link. */
export function SectionNav({ condominiumId }: { condominiumId: string }) {
  const pathname = usePathname();
  const here = locate(pathname);
  const depth = pathname.split("/").filter(Boolean).length;
  if (!here || here.tab.sections.length < 2 || depth > 3) return null;
  return (
    <nav aria-label={`Seções de ${here.tab.label}`} className="-mx-4 overflow-x-auto px-4">
      <ul className="flex gap-2">
        {here.tab.sections.map((s) => {
          const active = s.slug === here.section.slug;
          return (
            <li key={s.slug}>
              <Link
                href={`/condominio/${condominiumId}/${s.slug}`}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "transition-ui inline-flex h-8 items-center rounded-full border px-3 text-[13px] whitespace-nowrap",
                  active
                    ? "border-accent/70 font-medium text-fg"
                    : "border-control text-fg-2 hover:text-fg",
                )}
              >
                {s.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
