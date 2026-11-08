"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Inbox,
  PauseCircle,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { InboundChannel, InboundStatus } from "@/lib/types";

const IDLE_DAYS = 30;

const STATUS: Record<InboundStatus, { label: string; tone: BadgeTone; icon: ReactNode }> = {
  processada: { label: "Processado", tone: "success", icon: <CheckCircle2 size={12} /> },
  recusada: { label: "Recusado", tone: "warning", icon: <XCircle size={12} /> },
  falhou: { label: "Falhou", tone: "danger", icon: <AlertTriangle size={12} /> },
};

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

function Health({ channel }: { channel: InboundChannel }) {
  if (channel.paused)
    return (
      <Badge tone="warning" icon={<PauseCircle size={12} />}>
        Pausado: os e-mails esperam até retomar
      </Badge>
    );
  if (channel.days_since_last_message === null)
    return (
      <Badge tone="neutral" icon={<Inbox size={12} />}>
        Nenhum e-mail recebido ainda
      </Badge>
    );
  if (channel.days_since_last_message >= IDLE_DAYS)
    return (
      <Badge tone="warning" icon={<AlertTriangle size={12} />}>
        Nenhum e-mail há {channel.days_since_last_message} dias
      </Badge>
    );
  return (
    <Badge tone="success" icon={<CheckCircle2 size={12} />}>
      Recebendo
    </Badge>
  );
}

/** The condominium's inbound e-mail (D101, LB-050/051): the address to give to whoever sends
 * documents, whether e-mails are arriving, and changing the address if it leaks. */
export function InboundEmailCard({
  condominiumId,
  channel,
}: {
  condominiumId: string;
  channel: InboundChannel;
}) {
  const router = useRouter();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const totals = channel.last_30_days;

  async function change() {
    setBusy(true);
    setError(null);
    const r = await send("POST", `/condominiums/${condominiumId}/inbound/change-address`);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setConfirm(false);
    router.refresh();
  }

  return (
    <Card aria-label="E-mail de entrada">
      <CardTitle>E-mail de entrada</CardTitle>
      <p className="text-sm text-fg-2">
        Notas, boletos e contratos mandados para este endereço entram sozinhos no condomínio.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <code
          data-testid="inbound-address"
          className="rounded-[var(--radius-control)] border border-line bg-elevated px-2 py-1 text-[13px] break-all"
        >
          {channel.address}
        </code>
        <Button
          size="sm"
          variant="ghost"
          icon={<Copy size={14} aria-hidden />}
          onClick={async () => {
            await navigator.clipboard.writeText(channel.address);
            setCopied(true);
          }}
        >
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>
      <div className="mt-3 space-y-1 text-sm">
        <Health channel={channel} />
        {channel.last_message_at && (
          <p className="text-[13px] text-fg-2">
            Último e-mail: {formatDateTime(channel.last_message_at)}
            {channel.last_document_at &&
              ` · último documento: ${formatDateTime(channel.last_document_at)}`}
          </p>
        )}
        <p className="text-[13px] text-fg-2">
          Últimos 30 dias: {plural(totals.messages, "e-mail", "e-mails")} ·{" "}
          {plural(totals.documents, "documento", "documentos")}
          {totals.not_processed > 0 &&
            ` · ${plural(totals.not_processed, "não processado", "não processados")}`}
        </p>
      </div>
      {channel.recent.length > 0 && (
        <ul
          className="mt-3 divide-y divide-line border-t border-line text-[13px]"
          aria-label="E-mails recebidos"
        >
          {channel.recent.slice(0, 5).map((m) => (
            <li key={m.received_at} className="py-2">
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {formatDateTime(m.received_at)} · {m.sender_domain ?? "remetente sem domínio"}
                </span>
                <Badge tone={STATUS[m.status].tone} icon={STATUS[m.status].icon}>
                  {STATUS[m.status].label}
                </Badge>
              </span>
              <span className="block text-fg-2">
                {plural(m.documents, "documento novo", "documentos novos")}
                {m.duplicates > 0 && ` · ${plural(m.duplicates, "já recebido", "já recebidos")}`}
                {m.reasons.length > 0 && ` · ${m.reasons.join(" ")}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {channel.can_change && (
        <div className="mt-4 border-t border-line pt-3">
          {confirm ? (
            <div className="space-y-2">
              <p className="text-sm">
                O endereço atual para de funcionar na hora. Avise quem manda documentos para ele.
              </p>
              <div className="flex gap-2">
                <Button size="sm" variant="danger" disabled={busy} onClick={() => void change()}>
                  Trocar endereço
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>
                  Cancelar
                </Button>
              </div>
            </div>
          ) : (
            <Button
              size="sm"
              icon={<RefreshCw size={14} aria-hidden />}
              onClick={() => setConfirm(true)}
            >
              Trocar o endereço
            </Button>
          )}
          {error && (
            <p role="alert" className="mt-2 text-sm text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
