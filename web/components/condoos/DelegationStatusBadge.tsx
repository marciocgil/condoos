import { Ban, CheckCircle2, Clock, FileEdit, Inbox, Send, TimerOff, XCircle } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { DelegationStatus } from "@/lib/types";

const STATUS: Record<DelegationStatus, { label: string; tone: BadgeTone; icon: React.ReactNode }> =
  {
    rascunho: { label: "Rascunho", tone: "neutral", icon: <FileEdit size={12} /> },
    autorizado: { label: "Autorizado", tone: "info", icon: <CheckCircle2 size={12} /> },
    aguardando_envio: { label: "Aguardando envio", tone: "warning", icon: <Clock size={12} /> },
    recebendo: { label: "Recebendo arquivos", tone: "info", icon: <Inbox size={12} /> },
    concluido: { label: "Concluído", tone: "success", icon: <CheckCircle2 size={12} /> },
    encerrado: { label: "Encerrado", tone: "neutral", icon: <XCircle size={12} /> },
    expirado: { label: "Link vencido", tone: "neutral", icon: <TimerOff size={12} /> },
    revogado: { label: "Revogado", tone: "danger", icon: <Ban size={12} /> },
  };

export function DelegationStatusBadge({ status }: { status: DelegationStatus }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone} icon={s.icon}>
      {s.label}
    </Badge>
  );
}

export const SHARED_ICON = <Send size={12} />;
