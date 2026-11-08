import {
  AlertTriangle,
  BellRing,
  CalendarClock,
  CalendarX,
  CheckCircle2,
  Clock,
  FileQuestion,
  FileSearch,
  Search,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { formatBRL } from "@/lib/format";
import type { AgendaEvent, AgendaKind } from "@/lib/types";

export const KIND_LABEL: Record<AgendaKind, string> = {
  vencimento: "Vencimentos",
  nf_prevista: "NF dos contratos",
  reajuste: "Reajustes",
  aviso_previo: "Aviso prévio",
  fim_contrato: "Fim de contrato",
};

type Look = { label: string; tone: BadgeTone; icon: ReactNode };

/** Status of an agenda item: always text and icon, never color alone (DS). */
export function agendaStatus(e: AgendaEvent): Look {
  const key = `${e.kind}:${e.status}`;
  const map: Record<string, Look> = {
    "vencimento:pago": { label: "Pago", tone: "success", icon: <CheckCircle2 size={12} /> },
    "vencimento:vencido": {
      label: "Vencido sem pagamento",
      tone: "danger",
      icon: <AlertTriangle size={12} />,
    },
    "vencimento:a_vencer": { label: "A vencer", tone: "info", icon: <Clock size={12} /> },
    "nf_prevista:recebida": {
      label: "NF recebida",
      tone: "success",
      icon: <CheckCircle2 size={12} />,
    },
    "nf_prevista:prevista": {
      label: "NF prevista",
      tone: "neutral",
      icon: <CalendarClock size={12} />,
    },
    "nf_prevista:em_conferencia": {
      label: "NF chegou, em conferência",
      tone: "info",
      icon: <FileSearch size={12} />,
    },
    "nf_prevista:nao_chegou": {
      label: "NF não chegou",
      tone: "warning",
      icon: <FileQuestion size={12} />,
    },
    "reajuste:previsto": {
      label: "Reajuste previsto",
      tone: "neutral",
      icon: <TrendingUp size={12} />,
    },
    "reajuste:conferir": { label: "Conferir reajuste", tone: "info", icon: <Search size={12} /> },
    "aviso_previo:previsto": {
      label: "Prazo do aviso prévio",
      tone: "info",
      icon: <BellRing size={12} />,
    },
    "aviso_previo:vencido": {
      label: "Prazo do aviso passou",
      tone: "warning",
      icon: <BellRing size={12} />,
    },
    "fim_contrato:vence": {
      label: "Contrato vence",
      tone: "warning",
      icon: <CalendarX size={12} />,
    },
    "fim_contrato:vencido": {
      label: "Contrato vencido",
      tone: "danger",
      icon: <CalendarX size={12} />,
    },
  };
  return map[key] ?? { label: e.status, tone: "neutral", icon: <Clock size={12} /> };
}

/** "Needs attention now": overdue payments, invoices that did not arrive, ended contracts. */
export function isLate(e: AgendaEvent): boolean {
  return (
    (e.kind === "vencimento" && e.status === "vencido") ||
    (e.kind === "nf_prevista" && e.status === "nao_chegou") ||
    (e.kind === "fim_contrato" && e.status === "vencido")
  );
}

export function AgendaItem({
  event,
  href,
  showCondo,
}: {
  event: AgendaEvent;
  href?: string | null;
  showCondo?: boolean;
}) {
  const look = agendaStatus(event);
  const body = (
    <>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm">{event.title}</span>
        <span className="block truncate text-xs text-muted">
          {showCondo && event.condominium ? `${event.condominium} · ` : ""}
          {event.detail}
          {event.predicted && " · data prevista"}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        {event.amount && <span className="tabular text-sm">{formatBRL(event.amount)}</span>}
        <Badge tone={look.tone} icon={look.icon}>
          {look.label}
        </Badge>
      </span>
    </>
  );
  const cls =
    "flex items-start gap-3 rounded-[var(--radius-card)] border border-line bg-bg-2 px-3 py-2.5";
  return href ? (
    <Link href={href} className={`${cls} transition-ui hover:border-control`}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}
