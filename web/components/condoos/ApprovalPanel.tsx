"use client";

import { CheckCircle2, FileCheck2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { formatDate } from "@/lib/format";

const APPROVERS = ["Conselho consultivo", "Assembleia geral", "Assembleia extraordinária"];

/** Rule R12 (above the approval limit): approvals recorded for the expense, and the form the
 * management company uses to record the board's or the assembly's approval. */
export function ApprovalPanel({
  condominiumId,
  expenseId,
  approvals,
  canRecord,
}: {
  condominiumId: string;
  expenseId: string;
  approvals: { id: string; approved_by: string; approved_at: string; notes: string | null }[];
  canRecord: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [approvedBy, setApprovedBy] = useState(APPROVERS[0] ?? "");
  const [approvedAt, setApprovedAt] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function save() {
    setBusy(true);
    setError(null);
    const res = await fetch(`/api/condominiums/${condominiumId}/expenses/${expenseId}/approvals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        approved_by: approvedBy,
        approved_at: approvedAt,
        notes: notes || null,
      }),
    });
    setBusy(false);
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
      setError(typeof body?.detail === "string" ? body.detail : "Confira a data e quem aprovou.");
      return;
    }
    setDone(true);
    setOpen(false);
    router.refresh();
  }

  if (approvals.length === 0 && !canRecord) return null;
  return (
    <section aria-labelledby="approvals" className="space-y-3">
      <h2 id="approvals" className="text-base font-semibold">
        Aprovação da despesa
      </h2>
      {approvals.length > 0 ? (
        <ul className="space-y-2">
          {approvals.map((a) => (
            <li
              key={a.id}
              className="flex items-start gap-3 rounded-[var(--radius-card)] border border-line bg-bg-2 px-4 py-3 text-sm"
            >
              <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0 text-success" />
              <span>
                Aprovada por <strong>{a.approved_by}</strong> em {formatDate(a.approved_at)}
                {a.notes && <span className="mt-0.5 block text-[13px] text-fg-2">{a.notes}</span>}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-fg-2">
          Nenhuma aprovação registrada. Se o conselho ou a assembleia aprovou esta despesa, registre
          aqui: o achado é reavaliado em instantes.
        </p>
      )}
      {done && (
        <p role="status" className="text-[13px] text-success">
          Aprovação registrada. O achado será reavaliado em instantes.
        </p>
      )}
      {canRecord && !open && (
        <Button variant="secondary" icon={<FileCheck2 size={16} />} onClick={() => setOpen(true)}>
          Registrar aprovação
        </Button>
      )}
      {canRecord && open && (
        <div className="space-y-3 rounded-[var(--radius-card)] border border-line bg-surface p-4">
          <Field id="approved-by" label="Quem aprovou" required>
            <input
              id="approved-by"
              list="approvers"
              value={approvedBy}
              onChange={(e) => setApprovedBy(e.target.value)}
              className={controlClass}
            />
            <datalist id="approvers">
              {APPROVERS.map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
          </Field>
          <Field id="approved-at" label="Data da aprovação" required>
            <input
              id="approved-at"
              type="date"
              value={approvedAt}
              onChange={(e) => setApprovedAt(e.target.value)}
              className={controlClass}
            />
          </Field>
          <Field
            id="approval-notes"
            label="Observação"
            hint="Ex.: ata da reunião de 08/09/2026, item 3."
          >
            <textarea
              id="approval-notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={textareaClass}
            />
          </Field>
          {error && (
            <p role="alert" className="text-[13px] text-danger">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => void save()}
              disabled={busy || approvedBy.trim().length < 3 || !approvedAt}
            >
              {busy ? "Registrando…" : "Registrar"}
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
