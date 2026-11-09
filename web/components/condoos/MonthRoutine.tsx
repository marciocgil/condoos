import { CheckCircle2, FileText, Gavel, Lock } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatMonth } from "@/lib/format";
import type { LaunchMonth } from "@/lib/types";

const ICON: Record<string, ReactNode> = {
  documentos: <FileText size={16} aria-hidden className="text-info" />,
  decisoes: <Gavel size={16} aria-hidden className="text-info" />,
  fechamento: <Lock size={16} aria-hidden className="text-info" />,
};

/** "Seu mês" on the síndico's Hoje (LB-082, D108): at most three things about the previous
 * month, built by the API from records. An item without anything pending is not listed. */
export function MonthRoutine({
  condominiumId,
  routine,
}: {
  condominiumId: string;
  routine: LaunchMonth;
}) {
  if (!routine.active) return null;
  return (
    <Card aria-labelledby="month-title" data-testid="month-routine">
      <h2 id="month-title" className="text-[15px] font-semibold">
        Seu mês: {formatMonth(`${routine.month}-01`)}
      </h2>
      {routine.items.length === 0 ? (
        <p className="mt-2 flex items-center gap-2 text-sm">
          <CheckCircle2 size={14} aria-hidden className="text-success" /> Nada pendente neste mês.
        </p>
      ) : (
        <ol className="mt-3 space-y-4">
          {routine.items.map((item, i) => (
            <li key={item.key} className="flex gap-3" data-testid={`month-${item.key}`}>
              <span className="mt-0.5 shrink-0">{ICON[item.key]}</span>
              <div className="min-w-0">
                <p className="text-sm font-medium">{item.title}</p>
                <p className="text-sm text-fg-2">{item.detail}</p>
                {item.actions.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {item.actions.map((a) => (
                      <Link
                        key={a.href}
                        href={`/condominio/${condominiumId}/${a.href}`}
                        // One primary action on the card: the first item's.
                        className={buttonClass(
                          a.primary && i === 0 ? "primary" : "secondary",
                          "sm",
                        )}
                      >
                        {a.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
