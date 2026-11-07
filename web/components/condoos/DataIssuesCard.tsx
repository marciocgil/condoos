"use client";

import { AlertTriangle, Check, FileText, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { DataIssue } from "@/lib/types";

const MONEY_FIELDS = new Set(["monthly_value"]);

function show(issue: DataIssue, value: string): string {
  if (MONEY_FIELDS.has(issue.field_name ?? "") && /^\d+(\.\d+)?$/.test(value)) {
    return Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-");
    return `${d}/${m}/${y}`;
  }
  return value;
}

function IssueItem({ condominiumId, issue }: { condominiumId: string; issue: DataIssue }) {
  const router = useRouter();
  const [choice, setChoice] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/condominiums/${condominiumId}/data-issues/${issue.id}`;

  async function act(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}/${path}`, body);
    setBusy(false);
    if (!r.ok) setError(r.error);
    else router.refresh();
  }

  return (
    <li className="py-4" data-issue={issue.id}>
      <p className="flex items-start gap-2 font-medium">
        <AlertTriangle size={16} aria-hidden className="mt-0.5 shrink-0 text-warning" />
        {issue.title}
      </p>
      <fieldset className="mt-3" disabled={!issue.can_resolve || busy}>
        <legend className="sr-only">Versões</legend>
        <div className="grid gap-2 md:grid-cols-2">
          {issue.sources.map((s, i) => (
            <label
              key={i}
              className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-button)] border border-line bg-elevated p-3 has-[:checked]:border-accent"
            >
              {issue.can_resolve && (
                <input
                  type="radio"
                  name={`v-${issue.id}`}
                  className="mt-1"
                  checked={choice === i}
                  onChange={() => setChoice(i)}
                />
              )}
              <span className="min-w-0 text-sm">
                <span className="block text-[13px] text-fg-2">{s.label}</span>
                <span className="tabular block font-medium">{show(issue, s.value)}</span>
                {s.excerpt && (
                  <span className="mt-1 flex items-start gap-1 text-[13px] text-muted">
                    <FileText size={12} aria-hidden className="mt-0.5 shrink-0" />
                    <q className="not-italic">{s.excerpt}</q>
                    {s.page ? ` · página ${s.page}` : null}
                  </span>
                )}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {issue.can_resolve ? (
        <div className="mt-3 space-y-2">
          <Field id={`r-${issue.id}`} label="Motivo (obrigatório)">
            <textarea
              id={`r-${issue.id}`}
              className={`${controlClass} min-h-16`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ex.: o documento assinado é o que vale."
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              size="sm"
              icon={<Check size={14} aria-hidden />}
              disabled={busy || choice === null}
              onClick={() => void act("resolve", { prevailing: choice, reason })}
            >
              Usar a versão escolhida
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<X size={14} aria-hidden />}
              disabled={busy}
              onClick={() => void act("dismiss", { reason })}
            >
              Manter o cadastro e descartar
            </Button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-[13px] text-muted">
          Quem resolve: síndico, equipe CondoOS ou a administradora quando ela revisa.
        </p>
      )}
    </li>
  );
}

/** Open data conflicts (LB-030, D95): each version side by side, with its excerpt. Choosing
 * a version needs a reason; nothing is deleted, and the other version stays recorded. */
export function DataIssuesCard({
  condominiumId,
  issues,
}: {
  condominiumId: string;
  issues: DataIssue[];
}) {
  if (issues.length === 0) return null;
  return (
    <Card id="conflitos" aria-labelledby="conflitos-titulo" data-testid="data-issues">
      <CardTitle
        action={
          <Badge tone="warning" icon={<AlertTriangle size={12} />}>
            {issues.length} {issues.length === 1 ? "aberto" : "abertos"}
          </Badge>
        }
      >
        <span id="conflitos-titulo">Conflitos de dados</span>
      </CardTitle>
      <p className="text-[13px] text-fg-2">
        O cadastro e os documentos não batem. Até alguém escolher a versão certa, nada é conferido
        com esses dados e nenhuma ação sobre o contrato é pedida.
      </p>
      <ul className="divide-y divide-line">
        {issues.map((i) => (
          <IssueItem key={i.id} condominiumId={condominiumId} issue={i} />
        ))}
      </ul>
    </Card>
  );
}
