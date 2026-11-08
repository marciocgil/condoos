import { AlertTriangle, ArrowRight, Hourglass, UserCheck, Users } from "lucide-react";
import Link from "next/link";

import { Card, CardTitle } from "@/components/ui/Card";
import { formatDate } from "@/lib/format";
import type { BoardMine, BoardOthers, DelegationBoard as Board } from "@/lib/types";

const MINE_LABEL: Record<BoardMine["kind"], string> = {
  autorizar: "Autorizar o pedido",
  enviar_link: "Enviar o link",
  conferir: "Conferir os arquivos recebidos",
};

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

function OthersLine({ entry, base }: { entry: BoardOthers; base: string }) {
  if (entry.kind === "equipe") {
    const parts = [
      entry.documents > 0 &&
        plural(entry.documents, "documento em conferência", "documentos em conferência"),
      entry.conflicts > 0 &&
        plural(entry.conflicts, "divergência em validação", "divergências em validação"),
    ].filter(Boolean);
    return (
      <li className="flex items-start gap-2 py-2">
        <Users size={16} aria-hidden className="mt-0.5 shrink-0 text-fg-2" />
        <span>
          <span className="font-medium">Equipe CondoOS</span>
          <span className="block text-[13px] text-fg-2">{parts.join(" · ")}</span>
        </span>
      </li>
    );
  }
  return (
    <li>
      <Link
        href={`${base}/${entry.request_id}`}
        className="transition-ui flex items-start gap-2 py-2 hover:text-fg"
      >
        {entry.late ? (
          <AlertTriangle size={16} aria-hidden className="mt-0.5 shrink-0 text-warning" />
        ) : (
          <Hourglass size={16} aria-hidden className="mt-0.5 shrink-0 text-fg-2" />
        )}
        <span>
          <span className="font-medium">{entry.recipient_name}</span>
          <span className="block text-[13px] text-fg-2">
            {entry.progress.attended} de {entry.progress.total} recebidos ·{" "}
            {entry.late ? "prazo vencido em " : "prazo "}
            {formatDate(entry.due_date)}
          </span>
        </span>
      </Link>
    </li>
  );
}

/** Hoje (LB-044): what waits for you × what is with others, from the requests and documents
 * at each read. Hidden when there is nothing on either side. */
export function DelegationBoard({ condominiumId, board }: { condominiumId: string; board: Board }) {
  if (board.mine.length === 0 && board.others.length === 0) return null;
  const base = `/condominio/${condominiumId}/pedidos`;
  return (
    <Card aria-label="Com você e com outros">
      <CardTitle
        action={
          <Link href={base} className="text-[13px] text-fg-2 hover:text-fg">
            Pedidos
          </Link>
        }
      >
        Pedidos de documentos
      </CardTitle>
      <div className="grid gap-4 sm:grid-cols-2">
        <section aria-label="Com você">
          <h3 className="text-[13px] font-medium text-fg-2">Com você</h3>
          {board.mine.length === 0 ? (
            <p className="py-2 text-sm text-fg-2">Nada esperando por você.</p>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {board.mine.map((m) => (
                <li key={`${m.kind}-${m.request_id}`}>
                  <Link
                    href={`${base}/${m.request_id}`}
                    className="transition-ui flex items-start gap-2 py-2 hover:text-fg"
                  >
                    <UserCheck size={16} aria-hidden className="mt-0.5 shrink-0 text-fg-2" />
                    <span className="flex-1">
                      <span className="font-medium">{MINE_LABEL[m.kind]}</span>
                      <span className="block text-[13px] text-fg-2">
                        {m.recipient_name}
                        {m.kind === "conferir" &&
                          ` · ${plural(m.received, "arquivo recebido", "arquivos recebidos")}`}
                      </span>
                    </span>
                    <ArrowRight size={14} aria-hidden className="mt-1 shrink-0 text-muted" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-label="Com outros">
          <h3 className="text-[13px] font-medium text-fg-2">Com outros</h3>
          {board.others.length === 0 ? (
            <p className="py-2 text-sm text-fg-2">Ninguém está com algo seu agora.</p>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {board.others.map((o) => (
                <OthersLine
                  key={o.kind === "equipe" ? "equipe" : o.request_id}
                  entry={o}
                  base={base}
                />
              ))}
            </ul>
          )}
        </section>
      </div>
    </Card>
  );
}
