"use client";

import { ChevronLeft, FolderPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { Timeline } from "@/components/ui/Timeline";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import {
  OPPORTUNITY_ACTION_LABEL,
  OPPORTUNITY_ACTION_VERB,
  OPPORTUNITY_NEEDS_COMMENT,
  OPPORTUNITY_TYPE_LABEL,
} from "@/lib/labels";
import type { OpportunityDetail } from "@/lib/types";

import { OpportunityStatusBadge } from "./OpportunityStatusBadge";
import { SavingsStages } from "./SavingsStages";

/** Opportunity detail for the CondoOS team (review) and for the board (decision). */
export function OpportunityDetailView({
  detail: o,
  backHref,
  backLabel,
  findingPath,
  newCaseHref,
}: {
  detail: OpportunityDetail;
  backHref: string;
  backLabel: string;
  findingPath: string; // "{id}" is replaced (strings: functions cannot cross to the client)
  newCaseHref?: string;
}) {
  const router = useRouter();
  const base = `/condominiums/${o.condominium_id}/opportunities/${o.id}`;
  const [pending, setPending] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const potential = o.stages.find((s) => s.stage === "potencial");
  const [adj, setAdj] = useState({
    amount: potential?.amount ?? "",
    one_time_cost: potential?.one_time_cost ?? "0",
    reason: "",
  });

  async function post(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}${path}`, body);
    setBusy(false);
    if (!r.ok) return (setError(r.error), false);
    setPending(null);
    setComment("");
    router.refresh();
    return true;
  }

  async function act(action: string) {
    if (action === "ajustar" || (OPPORTUNITY_NEEDS_COMMENT.has(action) && pending !== action)) {
      setPending(pending === action ? null : action);
      return;
    }
    await post("/decisions", { action, comment: comment || undefined });
  }

  return (
    <article className="space-y-5" aria-labelledby="opp-title">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> {backLabel}
      </Link>
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-muted tabular-nums">{o.number}</span>
          <OpportunityStatusBadge status={o.status} />
          <Badge tone="neutral">
            {OPPORTUNITY_TYPE_LABEL[o.opportunity_type] ?? o.opportunity_type}
          </Badge>
        </div>
        <h1 id="opp-title" className="text-xl font-semibold">
          {o.title}
        </h1>
        <p className="text-[13px] text-fg-2">
          {o.condominium_name}
          {o.supplier_name && ` · ${o.supplier_name}`}
          {!o.presented && " · ainda não apresentada ao condomínio"}
        </p>
      </header>

      <Card>
        <CardTitle>Recomendação</CardTitle>
        <p className="text-sm">{o.recommendation}</p>
        <p className="mt-2 text-[13px] text-fg-2">
          Impacto no serviço: {o.operational_impact} · risco contratual {o.legal_contractual_risk}
        </p>
        <p className="mt-2 text-xs text-muted">
          Estimativa calculada a partir dos dados; não é economia já capturada. Nada é negociado ou
          pago pelo sistema.
        </p>
      </Card>

      <section aria-labelledby="opp-savings" className="space-y-2">
        <h2 id="opp-savings" className="text-base font-semibold">
          Economia
        </h2>
        <SavingsStages stages={o.stages} />
      </section>

      {o.allowed_actions.length > 0 && (
        <section aria-label="Decisão" className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {o.allowed_actions.map((a) => (
              <Button
                key={a}
                variant={
                  a === "aprovar" || a === "condominio_aprovar"
                    ? "primary"
                    : a === "rejeitar"
                      ? "danger"
                      : "secondary"
                }
                disabled={busy}
                aria-expanded={
                  OPPORTUNITY_NEEDS_COMMENT.has(a) || a === "ajustar" ? pending === a : undefined
                }
                onClick={() => void act(a)}
              >
                {OPPORTUNITY_ACTION_LABEL[a] ?? a}
              </Button>
            ))}
          </div>
          {pending && pending !== "ajustar" && (
            <div className="space-y-2 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
              <Field id="o-comment" label="Motivo" required>
                <textarea
                  id="o-comment"
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
                  Confirmar: {OPPORTUNITY_ACTION_LABEL[pending]?.toLowerCase()}
                </Button>
                <Button variant="ghost" onClick={() => setPending(null)}>
                  Cancelar
                </Button>
              </div>
            </div>
          )}
          {pending === "ajustar" && (
            <div className="space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
              <div className="grid grid-cols-2 gap-3">
                <Field id="o-amount" label="Economia por mês (R$)">
                  <input
                    id="o-amount"
                    inputMode="decimal"
                    className={controlClass}
                    value={adj.amount}
                    onChange={(e) => setAdj({ ...adj, amount: e.target.value })}
                  />
                </Field>
                <Field id="o-cost" label="Custo para implementar (R$)">
                  <input
                    id="o-cost"
                    inputMode="decimal"
                    className={controlClass}
                    value={adj.one_time_cost}
                    onChange={(e) => setAdj({ ...adj, one_time_cost: e.target.value })}
                  />
                </Field>
              </div>
              <Field id="o-reason" label="Por que ajustar" required>
                <input
                  id="o-reason"
                  className={controlClass}
                  value={adj.reason}
                  onChange={(e) => setAdj({ ...adj, reason: e.target.value })}
                />
              </Field>
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={busy || adj.reason.trim().length < 5}
                  onClick={() =>
                    void post("/estimate", {
                      amount: adj.amount.replace(",", "."),
                      one_time_cost: adj.one_time_cost.replace(",", "."),
                      reason: adj.reason,
                    })
                  }
                >
                  Salvar nova estimativa
                </Button>
                <Button variant="ghost" onClick={() => setPending(null)}>
                  Cancelar
                </Button>
              </div>
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </section>
      )}

      {newCaseHref && (
        <Link href={newCaseHref} className={buttonClass("secondary", "sm")}>
          <FolderPlus size={14} aria-hidden /> Abrir assunto para acompanhar
        </Link>
      )}

      {o.findings.length > 0 && (
        <Card>
          <CardTitle>Achados de origem</CardTitle>
          <ul className="space-y-1 text-sm">
            {o.findings.map((f) => (
              <li key={f.id}>
                <Link className="underline" href={findingPath.replace("{id}", f.id)}>
                  {f.rule_code} · {f.title}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <section aria-labelledby="opp-history">
        <h2 id="opp-history" className="mb-3 text-base font-semibold">
          Histórico
        </h2>
        {o.history.length === 0 ? (
          <p className="text-sm text-fg-2">Ainda sem decisões.</p>
        ) : (
          <Timeline
            label="Histórico da oportunidade"
            items={[...o.history].reverse().map((h, i) => ({
              id: `${h.at}-${i}`,
              when: formatDateTime(h.at),
              who: h.who,
              what: OPPORTUNITY_ACTION_VERB[h.action] ?? h.action,
              detail: h.comment ? <q>{h.comment}</q> : undefined,
            }))}
          />
        )}
      </section>
    </article>
  );
}
