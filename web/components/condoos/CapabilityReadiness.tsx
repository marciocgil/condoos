import { CheckCircle2, CircleDashed, CircleDot } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import type { CapabilityReadiness, ReadinessState } from "@/lib/types";

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

/** The same list as a card, for Ajustes (síndico) and Configurações (management). */
export function CapabilityReadinessCard({ items }: { items: CapabilityReadiness[] }) {
  return (
    <Card aria-labelledby="readiness-title">
      <CardTitle>
        <span id="readiness-title">O que já funciona</span>
      </CardTitle>
      <CapabilityReadinessList items={items} />
      <p className="mt-3 text-[12px] text-muted">
        Calculado a partir dos documentos e dados do condomínio. Toda ação continua precisando da
        aprovação do síndico.
      </p>
    </Card>
  );
}
