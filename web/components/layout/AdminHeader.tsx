"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogoutButton } from "@/components/LogoutButton";

const TITLES: [string, string][] = [
  ["/admin/carteira", "Carteira"],
  ["/admin/fila", "Fila de exceções"],
  ["/admin/achados", "Achados"],
  ["/admin/enviar", "Fila de exceções"],
  ["/admin/fornecedores", "Fornecedores"],
  ["/admin/contratos", "Contratos"],
  ["/admin/configuracoes", "Dados do condomínio"],
  ["/admin/validacao", "Conflitos de dados"],
  ["/admin/relatorios", "Relatórios"],
  ["/admin/conformidade", "Conformidade"],
  ["/admin/pergunte", "Pergunte à IA"],
];
const SUB: [string, string][] = [
  ["/admin/fila/documento", "Corrigir extração"],
  ["/admin/fila/casamento", "Resolver casamento"],
  ["/admin/achados/", "Detalhe do achado"],
  ["/admin/enviar", "Enviar documentos"],
];

/** Header of the app shell (DS §3.1): breadcrumb, page title and the user. */
export function AdminHeader({ companyName, userName }: { companyName: string; userName: string }) {
  const pathname = usePathname();
  const section = TITLES.find(([p]) => pathname.startsWith(p));
  const sub = SUB.find(([p]) => pathname.startsWith(p));
  const sectionHref = section?.[0] === "/admin/enviar" ? "/admin/fila" : section?.[0];
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-line bg-bg/95 px-8 backdrop-blur">
      <nav
        aria-label="Trilha de navegação"
        className="flex items-center gap-1 text-[13px] text-fg-2"
      >
        <span>{companyName}</span>
        {section && (
          <>
            <ChevronRight size={14} aria-hidden />
            {sub && sectionHref ? (
              <Link href={sectionHref} className="hover:text-fg">
                {section[1]}
              </Link>
            ) : (
              <span className="text-fg" aria-current="page">
                {section[1]}
              </span>
            )}
          </>
        )}
        {sub && (
          <>
            <ChevronRight size={14} aria-hidden />
            <span className="text-fg" aria-current="page">
              {sub[1]}
            </span>
          </>
        )}
      </nav>
      <div className="flex items-center gap-3 text-sm">
        <span
          aria-hidden
          className="flex h-8 w-8 items-center justify-center rounded-full bg-elevated text-xs font-semibold"
        >
          {userName
            .split(" ")
            .slice(0, 2)
            .map((p) => p[0])
            .join("")}
        </span>
        <span className="hidden text-fg-2 md:inline">{userName}</span>
        <LogoutButton className="text-[13px] text-fg-2 underline-offset-4 hover:text-fg hover:underline" />
      </div>
    </header>
  );
}
