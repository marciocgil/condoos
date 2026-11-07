import {
  Ban,
  CheckCircle2,
  CircleDashed,
  Hand,
  Hourglass,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { ACTION_STATUS_LABEL } from "@/lib/labels";

const TONE: Record<string, BadgeTone> = {
  aguardando_aprovacao: "warning",
  enfileirada: "info",
  aguardando_execucao_manual: "info",
  executada: "success",
  recusada: "neutral",
  cancelada: "neutral",
  bloqueada: "danger",
};
const ICON: Record<string, React.ReactNode> = {
  aguardando_aprovacao: <Hourglass size={12} />,
  enfileirada: <CircleDashed size={12} />,
  aguardando_execucao_manual: <Hand size={12} />,
  executada: <CheckCircle2 size={12} />,
  recusada: <XCircle size={12} />,
  cancelada: <Ban size={12} />,
  bloqueada: <ShieldAlert size={12} />,
};

export function ActionStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={TONE[status] ?? "neutral"} icon={ICON[status] ?? <CircleDashed size={12} />}>
      {ACTION_STATUS_LABEL[status] ?? status}
    </Badge>
  );
}
