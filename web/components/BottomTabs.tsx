"use client";

import { FileSignature, LayoutDashboard, ListTodo, Wallet, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cx } from "@/components/ui/cx";
import { locate, SINDICO_TABS } from "@/lib/sindicoNav";

const ICON: Record<string, LucideIcon> = {
  hoje: LayoutDashboard,
  financas: Wallet,
  rotina: ListTodo,
  documentos: FileSignature,
};

/** Four tabs by purpose (D111): each opens its first section; the others are inside. */
export function BottomTabs({ condominiumId }: { condominiumId: string }) {
  const pathname = usePathname();
  const current = locate(pathname)?.tab.key;
  return (
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-bg-2/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    >
      <ul className="mx-auto grid max-w-md grid-cols-4">
        {SINDICO_TABS.map((tab) => {
          const href = `/condominio/${condominiumId}/${tab.sections[0]!.slug}`;
          const active = current === tab.key;
          const Icon = ICON[tab.key]!;
          return (
            <li key={tab.key}>
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
