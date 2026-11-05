"use client";

import { MessageSquare } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

/** "Pergunte ao CondoOS" — always visible; carries what the user is looking at (screen
 * context), so "explique este achado" answers about the open finding. */
export function AskButton({ condominiumId }: { condominiumId: string }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const base = `/condominio/${condominiumId}`;
  if (pathname.startsWith(`${base}/pergunte`)) return null;

  const rest = pathname.slice(base.length + 1).split("/");
  const params = new URLSearchParams();
  if (rest[0] === "achados" && rest[1]) {
    params.set("tela", "achado");
    params.set("achado", rest[1]);
  } else if (["resumo", "achados", "contratos", "historico"].includes(rest[0] ?? "")) {
    params.set("tela", rest[0] as string);
  }
  const competence = search.get("competencia");
  if (competence) params.set("competencia", competence);
  const query = params.toString();

  return (
    <Link
      href={`${base}/pergunte${query ? `?${query}` : ""}`}
      className="transition-ui fixed right-4 bottom-20 z-20 inline-flex h-11 items-center gap-2 rounded-full border border-info/70 bg-bg-2 px-4 text-sm font-medium text-fg shadow-lg hover:bg-surface"
    >
      <MessageSquare size={16} aria-hidden className="text-info" />
      Pergunte ao CondoOS
    </Link>
  );
}
