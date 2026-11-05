import {
  CheckCircle2,
  Clock,
  EyeOff,
  MessageSquareWarning,
  RefreshCcw,
  Sparkles,
  XCircle,
} from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { STATUS_LABEL } from "@/lib/labels";
import type { FindingStatus } from "@/lib/types";

const TONE: Record<FindingStatus, BadgeTone> = {
  aguardando_validacao: "warning",
  publicado: "accent",
  confirmado: "success",
  contestado: "info",
  ignorado: "neutral",
  descartado: "neutral",
  superado: "neutral",
};
const ICON: Record<FindingStatus, React.ReactNode> = {
  aguardando_validacao: <Clock size={12} />,
  publicado: <Sparkles size={12} />,
  confirmado: <CheckCircle2 size={12} />,
  contestado: <MessageSquareWarning size={12} />,
  ignorado: <EyeOff size={12} />,
  descartado: <XCircle size={12} />,
  superado: <RefreshCcw size={12} />,
};

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return (
    <Badge tone={TONE[status]} icon={ICON[status]}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
