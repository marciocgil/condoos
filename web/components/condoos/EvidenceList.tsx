import { Banknote, FileSignature, FileText, Receipt, Store, UserRound } from "lucide-react";

import { formatBRL } from "@/lib/format";
import type { Evidence } from "@/lib/types";

/** Evidence labels keep machine values ("R$ 6200.00", checked by the explanation validator);
 * shown in the Brazilian format. */
function humanize(text: string): string {
  return text.replace(/R\$ (-?\d+\.\d{2})\b/g, (_, v: string) => formatBRL(v));
}

const ICON: Record<string, React.ReactNode> = {
  document: <FileText size={16} />,
  expense: <Receipt size={16} />,
  bank_transaction: <Banknote size={16} />,
  contract: <FileSignature size={16} />,
  supplier: <Store size={16} />,
  board_member: <UserRound size={16} />,
};

/** Evidence list: every item says where it comes from; documents open the original file. */
export function EvidenceList({ items }: { items: Evidence[] }) {
  return (
    <ul className="space-y-2" aria-label="Evidências">
      {items.map((e, i) => {
        const body = (
          <>
            <span aria-hidden className="mt-0.5 text-fg-2">
              {ICON[e.kind] ?? <FileText size={16} />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="tabular block text-sm">{humanize(e.label)}</span>
              {e.excerpt && (
                <span className="mt-0.5 block text-[13px] break-words text-fg-2">
                  {humanize(e.excerpt)}
                </span>
              )}
            </span>
          </>
        );
        const cls =
          "flex items-start gap-3 rounded-[var(--radius-card)] border border-line bg-bg-2 px-4 py-3";
        return (
          <li key={`${e.kind}-${e.id}-${i}`}>
            {e.file_url ? (
              <a
                href={e.page ? `${e.file_url}#page=${e.page}` : e.file_url}
                target="_blank"
                rel="noreferrer"
                className={`${cls} transition-ui hover:border-control`}
              >
                {body}
                <span className="text-xs text-accent">Abrir documento</span>
              </a>
            ) : (
              <div className={cls}>{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
