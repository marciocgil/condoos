"use client";

import { Ban, CheckCircle2, Circle, Copy, Link2, Send, Share2, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DelegationStatusBadge } from "@/components/condoos/DelegationStatusBadge";
import { RequestEmailCard } from "@/components/condoos/RequestEmailCard";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { send } from "@/lib/client";
import { formatDate, formatDateTime } from "@/lib/format";
import type { DelegationDetail, DelegationLinkOut } from "@/lib/types";

const EVENT_LABEL: Record<string, string> = {
  criado: "Pedido preparado",
  autorizado: "Autorizado pelo síndico",
  link_gerado: "Link gerado",
  compartilhado: "Marcado como enviado pelo síndico",
  arquivo_recebido: "Arquivo recebido",
  arquivo_recusado: "Arquivo recusado na triagem",
  item_atendido: "Item recebido",
  concluido: "Concluído",
  encerrado: "Encerrado",
  expirado: "Link venceu",
  revogado: "Revogado",
  email_aprovado: "E-mail aprovado pelo síndico",
  email_enviado: "E-mail aceito pelo servidor de e-mail",
  email_falhou: "E-mail não enviado",
};

/** One request (D95): authorise, make the link and the text, share it from the phone, follow
 * what arrives. "Enviei" is the síndico's own statement; the CondoOS sends only the request
 * e-mail the síndico approves (D103). */
export function DelegationDetailView({
  condominiumId,
  request,
}: {
  condominiumId: string;
  request: DelegationDetail;
}) {
  const router = useRouter();
  const [link, setLink] = useState<DelegationLinkOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const base = `/condominiums/${condominiumId}/delegations/${request.id}`;

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setError(null);
    const r = await send<unknown>("POST", `${base}/${path}`, body);
    setBusy(false);
    if (!r.ok) return (setError(r.error), null);
    router.refresh();
    return r.data;
  }

  async function makeLink() {
    const data = (await act("link", { days: 7 })) as DelegationLinkOut | null;
    if (data) setLink(data);
  }

  async function share() {
    if (!link) return;
    if (navigator.share) {
      try {
        await navigator.share({ text: link.text });
      } catch {
        return; // the person closed the share sheet
      }
    } else {
      await navigator.clipboard.writeText(link.text);
      setCopied(true);
    }
  }

  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{request.recipient_name}</h1>
          <p className="text-sm text-fg-2">
            {request.progress.attended} de {request.progress.total} recebidos · prazo{" "}
            {formatDate(request.due_date)}
          </p>
        </div>
        <DelegationStatusBadge status={request.status} />
      </div>

      {request.can.authorize && (
        <Card>
          <p className="text-sm">
            A equipe CondoOS preparou este pedido. Ele só vale com a sua autorização.
          </p>
          <Button
            className="mt-3"
            variant="primary"
            icon={<CheckCircle2 size={16} aria-hidden />}
            disabled={busy}
            onClick={() => void act("authorize")}
          >
            Autorizar pedido
          </Button>
        </Card>
      )}

      {request.can.issue_link && (
        <Card data-testid="delegation-link">
          <CardTitle>
            <span>Link e texto para enviar</span>
          </CardTitle>
          {link ? (
            <div className="space-y-3">
              <pre className="rounded-[var(--radius-control)] border border-line bg-bg-2 p-3 text-[13px] whitespace-pre-wrap [overflow-wrap:anywhere]">
                {link.text}
              </pre>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  icon={<Share2 size={16} aria-hidden />}
                  onClick={() => void share()}
                >
                  Compartilhar
                </Button>
                <Button
                  icon={<Copy size={16} aria-hidden />}
                  onClick={async () => {
                    await navigator.clipboard.writeText(link.text);
                    setCopied(true);
                  }}
                >
                  {copied ? "Texto copiado" : "Copiar texto"}
                </Button>
                <Button
                  icon={<Send size={16} aria-hidden />}
                  disabled={busy}
                  onClick={() => void act("shared")}
                >
                  Já enviei
                </Button>
              </div>
              <p className="text-[12px] text-muted">
                O link só aceita envio de arquivos e vale até {formatDate(link.expires_at)}. Quem
                envia este texto é você; se preferir, o CondoOS manda por e-mail (abaixo).
              </p>
            </div>
          ) : (
            <>
              <p className="text-sm text-fg-2">
                {request.shared_at
                  ? `${request.shared_by === "email" ? "O CondoOS enviou por e-mail" : "Você marcou como enviado"} em ${formatDateTime(request.shared_at)}. Gerar de novo invalida o link anterior.`
                  : "Gero um link só para envio de arquivos, válido por 7 dias, e um texto pronto."}
              </p>
              <Button
                className="mt-3"
                variant={request.shared_at ? "secondary" : "primary"}
                icon={<Link2 size={16} aria-hidden />}
                disabled={busy}
                onClick={() => void makeLink()}
              >
                {request.shared_at ? "Gerar novo link" : "Gerar link e texto"}
              </Button>
            </>
          )}
        </Card>
      )}

      <RequestEmailCard
        condominiumId={condominiumId}
        requestId={request.id}
        email={request.email}
      />

      <Card>
        <CardTitle>
          <span>O que foi pedido</span>
        </CardTitle>
        <ul className="space-y-2" aria-label="Itens do pedido">
          {request.items.map((i) => (
            <li key={i.key} className="flex items-start justify-between gap-3 text-sm">
              <span className="flex items-start gap-2">
                {i.attended_at ? (
                  <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0 text-success" />
                ) : (
                  <Circle size={16} aria-hidden className="mt-0.5 shrink-0 text-muted" />
                )}
                <span>
                  {i.label}
                  <span className="block text-[12px] text-fg-2">
                    {i.attended_at
                      ? i.attended_by === "automatico"
                        ? "Recebido: a nota chegou"
                        : "Marcado como recebido"
                      : "Pendente"}
                  </span>
                </span>
              </span>
              {!i.attended_at && request.can.attend && (
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => void act(`items/${encodeURIComponent(i.key)}/attend`)}
                >
                  Recebido
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardTitle>
          <span>Arquivos recebidos</span>
        </CardTitle>
        {request.documents.length === 0 ? (
          <p className="text-sm text-fg-2">Nenhum arquivo ainda.</p>
        ) : (
          <ul className="space-y-1 text-sm" aria-label="Arquivos recebidos">
            {request.documents.map((d) => (
              <li key={d.id}>
                <span className="break-all">{d.filename}</span>{" "}
                <span className="text-[12px] text-fg-2">· {d.doc_type_label}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <details className="text-sm">
        <summary className="cursor-pointer text-fg-2 hover:text-fg">Histórico</summary>
        <ol className="mt-2 space-y-1 text-[13px] text-fg-2">
          {request.events.map((e, i) => (
            <li key={`${e.kind}-${i}`}>
              {formatDateTime(e.at)} · {EVENT_LABEL[e.kind] ?? e.kind}
              {e.by_person ? "" : " (automático ou pelo link)"}
            </li>
          ))}
        </ol>
      </details>

      {request.can.finish && (
        <div className="flex flex-wrap gap-2">
          <Button
            icon={<XCircle size={16} aria-hidden />}
            disabled={busy}
            onClick={() => void act("close")}
          >
            Encerrar pedido
          </Button>
          <Button
            variant="danger"
            icon={<Ban size={16} aria-hidden />}
            disabled={busy}
            onClick={() => void act("revoke")}
          >
            Revogar link
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </>
  );
}
