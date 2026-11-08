"use client";

import { ChevronLeft, Info } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { Timeline } from "@/components/ui/Timeline";
import { send } from "@/lib/client";
import { formatBRL, formatDate, formatDateTime } from "@/lib/format";
import { ACTION_BUTTON_LABEL, ACTION_DECISION_VERB } from "@/lib/labels";
import type { ActionDetail, ActionTypes } from "@/lib/types";

import { ActionForm } from "./ActionForm";
import { ActionStatusBadge } from "./ActionStatusBadge";

const NEEDS_COMMENT = new Set(["pedir_ajustes", "recusar", "cancelar"]);

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[180px_1fr]">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

/** Contextual approval (spec §7.5; D83): what is authorised, why, the exact effect, cost and
 * cap, who executes, sources, risks, the applicable limit and how long the approval lasts. */
export function ActionDetailView({
  detail: a,
  types,
  backHref,
  backLabel,
  casePath,
}: {
  detail: ActionDetail;
  types: ActionTypes["types"];
  backHref: string;
  backLabel: string;
  casePath: string; // "{id}" is replaced
}) {
  const router = useRouter();
  const base = `/condominiums/${a.condominium_id}/actions/${a.id}`;
  const [pending, setPending] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [exec, setExec] = useState({ note: "", final_cost: a.cost_cap });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function post(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}${path}`, body);
    setBusy(false);
    setPending(null);
    setComment("");
    router.refresh();
    if (!r.ok) setError(r.error);
  }

  async function act(action: string) {
    if (action === "ajustar" || action === "registrar_execucao" || NEEDS_COMMENT.has(action)) {
      setPending(pending === action ? null : action);
      return;
    }
    // Approve exactly the version on screen (its hash): if it changed, the API refuses.
    await post("/decisions", { action, payload_hash: a.payload_hash });
  }

  const p = a.payload;
  return (
    <article className="space-y-5" aria-labelledby="action-title">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> {backLabel}
      </Link>
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <ActionStatusBadge status={a.status} />
          <Badge tone="neutral">{a.type_label}</Badge>
        </div>
        <h1 id="action-title" className="text-xl font-semibold">
          {a.title}
        </h1>
        <p className="text-[13px] text-fg-2">
          {a.condominium_name} · pedido por {a.requested_by} em {formatDateTime(a.created_at)}
        </p>
      </header>

      <Card>
        <CardTitle>O que será autorizado</CardTitle>
        <dl className="space-y-3">
          <Row label="Efeito exato">{p.effect}</Row>
          <Row label="Por quê">{p.reason}</Row>
          {p.email ? (
            <>
              <Row label="E-mail que o CondoOS vai enviar">
                <span className="block text-[13px]">
                  De {p.email.from_name} · para {p.email.to}
                  {p.email.reply_to && ` · responder para ${p.email.reply_to}`}
                </span>
                <span className="block text-[13px] font-medium">{p.email.subject}</span>
                <pre className="mt-1 rounded-[var(--radius-control)] border border-line bg-bg-2 p-3 text-[13px] whitespace-pre-wrap [overflow-wrap:anywhere]">
                  {p.email.body.replace("{link}", "[link novo, gerado no momento do envio]")}
                </pre>
              </Row>
              <Row label="Depois do clique">
                O CondoOS envia exatamente este e-mail, com um link novo (o anterior deixa de
                valer), e registra quando o servidor de e-mail aceitar. Isso não confirma a entrega.
              </Row>
            </>
          ) : (
            <Row label="Depois do clique">
              Nada é enviado pelo sistema. A ação fica aprovada e aguarda uma pessoa executar e
              registrar o que foi feito.
            </Row>
          )}
          <Row label="Custo e teto">
            Teto de <span className="font-medium tabular-nums">{formatBRL(a.cost_cap)}</span>
            {Number(a.cost_cap) === 0 && " (sem custo)"}; custo acima do teto exige nova aprovação.
          </Row>
          <Row label="Quem executará">
            {p.executor}
            {a.supplier_name && ` · ${a.supplier_name}`}
            {p.due_date && ` · prazo ${formatDate(p.due_date)}`}
          </Row>
          <Row label="Riscos e alternativas">{p.risks || "Nenhum informado."}</Row>
          <Row label="Fontes">
            {a.case_id ? (
              <Link className="underline" href={casePath.replace("{id}", a.case_id)}>
                Assunto {a.case_number} — {a.case_title}
              </Link>
            ) : (
              "Sem assunto vinculado."
            )}
          </Row>
          <Row label="Alçada aplicável">
            {a.approval_limit
              ? `Alçada do síndico: ${formatBRL(a.approval_limit)}`
              : "Sem alçada configurada"}
            . Vale por {a.approval_valid_days} dias depois de aprovada
            {a.approval_expires_at && ` (até ${formatDateTime(a.approval_expires_at)})`}.
          </Row>
        </dl>
        <p className="mt-3 flex items-start gap-1.5 border-t border-line pt-3 text-xs text-muted">
          <Info size={14} aria-hidden className="mt-px shrink-0" />
          Política versão {a.policy_version}: {a.policy_reason} Versão do pedido{" "}
          {a.payload_hash.slice(0, 12)}.
        </p>
      </Card>

      {a.execution_note && (
        <Card>
          <CardTitle>Execução registrada</CardTitle>
          <p className="text-sm">{a.execution_note}</p>
          <p className="mt-1 text-xs text-muted">
            {a.executed_by} · {a.executed_at && formatDateTime(a.executed_at)}
          </p>
        </Card>
      )}

      {a.allowed_actions.length > 0 && (
        <section aria-label="Decisão" className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {a.allowed_actions.map((x) => (
              <Button
                key={x}
                variant={
                  x === "aprovar" || x === "registrar_execucao"
                    ? "primary"
                    : x === "recusar"
                      ? "danger"
                      : "secondary"
                }
                disabled={busy}
                aria-expanded={x === "aprovar" ? undefined : pending === x}
                onClick={() => void act(x)}
              >
                {ACTION_BUTTON_LABEL[x] ?? x}
              </Button>
            ))}
          </div>
          {pending && NEEDS_COMMENT.has(pending) && (
            <div className="space-y-2 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
              <Field id="a-decision-comment" label="Motivo" required>
                <textarea
                  id="a-decision-comment"
                  rows={2}
                  className={textareaClass}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </Field>
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={busy || comment.trim().length < 5}
                  onClick={() => void post("/decisions", { action: pending, comment })}
                >
                  Confirmar: {ACTION_BUTTON_LABEL[pending]?.toLowerCase()}
                </Button>
                <Button variant="ghost" onClick={() => setPending(null)}>
                  Voltar
                </Button>
              </div>
            </div>
          )}
          {pending === "registrar_execucao" && (
            <div className="space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
              <Field id="a-exec-note" label="O que foi feito" required>
                <textarea
                  id="a-exec-note"
                  rows={2}
                  className={textareaClass}
                  value={exec.note}
                  onChange={(e) => setExec({ ...exec, note: e.target.value })}
                />
              </Field>
              <Field id="a-exec-cost" label="Custo final (R$)" required>
                <input
                  id="a-exec-cost"
                  inputMode="decimal"
                  className={controlClass}
                  value={exec.final_cost}
                  onChange={(e) => setExec({ ...exec, final_cost: e.target.value })}
                />
              </Field>
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={busy || exec.note.trim().length < 5}
                  onClick={() =>
                    void post("/execution", {
                      note: exec.note,
                      final_cost: exec.final_cost.replace(",", ".") || "0",
                    })
                  }
                >
                  Confirmar execução
                </Button>
                <Button variant="ghost" onClick={() => setPending(null)}>
                  Voltar
                </Button>
              </div>
            </div>
          )}
          {pending === "ajustar" && (
            <ActionForm
              condominiumId={a.condominium_id}
              types={types}
              actionId={a.id}
              detailPath=""
              initial={{
                action_type: a.action_type,
                title: a.title,
                cost_cap: a.cost_cap,
                payload: { ...p, due_date: p.due_date ?? "", risks: p.risks ?? "" },
              }}
              onDone={() => setPending(null)}
            />
          )}
        </section>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      <section aria-labelledby="action-history">
        <h2 id="action-history" className="mb-3 text-base font-semibold">
          Histórico
        </h2>
        <Timeline
          label="Histórico da ação"
          items={[...a.history].reverse().map((h, i) => ({
            id: `${h.at}-${i}`,
            when: formatDateTime(h.at),
            who: h.who,
            what: ACTION_DECISION_VERB[h.kind] ?? h.kind,
            detail: h.comment ? <q>{h.comment}</q> : undefined,
          }))}
        />
      </section>
    </article>
  );
}
