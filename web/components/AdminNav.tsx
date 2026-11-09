"use client";

import {
  BarChart3,
  CheckSquare,
  Building2,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  FileSignature,
  FileText,
  FolderKanban,
  GitCompare,
  Inbox,
  Send,
  LayoutGrid,
  MessageSquare,
  PiggyBank,
  Settings,
  Store,
  Sun,
  ShieldAlert,
  ShieldCheck,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/layout/Logo";
import { cx } from "@/components/ui/cx";

/** Who is looking: decides which items show (D111: each role sees what it uses). */
export type NavAccess = {
  permissions: string[]; // union of the user's permissions over its condominiums
  platform: boolean; // CondoOS staff (D77)
};

type Item = {
  href: string;
  label: string;
  icon: typeof Sun;
  counter?: boolean;
  show?: (a: NavAccess) => boolean;
};
type Group = { title: string | null; items: Item[] };

const can =
  (...perms: string[]) =>
  (a: NavAccess) =>
    perms.some((p) => a.permissions.includes(p));

/** Menu by purpose (D111, docs/proposta-menu.md): what to look at every day first, then the
 * groups in order of use. Labels say what each item is for. */
const GROUPS: Group[] = [
  {
    title: null,
    items: [
      { href: "/admin/hoje", label: "Hoje", icon: Sun },
      { href: "/admin/carteira", label: "Carteira", icon: LayoutGrid },
      { href: "/admin/agenda", label: "Agenda", icon: CalendarDays },
    ],
  },
  {
    title: "Gestão financeira",
    items: [
      { href: "/admin/achados", label: "Achados", icon: ShieldAlert },
      { href: "/admin/aprovacoes", label: "Aprovações", icon: CheckSquare },
      { href: "/admin/oportunidades", label: "Oportunidades", icon: PiggyBank },
      {
        href: "/admin/pendencias",
        label: "Pendências",
        icon: ClipboardList,
        show: can("view_pending_findings"),
      },
      { href: "/admin/relatorios", label: "Relatórios", icon: FileText, show: can("export") },
    ],
  },
  {
    title: "Gestão operacional",
    items: [
      { href: "/admin/assuntos", label: "Assuntos", icon: FolderKanban },
      { href: "/admin/conformidade", label: "Conformidade", icon: ShieldCheck },
      { href: "/admin/pedidos", label: "Pedidos de documentos", icon: Send },
    ],
  },
  {
    title: "Contratos e documentos",
    items: [
      { href: "/admin/contratos", label: "Contratos", icon: FileSignature },
      { href: "/admin/fornecedores", label: "Fornecedores", icon: Store },
      {
        href: "/admin/enviar",
        label: "Enviar documentos",
        icon: Upload,
        show: can("upload_document"),
      },
    ],
  },
  {
    title: "Qualidade dos dados",
    items: [
      {
        href: "/admin/fila",
        label: "Fila de exceções",
        icon: Inbox,
        counter: true,
        show: can("correct_extraction", "validate_finding"),
      },
      {
        href: "/admin/validacao",
        label: "Conflitos de dados",
        icon: GitCompare,
        show: can("correct_extraction"),
      },
    ],
  },
  {
    title: "Cadastro e configurações",
    items: [
      {
        href: "/admin/configuracoes",
        label: "Dados do condomínio",
        icon: Settings,
        show: can("configure", "configure_policy", "manage_platform"),
      },
      {
        href: "/admin/metricas",
        label: "Métricas do piloto",
        icon: BarChart3,
        show: (a) => a.platform,
      },
    ],
  },
];

const STORAGE_KEY = "condoos.sidebar.collapsed";

/** Sidebar of the app shell (DS §3.1): 232 px expanded, 64 px collapsed. */
export function AdminNav({
  queueCount,
  companyName,
  access,
}: {
  queueCount: number;
  companyName: string;
  access: NavAccess;
}) {
  const groups = GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => !i.show || i.show(access)),
  })).filter((g) => g.items.length > 0);
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
      <nav aria-label="Menu da administradora" className="flex-1 overflow-y-auto px-3">
        {groups.map((group) => (
          <div key={group.title ?? "topo"} className={group.title ? "mt-4" : undefined}>
            {group.title &&
              (collapsed ? (
                <hr className="mx-2 mb-2 border-line" />
              ) : (
                <p className="mb-1 px-3 text-[11px] font-medium tracking-wide text-muted uppercase">
                  {group.title}
                </p>
              ))}
            <ul className="space-y-1" aria-label={group.title ?? "Principal"}>
              {group.items.map((item) => {
                const active = pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={withCondo(item.href)}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={cx(
                        "transition-ui flex h-9 items-center gap-3 rounded-[var(--radius-control)] px-3 text-sm",
                        active
                          ? "bg-surface font-medium text-fg"
                          : "text-fg-2 hover:bg-surface hover:text-fg",
                      )}
                    >
                      <Icon size={18} aria-hidden className={active ? "text-accent" : undefined} />
                      {!collapsed && <span className="flex-1">{item.label}</span>}
                      {item.counter && queueCount > 0 && (
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
          </div>
        ))}
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
