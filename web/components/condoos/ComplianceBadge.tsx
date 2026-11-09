import {
  Archive,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  FileQuestion,
  FileSearch,
  HelpCircle,
  ShieldAlert,
  TimerReset,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { ComplianceCode, ComplianceSituation } from "@/lib/types";

const LOOK: Record<ComplianceCode, { tone: BadgeTone; icon: ReactNode }> = {
  vencido: { tone: "danger", icon: <ShieldAlert size={12} /> },
  vence_em_breve: { tone: "warning", icon: <TimerReset size={12} /> },
  sem_documento: { tone: "warning", icon: <FileQuestion size={12} /> },
  sem_validade: { tone: "info", icon: <HelpCircle size={12} /> },
  lendo: { tone: "info", icon: <FileSearch size={12} /> },
  a_validar: { tone: "neutral", icon: <CircleDashed size={12} /> },
  em_dia: { tone: "success", icon: <CheckCircle2 size={12} /> },
  nao_aplicavel: { tone: "neutral", icon: <CircleSlash size={12} /> },
  arquivada: { tone: "neutral", icon: <Archive size={12} /> },
};

/** Situation of a compliance obligation (D112): always text and icon, never colour alone. */
export function ComplianceBadge({ situation }: { situation: ComplianceSituation }) {
  const look = LOOK[situation.code];
  return (
    <Badge tone={look.tone} icon={look.icon}>
      {situation.label}
    </Badge>
  );
}
