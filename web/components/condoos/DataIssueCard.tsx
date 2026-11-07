"use client";

import { CheckCircle2, FileText, GitCompare, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { Field, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatBRL } from "@/lib/format";
import type { DataIssue } from "@/lib/types";

const MIN_REASON = 10;

/** One data conflict (D93): the two sides with their excerpts, and — for the CondoOS reviewer
 * and the manager — the choice of the prevailing version or "not a conflict", with a reason.
 * Resolving records the decision; correcting the contract stays in the Contracts screen. */
export function DataIssueCard({ issue }: { issue: DataIssue }) {
  const router = useRouter();
  const [chosen, setChosen] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/condominiums/${issue.condominium_id}/data-issues/${issue.id}`;
  const reasonOk = reason.trim().length >= MIN_REASON;

  async function act(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}/${path}`, body);
    setBusy(false);
    if (!r.ok) setError(r.error);
    else router.refresh();
  }

  return (
    <Card data-testid={`issue-${issue.id}`} aria-labelledby={`issue-title-${issue.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {issue.condominium && <p className="text-[13px] text-fg-2">{issue.condominium}</p>}
          <h2 id={`issue-title-${issue.id}`} className="text-[15px] font-semibold">
            {issue.title}
          </h2>
          <p className="mt-1 text-sm text-fg-2">{issue.detail}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {issue.amount_at_stake && (
            <span className="tabular text-sm">
              {formatBRL(issue.amount_at_stake)} por mês em jogo
            </span>
          )}
          <Badge tone="warning" icon={<GitCompare size={12} />}>
            Em validação
          </Badge>
        </div>
      </div>

      <fieldset className="mt-4">
        <legend className="sr-only">Versões em conflito</legend>
        <div className="grid gap-3 md:grid-cols-2">
          {issue.evidence.map((side, i) => (
            <label
              key={`${side.label}-${i}`}
              className={cx(
                "transition-ui block rounded-[var(--radius-card)] border p-4",
                chosen === i ? "border-accent bg-accent/5" : "border-line bg-bg-2",
                issue.can_resolve ? "cursor-pointer hover:border-control" : "",
              )}
            >
              <span className="flex items-center gap-2">
                {issue.can_resolve && (
                  <input
                    type="radio"
                    name={`prevailing-${issue.id}`}
                    checked={chosen === i}
                    onChange={() => setChosen(i)}
                    aria-label={`Manter: ${side.label}`}
                  />
                )}
                <span className="text-sm font-medium">{side.label}</span>
              </span>
              <span className="tabular mt-1 block text-sm">{side.value}</span>
              {side.excerpt && (
                <span className="mt-2 block border-l-2 border-line pl-2 text-[13px] break-words text-fg-2">
                  {side.page ? `p. ${side.page}: ` : ""}“{side.excerpt}”
                </span>
              )}
              {side.document_id && (
                <a
                  href={`/api/condominiums/${issue.condominium_id}/documents/${side.document_id}/file${side.page ? `#page=${side.page}` : ""}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-xs text-fg-2 hover:text-fg"
                >
                  <FileText size={12} aria-hidden /> {side.filename ?? "Abrir documento"}
                </a>
              )}
            </label>
          ))}
        </div>
      </fieldset>

      {issue.can_resolve ? (
        <div className="mt-4 space-y-3">
          <Field
            id={`reason-${issue.id}`}
            label="Motivo"
            required
            hint="Fica na trilha: quem decidiu, quando e por quê."
          >
            <textarea
              id={`reason-${issue.id}`}
              className={textareaClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              icon={<CheckCircle2 size={16} aria-hidden />}
              disabled={busy || chosen === null || !reasonOk}
              onClick={() => void act("resolve", { prevailing: chosen, reason })}
            >
              Manter a versão escolhida
            </Button>
            <Button
              icon={<XCircle size={16} aria-hidden />}
              disabled={busy || !reasonOk}
              onClick={() => void act("discard", { reason })}
            >
              Não é divergência
            </Button>
          </div>
          <p className="text-[12px] text-muted">
            Registrar a decisão não altera o contrato. Se algum dado estiver errado, corrija na tela
            de Contratos.
          </p>
        </div>
      ) : (
        <p className="mt-4 text-[13px] text-fg-2">
          A revisora CondoOS ou a gerência vai decidir qual versão vale.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
