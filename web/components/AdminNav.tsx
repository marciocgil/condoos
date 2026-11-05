"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/admin/carteira", label: "Carteira" },
  { href: "/admin/fila", label: "Fila de exceções", counter: true },
  { href: "/admin/fornecedores", label: "Fornecedores" },
  { href: "/admin/contratos", label: "Contratos" },
  { href: "/admin/configuracoes", label: "Configurações" },
  { href: "/admin/pergunte", label: "Pergunte à IA" },
] as const;

export function AdminNav({ queueCount }: { queueCount: number }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Menu da administradora">
      <ul className="space-y-1">
        {ITEMS.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
                  active
                    ? "bg-brand-700 font-medium text-white"
                    : "text-brand-100 hover:bg-brand-700/60"
                }`}
              >
                {item.label}
                {"counter" in item && (
                  <span
                    className="rounded-full bg-white/20 px-2 text-xs"
                    aria-label="itens na fila"
                  >
                    {queueCount}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
