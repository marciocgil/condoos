"use client";

import { FileSignature, History, LayoutDashboard, ListChecks } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cx } from "@/components/ui/cx";

const TABS = [
  { slug: "resumo", label: "Resumo", icon: LayoutDashboard },
  { slug: "achados", label: "Achados", icon: ListChecks },
  { slug: "contratos", label: "Contratos", icon: FileSignature },
  { slug: "historico", label: "Histórico", icon: History },
] as const;

export function BottomTabs({ condominiumId }: { condominiumId: string }) {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-bg-2/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    >
      <ul className="mx-auto grid max-w-md grid-cols-4">
        {TABS.map((tab) => {
          const href = `/condominio/${condominiumId}/${tab.slug}`;
          const active = pathname.startsWith(href);
          const Icon = tab.icon;
          return (
            <li key={tab.slug}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex flex-col items-center gap-0.5 py-2.5 text-xs",
                  active ? "font-semibold text-fg" : "text-fg-2",
                )}
              >
                <Icon size={20} aria-hidden className={active ? "text-accent" : undefined} />
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
