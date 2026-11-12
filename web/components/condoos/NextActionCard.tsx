import { ArrowRightCircle, Ban, CirclePause, ShieldCheck, UserCheck } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { NextAction } from "@/lib/types";

const STATE: Record<
  NextAction["authorization"],
  { label: string; tone: BadgeTone; icon: typeof ShieldCheck }
> = {
  require_approval: { label: "Precisa da aprovação do síndico", tone: "warning", icon: UserCheck },
  require_review: { label: "Precisa de revisão antes", tone: "warning", icon: UserCheck },
  deny: { label: "Não permitido pela política", tone: "danger", icon: Ban },
  pause: { label: "Pausado neste condomínio", tone: "neutral", icon: CirclePause },
  allow: { label: "Permitido", tone: "success", icon: ShieldCheck },
  interna: { label: "Passo interno, nada sai do CondoOS", tone: "info", icon: ShieldCheck },
};

/** Next step of a finding (FR-033, D126): what, why, on which evidence and whether it is
 * authorised. Proposing is not doing: nothing is sent from here. */
export function NextActionCard({ action }: { action: NextAction }) {
  const s = STATE[action.authorization] ?? STATE.interna;
  const Icon = s.icon;
  return (
    <section
      aria-labelledby="next-action"
      className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
      data-testid="next-action"
    >
      <h2 id="next-action" className="mb-1 flex items-center gap-2 text-base font-semibold">
        <ArrowRightCircle size={18} aria-hidden /> Próxima ação proposta
      </h2>
      <p className="font-medium">{action.title}</p>
      <p className="mt-1 text-[13px] text-fg-2">{action.why}</p>
      <div className="mt-2">
        <Badge tone={s.tone} icon={<Icon size={12} aria-hidden />}>
          {s.label}
        </Badge>
        <p className="mt-1 text-[12px] text-muted">
          {action.authorization_text} (política v{action.policy_version})
        </p>
      </div>
      {action.evidence.length > 0 && (
        <p className="mt-2 text-[12px] text-muted">
          Com base em: {action.evidence.map((e) => e.label).join("; ")}
        </p>
      )}
    </section>
  );
}
