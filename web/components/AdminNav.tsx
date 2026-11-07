"use client";

import {
  BarChart3,
  Building2,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  FileSignature,
  FolderKanban,
  Inbox,
  LayoutGrid,
  MessageSquare,
  PiggyBank,
  Settings,
  Store,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/layout/Logo";
import { cx } from "@/components/ui/cx";

const ITEMS = [
  { href: "/admin/carteira", label: "Carteira", icon: LayoutGrid },
  { href: "/admin/fila", label: "Fila de exceções", icon: Inbox, counter: true },
  { href: "/admin/assuntos", label: "Assuntos", icon: FolderKanban },
  { href: "/admin/oportunidades", label: "Oportunidades", icon: PiggyBank },
  { href: "/admin/pendencias", label: "Pendências", icon: ClipboardList },
  { href: "/admin/agenda", label: "Agenda", icon: CalendarDays },
  { href: "/admin/fornecedores", label: "Fornecedores", icon: Store },
  { href: "/admin/contratos", label: "Contratos", icon: FileSignature },
  { href: "/admin/metricas", label: "Métricas do piloto", icon: BarChart3 },
  { href: "/admin/configuracoes", label: "Configurações", icon: Settings },
] as const;

const STORAGE_KEY = "condoos.sidebar.collapsed";

/** Sidebar of the app shell (DS §3.1): 232 px expanded, 64 px collapsed. */
export function AdminNav({ queueCount, companyName }: { queueCount: number; companyName: string }) {
  const pathname = usePathname();
  // The condominium chosen in a screen's filter follows to the other screens.
  const condo = useSearchParams().get("condominio");
  const withCondo = (href: string) => (condo ? `${href}?condominio=${condo}` : href);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      /* storage unavailable: keep expanded */
    }
  }, []);
  function toggle() {
    setCollapsed((c) => {
      try {
        window.localStorage.setItem(STORAGE_KEY, c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });
  }
  return (
    <aside
      className={cx(
        "transition-ui sticky top-0 flex h-dvh shrink-0 flex-col border-r border-line bg-bg-2",
        collapsed ? "w-16" : "w-[232px]",
      )}
    >
      <div className="flex h-16 items-center px-4">
        <Logo compact={collapsed} />
      </div>
      {!collapsed && (
        <div className="mx-3 mb-4 flex items-center gap-2 rounded-[var(--radius-control)] border border-line px-3 py-2 text-[13px] text-fg-2">
          <Building2 size={16} aria-hidden />
          <span className="truncate" title={companyName}>
            {companyName}
          </span>
        </div>
      )}
      <nav aria-label="Menu da administradora" className="flex-1 px-3">
        <ul className="space-y-1">
          {ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={withCondo(item.href)}
                  aria-current={active ? "page" : undefined}
                  title={collapsed ? item.label : undefined}
                  className={cx(
                    "transition-ui flex h-10 items-center gap-3 rounded-[var(--radius-control)] px-3 text-sm",
                    active
                      ? "bg-surface font-medium text-fg"
                      : "text-fg-2 hover:bg-surface hover:text-fg",
                  )}
                >
                  <Icon size={18} aria-hidden className={active ? "text-accent" : undefined} />
                  {!collapsed && <span className="flex-1">{item.label}</span>}
                  {"counter" in item && queueCount > 0 && (
                    <span
                      className="tabular rounded-full border border-warning/70 px-2 text-xs text-warning"
                      aria-label={`${queueCount} itens na fila`}
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
      <div className="space-y-2 p-3">
        <Link
          href={withCondo("/admin/pergunte")}
          className="transition-ui flex h-10 items-center justify-center gap-2 rounded-[var(--radius-button)] border border-control text-sm text-fg-2 hover:text-fg"
          title="Pergunte à IA"
        >
          <MessageSquare size={16} aria-hidden />
          {!collapsed && "Pergunte à IA"}
        </Link>
        <button
          type="button"
          onClick={toggle}
          className="transition-ui flex h-8 w-full items-center justify-center rounded-[var(--radius-control)] text-muted hover:text-fg"
          aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
