import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Clock,
  Hammer,
  Hourglass,
  PauseCircle,
  RotateCcw,
  Search,
  ShieldQuestion,
  Users,
  XCircle,
  ClipboardList,
} from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { CASE_ATTENTION_LABEL, CASE_STATUS_LABEL } from "@/lib/labels";

const TONE: Record<string, BadgeTone> = {
  novo: "accent",
  em_triagem: "info",
  em_planejamento: "info",
  aguardando_aprovacao: "warning",
  em_execucao: "info",
  aguardando_terceiro: "warning",
  aguardando_validacao: "warning",
  resolvido: "success",
  cancelado: "neutral",
  reaberto: "warning",
  suspenso_justificadamente: "neutral",
};
const ICON: Record<string, React.ReactNode> = {
  novo: <CircleDashed size={12} />,
  em_triagem: <Search size={12} />,
  em_planejamento: <ClipboardList size={12} />,
  aguardando_aprovacao: <ShieldQuestion size={12} />,
  em_execucao: <Hammer size={12} />,
  aguardando_terceiro: <Users size={12} />,
  aguardando_validacao: <Hourglass size={12} />,
  resolvido: <CheckCircle2 size={12} />,
  cancelado: <XCircle size={12} />,
  reaberto: <RotateCcw size={12} />,
  suspenso_justificadamente: <PauseCircle size={12} />,
};

/** State of a case: always text and icon (DS: status never by colour alone). */
export function CaseStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={TONE[status] ?? "neutral"} icon={ICON[status] ?? <Clock size={12} />}>
      {CASE_STATUS_LABEL[status] ?? status}
    </Badge>
  );
}

/** "Sem próxima ação, sem controle" (spec §8.4): what needs attention in an open case. */
export function CaseAttention({ flags }: { flags: string[] }) {
  if (flags.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {flags.map((f) => (
        <Badge key={f} tone="danger" icon={<AlertTriangle size={12} />}>
          {CASE_ATTENTION_LABEL[f] ?? f}
        </Badge>
      ))}
    </span>
  );
}
