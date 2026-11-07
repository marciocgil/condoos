import {
  CheckCircle2,
  CircleDashed,
  Eye,
  Hammer,
  Hourglass,
  RotateCcw,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { OPPORTUNITY_STATUS_LABEL } from "@/lib/labels";

const TONE: Record<string, BadgeTone> = {
  identificada: "neutral",
  em_revisao_interna: "warning",
  devolvida: "warning",
  rejeitada: "neutral",
  aprovada_para_cliente: "accent",
  aprovada_pelo_condominio: "success",
  recusada_pelo_condominio: "neutral",
  em_execucao: "info",
  implementada: "success",
  resultado_medido: "success",
  encerrada: "neutral",
};
const ICON: Record<string, React.ReactNode> = {
  identificada: <CircleDashed size={12} />,
  em_revisao_interna: <Hourglass size={12} />,
  devolvida: <RotateCcw size={12} />,
  rejeitada: <XCircle size={12} />,
  aprovada_para_cliente: <Eye size={12} />,
  aprovada_pelo_condominio: <ShieldCheck size={12} />,
  recusada_pelo_condominio: <XCircle size={12} />,
  em_execucao: <Hammer size={12} />,
  implementada: <CheckCircle2 size={12} />,
  resultado_medido: <CheckCircle2 size={12} />,
  encerrada: <CheckCircle2 size={12} />,
};

export function OpportunityStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={TONE[status] ?? "neutral"} icon={ICON[status] ?? <CircleDashed size={12} />}>
      {OPPORTUNITY_STATUS_LABEL[status] ?? status}
    </Badge>
  );
}
