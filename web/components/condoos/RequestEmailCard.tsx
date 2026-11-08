"use client";

import { AlertTriangle, CheckCircle2, Clock, Mail, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { RequestEmail } from "@/lib/types";

const HISTORY: Record<string, { label: string; tone: BadgeTone; icon: ReactNode }> = {
  executada: {
    label: "Aceito pelo servidor de e-mail",
    tone: "success",
    icon: <CheckCircle2 size={12} />,
  },
  bloqueada: { label: "Não enviado", tone: "danger", icon: <AlertTriangle size={12} /> },
  recusada: { label: "Recusado pelo síndico", tone: "neutral", icon: <XCircle size={12} /> },
  cancelada: { label: "Cancelado", tone: "neutral", icon: <XCircle size={12} /> },
};

/** LB-053 (D103): the CondoOS sends the request by e-mail — the one thing the system sends
 * out — only after the síndico approves this exact e-mail. "Aceito pelo servidor" is not
 * delivery. */
export function RequestEmailCard({
  condominiumId,
  requestId,
  email,
}: {
  condominiumId: string;
  requestId: string;
  email: RequestEmail;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!email.enabled) return null;
  const pending = email.pending;
  if (!pending && !email.can_prepare && email.history.length === 0) return null;

  async function call(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    const r = await send("POST", path, body);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOpen(false);
    router.refresh();
  }

  const prepare = () =>
    call(`/condominiums/${condominiumId}/delegations/${requestId}/email`, {
      to,
      note,
      idempotency_key: `mail-${crypto.randomUUID()}`,
    });
  const decide = (action: "aprovar" | "cancelar") =>
    pending &&
    call(`/condominiums/${condominiumId}/actions/${pending.id}/decisions`, {
      action,
      payload_hash: pending.payload_hash,
      comment: action === "cancelar" ? "Cancelado na tela do pedido de documentos." : undefined,
    });

  return (
    <Card aria-label="Enviar por e-mail pelo CondoOS">
      <CardTitle>
        <span>Enviar por e-mail pelo CondoOS</span>
      </CardTitle>

      {pending ? (
        <div className="space-y-3">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
            <dt className="text-fg-2">De</dt>
            <dd>{pending.from_name}</dd>
            <dt className="text-fg-2">Para</dt>
            <dd className="break-all">{pending.to}</dd>
            {pending.reply_to && (
              <>
                <dt className="text-fg-2">Responder para</dt>
                <dd className="break-all">{pending.reply_to}</dd>
              </>
            )}
            <dt className="text-fg-2">Assunto</dt>
            <dd>{pending.subject}</dd>
          </dl>
          <pre
            data-testid="email-preview"
            className="rounded-[var(--radius-control)] border border-line bg-bg-2 p-3 text-[13px] whitespace-pre-wrap [overflow-wrap:anywhere]"
          >
            {pending.body.replace("{link}", "[link novo, gerado no momento do envio]")}
          </pre>
          {pending.status === "aguardando_aprovacao" ? (
            pending.can_approve ? (
              <>
                <p className="text-[13px] text-fg-2">
                  Ao aprovar, o CondoOS envia exatamente este e-mail com um link novo; o link
                  anterior deixa de valer. O sistema registra quando o servidor de e-mail aceitar, o
                  que não confirma a entrega.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="primary"
                    icon={<Mail size={16} aria-hidden />}
                    disabled={busy}
                    onClick={() => void decide("aprovar")}
                  >
                    Aprovar e enviar
                  </Button>
                  {pending.can_cancel && (
                    <Button variant="ghost" disabled={busy} onClick={() => void decide("cancelar")}>
                      Cancelar
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <Badge tone="neutral" icon={<Clock size={12} />}>
                Aguardando a aprovação do síndico
              </Badge>
            )
          ) : (
            <Badge tone="info" icon={<Clock size={12} />}>
              Aprovado: o CondoOS está enviando
            </Badge>
          )}
        </div>
      ) : email.can_prepare ? (
        open ? (
          <div className="space-y-3">
            <Field id="mail-to" label="E-mail de quem vai enviar os documentos" required>
              <input
                id="mail-to"
                type="email"
                className={controlClass}
                value={to}
                onChange={(e) => setTo(e.target.value)}
                autoComplete="off"
              />
            </Field>
            <Field id="mail-note" label="Recado (opcional)" hint="Até 500 caracteres.">
              <textarea
                id="mail-note"
                className={controlClass}
                rows={2}
                maxLength={500}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </Field>
            <div className="flex gap-2">
              <Button
                variant="primary"
                disabled={busy || !to.trim()}
                onClick={() => void prepare()}
              >
                Ver o e-mail antes de enviar
              </Button>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-fg-2">
              Em vez de mandar o link pelo seu WhatsApp, o CondoOS pode enviar o pedido por e-mail.
              Você vê o e-mail inteiro e aprova antes.
            </p>
            <Button
              className="mt-3"
              icon={<Mail size={16} aria-hidden />}
              onClick={() => setOpen(true)}
            >
              Preparar e-mail
            </Button>
          </>
        )
      ) : null}

      {email.history.length > 0 && (
        <ul
          className="mt-3 divide-y divide-line border-t border-line text-[13px]"
          aria-label="E-mails do pedido"
        >
          {email.history.map((h) => {
            const look = HISTORY[h.status] ?? HISTORY.cancelada!;
            return (
              <li key={h.id} className="py-2">
                <span className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    {formatDateTime(h.at)} · {h.to}
                  </span>
                  <Badge tone={look.tone} icon={look.icon}>
                    {look.label}
                  </Badge>
                </span>
                {h.status !== "executada" && h.note && (
                  <span className="block text-fg-2">{h.note}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
