import { Building2, MessageSquare } from "lucide-react";
import Link from "next/link";

import { ChatPanel } from "@/components/condoos/ChatPanel";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { ChatMessage, Portfolio } from "@/lib/types";

/** "Pergunte à IA" for the management company: one condominium at a time, chosen here.
 * The assistant never mixes condominiums; switching starts that condominium's own chat. */
export default async function PerguntePage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const sp = await searchParams;
  const p = await apiGet<Portfolio>("/portfolio");
  const condos = [...p.condominiums].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  const current = condos.find((c) => c.id === sp.condominio) ?? condos[0];
  if (!current) {
    return (
      <EmptyState icon={<MessageSquare size={28} />} title="Nenhum condomínio na carteira">
        O assistente responde com os dados de cada condomínio da carteira.
      </EmptyState>
    );
  }
  const history = await apiGet<ChatMessage[]>(`/condominiums/${current.id}/chat`);
  return (
    <div className="mx-auto max-w-3xl">
      <nav aria-label="Condomínio da conversa" className="mb-5">
        <p className="mb-2 text-xs font-medium tracking-wide text-fg-2 uppercase">Condomínio</p>
        <ul className="flex flex-wrap gap-2">
          {condos.map((c) => {
            const active = c.id === current.id;
            return (
              <li key={c.id}>
                <Link
                  href={`/admin/pergunte?condominio=${c.id}`}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "transition-ui inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm",
                    active
                      ? "border-accent/70 bg-surface font-medium text-fg"
                      : "border-line text-fg-2 hover:border-control hover:text-fg",
                  )}
                >
                  <Building2 size={14} aria-hidden className={active ? "text-accent" : undefined} />
                  {c.name}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <ChatPanel
        key={current.id}
        condominiumId={current.id}
        condominiumName={current.name}
        initial={history}
        screen={{ screen: "carteira" }}
        variant="admin"
      />
    </div>
  );
}
