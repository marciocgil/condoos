import { Ban, CheckCircle2, CircleDashed, CircleSlash, Clock, TriangleAlert } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { ControlStatusCode } from "@/lib/types";

const STYLE: Record<ControlStatusCode, { tone: BadgeTone; label: string; icon: typeof Clock }> = {
  VALIDADO: { tone: "success", label: "Validado", icon: CheckCircle2 },
  COM_RESSALVA: { tone: "warning", label: "Com ressalva", icon: TriangleAlert },
  PENDENTE: { tone: "info", label: "Pendente", icon: Clock },
  DIVERGENTE: { tone: "danger", label: "Divergente", icon: Ban },
  NAO_AVALIADO: { tone: "neutral", label: "Não avaliado", icon: CircleDashed },
  NAO_APLICAVEL: { tone: "neutral", label: "Não aplicável", icon: CircleSlash },
};

/** The six states of the farol (D122): always text and icon, never colour alone. */
export function ControlStatusBadge({ status }: { status: ControlStatusCode | null | undefined }) {
  if (!status) return <Badge tone="neutral">Sem execução</Badge>;
  const s = STYLE[status];
  const Icon = s.icon;
  return (
    <Badge tone={s.tone} icon={<Icon size={12} aria-hidden />}>
      {s.label}
    </Badge>
  );
}
