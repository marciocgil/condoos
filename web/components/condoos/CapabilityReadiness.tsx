import { ArrowRight, CheckCircle2, CircleDashed, CircleDot } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { formatDateTime } from "@/lib/format";
import type { CapabilityChange, CapabilityReadiness, ReadinessState } from "@/lib/types";

const HISTORY_SHOWN = 5;

const READINESS: Record<ReadinessState, { tone: BadgeTone; icon: React.ReactNode }> = {
  nao_configurado: { tone: "neutral", icon: <CircleDashed size={12} /> },
  analise_parcial: { tone: "warning", icon: <CircleDot size={12} /> },
  supervisionada: { tone: "success", icon: <CheckCircle2 size={12} /> },
};

/** What each capability can do with the data the condominium has, and what is missing
 * (Launch, D89). Status always with text and icon. */
export function CapabilityReadinessList({ items }: { items: CapabilityReadiness[] }) {
  return (
    <ul className="space-y-3" aria-label="Prontidão por função">
      {items.map((r) => (
        <li key={r.key} data-testid={`readiness-${r.key}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{r.title}</span>
            <Badge tone={READINESS[r.state].tone} icon={READINESS[r.state].icon}>
              {r.state_label}
            </Badge>
          </div>
          {r.missing.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-[13px] text-fg-2">
              {r.missing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Recent changes of state (LB-064, D109): what changed, when and why. */
function CapabilityHistory({ changes }: { changes: CapabilityChange[] }) {
  const shown = changes.filter((c) => c.from !== null).slice(0, HISTORY_SHOWN);
  return (
    <div className="mt-4 border-t border-line pt-3" data-testid="capability-history">
      <h3 className="text-[13px] font-medium text-fg-2">Mudanças recentes</h3>
      {shown.length === 0 ? (
        <p className="mt-1 text-[13px] text-fg-2">Nenhuma mudança desde a primeira verificação.</p>
      ) : (
        <ul className="mt-1 space-y-2 text-[13px]">
          {shown.map((c) => (
            <li key={`${c.at}-${c.key}`}>
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium">{c.title}</span>
                <span className="text-fg-2">{c.from_label}</span>
                <ArrowRight size={12} aria-label="para" className="text-muted" />
                <Badge tone={READINESS[c.to].tone} icon={READINESS[c.to].icon}>
                  {c.to_label}
                </Badge>
              </span>
              <span className="block text-fg-2">
                {formatDateTime(c.at)} · {c.reason}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The same list as a card, for Ajustes (síndico) and Configurações (management), with the
 * recent changes when given. */
export function CapabilityReadinessCard({
  items,
  history,
}: {
  items: CapabilityReadiness[];
  history?: CapabilityChange[];
}) {
  return (
    <Card aria-labelledby="readiness-title">
      <CardTitle>
        <span id="readiness-title">O que já funciona</span>
      </CardTitle>
      <CapabilityReadinessList items={items} />
      {history && <CapabilityHistory changes={history} />}
      <p className="mt-3 text-[12px] text-muted">
        Calculado a partir dos documentos e dados do condomínio. Toda ação continua precisando da
        aprovação do síndico.
      </p>
    </Card>
  );
}
