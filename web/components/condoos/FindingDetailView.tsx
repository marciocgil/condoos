import { ChevronLeft, FolderPlus, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { buttonClass } from "@/components/ui/Button";
import { Timeline } from "@/components/ui/Timeline";
import { formatBRL, formatDateTime, formatMonth } from "@/lib/format";
import { ACTION_LABEL } from "@/lib/labels";
import type { CaseRef, FindingDetail } from "@/lib/types";

import { ApprovalPanel } from "./ApprovalPanel";
import { CaseStatusBadge } from "./CaseStatusBadge";
import { CommentForm } from "./CommentForm";
import { DecisionBar } from "./DecisionBar";
import { EvidenceList } from "./EvidenceList";
import { FindingStatusBadge } from "./FindingStatusBadge";
import { SeverityBadge } from "./SeverityBadge";

/** Finding detail (mockup "Detalhe do achado"), shared by the síndico and the manager views. */
export function FindingDetailView({
  finding: f,
  condominiumId,
  backHref,
  backLabel,
  cases = [],
  casePath,
  newCaseHref,
}: {
  finding: FindingDetail;
  condominiumId: string;
  backHref: string;
  backLabel: string;
  /** Cases linked to this finding (D75) and where to open them. */
  cases?: CaseRef[];
  casePath?: string;
  /** Shown to those who manage cases. */
  newCaseHref?: string;
}) {
  const supplierLine = f.supplier
    ? `${f.supplier.name} · CNPJ ${f.supplier.registration_status === "ATIVA" ? "ativo" : (f.supplier.registration_status ?? "sem consulta").toLowerCase()}`
    : (f.category_label ?? "");
  const history = [
    ...f.decisions.map((d) => ({
      at: d.decided_at,
      id: d.id,
      when: formatDateTime(d.decided_at),
      who: d.user_name,
      what: <>{ACTION_LABEL[d.action]?.verb ?? d.action} o achado</>,
      detail: d.comment ? <q>{d.comment}</q> : undefined,
    })),
    ...f.comments.map((c) => ({
      at: c.created_at,
      id: c.id,
      when: formatDateTime(c.created_at),
      who: c.user_name,
      what: <>comentou</>,
      detail: <q>{c.body}</q>,
    })),
  ].sort((a, b) => a.at.localeCompare(b.at));

  return (
    <article className="space-y-6" aria-labelledby="finding-title">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> {backLabel}
      </Link>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={f.severity} />
          <FindingStatusBadge status={f.status} />
          {f.ai_assisted && (
            <span className="inline-flex items-center gap-1 text-xs text-fg-2">
              <Sparkles size={12} aria-hidden /> Assistido por IA
            </span>
          )}
        </div>
        <h1 id="finding-title" className="text-2xl leading-tight font-semibold">
          {f.title}
        </h1>
        <p className="text-fg-2">{supplierLine}</p>
        <div>
          <p className="tabular text-[28px] font-semibold" data-testid="finding-amount">
            {formatBRL(f.amount_at_risk)}
          </p>
          <p className="text-[13px] text-fg-2">valor em risco · {formatMonth(f.competence)}</p>
        </div>
      </div>

      <section aria-labelledby="why">
        <h2 id="why" className="mb-2 text-base font-semibold">
          Por que foi apontado
        </h2>
        <p className="leading-relaxed text-fg-2">{f.explanation}</p>
        <p className="mt-2 text-xs text-muted">
          Regra {f.rule_code}. Um achado é um indício para verificação, não uma conclusão.
        </p>
      </section>

      <section aria-labelledby="evidence">
        <h2 id="evidence" className="mb-2 text-base font-semibold">
          Evidências
        </h2>
        <EvidenceList items={f.evidence} />
      </section>

      {f.approval_expense_id && (
        <ApprovalPanel
          condominiumId={condominiumId}
          expenseId={f.approval_expense_id}
          approvals={f.approvals ?? []}
          canRecord={f.can_record_approval ?? false}
        />
      )}

      <DecisionBar condominiumId={condominiumId} findingId={f.id} actions={f.allowed_actions} />

      {f.validated_by_management && (
        <p className="inline-flex items-center gap-2 text-[13px] text-fg-2">
          <ShieldCheck size={16} className="text-success" aria-hidden /> Validado pela
          administradora
        </p>
      )}
      {f.validated_by_condoos && (
        <p className="inline-flex items-center gap-2 text-[13px] text-fg-2">
          <ShieldCheck size={16} className="text-success" aria-hidden /> Revisado pela equipe
          CondoOS
        </p>
      )}

      {(cases.length > 0 || newCaseHref) && (
        <section aria-labelledby="finding-cases" className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h2 id="finding-cases" className="text-base font-semibold">
              Assuntos
            </h2>
            {newCaseHref && (
              <Link href={newCaseHref} className={buttonClass("secondary", "sm")}>
                <FolderPlus size={14} aria-hidden /> Abrir assunto
              </Link>
            )}
          </div>
          {cases.length === 0 ? (
            <p className="text-[13px] text-fg-2">
              Nenhum assunto acompanha este achado. Abra um para definir responsável, prazo e
              evidência de conclusão.
            </p>
          ) : (
            <ul className="space-y-1 text-sm">
              {cases.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-2">
                  <Link href={(casePath ?? "").replace("{id}", c.id)} className="underline">
                    {c.number} — {c.title}
                  </Link>
                  <CaseStatusBadge status={c.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section aria-labelledby="history">
        <h2 id="history" className="mb-3 text-base font-semibold">
          Histórico de decisões
        </h2>
        {history.length > 0 ? (
          <Timeline items={history} label="Histórico de decisões" />
        ) : (
          <p className="text-[13px] text-muted">Nenhuma decisão registrada ainda.</p>
        )}
        {f.can_comment && (
          <div className="mt-4">
            <CommentForm condominiumId={condominiumId} findingId={f.id} />
          </div>
        )}
      </section>
    </article>
  );
}
