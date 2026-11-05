"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { slug: "resumo", label: "Resumo" },
  { slug: "achados", label: "Achados" },
  { slug: "contratos", label: "Contratos" },
  { slug: "historico", label: "Histórico" },
] as const;

export function BottomTabs({ condominiumId }: { condominiumId: string }) {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-10 border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="mx-auto grid max-w-md grid-cols-4">
        {TABS.map((tab) => {
          const href = `/condominio/${condominiumId}/${tab.slug}`;
          const active = pathname.startsWith(href);
          return (
            <li key={tab.slug}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`block py-3 text-center text-sm ${
                  active ? "font-semibold text-brand-700" : "text-gray-500"
                }`}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
