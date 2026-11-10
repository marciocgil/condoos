"use client";

import { Activity, CheckCircle2, FilePen, FolderPlus, Users, XCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import { CONTRACT_ALERT_KINDS, type DataIssue } from "@/lib/types";

const MIN_REASON = 10;

/** One health alert from the daily monitors (D110): what was observed and, for whoever
 * resolves data issues, "tratado" or "não procede" with a reason. No sides to choose. */
export function HealthAlertCard({
  issue,
  linkBase = "/admin",
}: {
  issue: DataIssue;
  /** Where the request and case forms live: "/admin" (desktop) or the síndico's condo path. */
  linkBase?: string;
}) {
  const desktop = linkBase === "/admin";
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/condominiums/${issue.condominium_id}/data-issues/${issue.id}`;
  const reasonOk = reason.trim().length >= MIN_REASON;

  async function act(path: string) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}/${path}`, { reason });
    setBusy(false);
    if (!r.ok) setError(r.error);
    else router.refresh();
  }

  return (
    <Card data-testid={`alert-${issue.kind}`} aria-labelledby={`alert-title-${issue.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {issue.condominium && <p className="text-[13px] text-fg-2">{issue.condominium}</p>}
          <h3 id={`alert-title-${issue.id}`} className="text-[15px] font-semibold">
            {issue.title}
          </h3>
          <p className="mt-1 text-sm text-fg-2">{issue.detail}</p>
          {issue.created_at && (
            <p className="mt-1 text-[12px] text-muted">Desde {formatDateTime(issue.created_at)}</p>
          )}
        </div>
        {issue.audiencia === "equipe" ? (
          <Badge tone="info" icon={<Users size={12} />}>
            Só equipe
          </Badge>
        ) : (
          <Badge tone="warning" icon={<Activity size={12} />}>
            Visível ao condomínio
          </Badge>
        )}
      </div>
      {CONTRACT_ALERT_KINDS.has(issue.kind) && (
        <div className="mt-3 flex flex-wrap gap-2" data-testid="contract-alert-actions">
          <Link
            className={buttonClass("secondary", "sm")}
            href={`${linkBase}/pedidos/novo?${new URLSearchParams({
              ...(desktop ? { condominio: issue.condominium_id } : {}),
              item: `Contrato corrigido: ${issue.title.toLowerCase()}`,
              papel: issue.kind === "contrato_contratante" ? "administradora" : "fornecedor",
            })}`}
          >
            <FilePen size={14} aria-hidden /> Pedir correção do contrato
          </Link>
          <Link
            className={buttonClass("secondary", "sm")}
            href={`${linkBase}/assuntos/novo?${new URLSearchParams({
              ...(desktop ? { condominio: issue.condominium_id } : {}),
              titulo: `Ajustar contrato: ${issue.title.toLowerCase()}`,
            })}`}
          >
            <FolderPlus size={14} aria-hidden /> Criar assunto
          </Link>
        </div>
      )}
      {issue.can_resolve && (
        <div className="mt-4 space-y-3">
          <Field
            id={`alert-reason-${issue.id}`}
            label="O que foi feito"
            required
            hint="Fica na trilha: quem tratou, quando e como."
          >
            <textarea
              id={`alert-reason-${issue.id}`}
              className={textareaClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              icon={<CheckCircle2 size={16} aria-hidden />}
              disabled={busy || !reasonOk}
              onClick={() => void act("resolve")}
            >
              Marcar como tratado
            </Button>
            <Button
              icon={<XCircle size={16} aria-hidden />}
              disabled={busy || !reasonOk}
              onClick={() => void act("discard")}
            >
              Não procede
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
