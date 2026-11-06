"use client";

import { FileCheck2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { DocumentItem } from "@/lib/types";

// Documents that can back a one-off service: contract, signed proposal or quote (sent as
// "outro"), minutes, convention.
const BACKING = new Set(["contrato", "ata", "outro", "convencao"]);
const TYPE_LABEL: Record<string, string> = {
  contrato: "Contrato",
  ata: "Ata",
  outro: "Proposta / outro",
  convencao: "Convenção",
};

/** Links an approval (and its document) to a one-off service in the pending cockpit. */
export function OneOffApproval({
  condominiumId,
  expenseId,
}: {
  condominiumId: string;
  expenseId: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [form, setForm] = useState({
    approved_by: "Conselho consultivo",
    approved_at: "",
    document: "",
    notes: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setOpen(true);
    if (docs === null) {
      const res = await fetch(`/api/condominiums/${condominiumId}/documents`);
      const all = res.ok ? ((await res.json()) as DocumentItem[]) : [];
      setDocs(all.filter((d) => BACKING.has(d.doc_type)));
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    const r = await send("POST", `/condominiums/${condominiumId}/expenses/${expenseId}/approvals`, {
      approved_by: form.approved_by,
      approved_at: form.approved_at,
      notes: form.notes || null,
      source_document_id: form.document || null,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOpen(false);
    router.refresh();
  }

  if (!open)
    return (
      <Button
        variant="secondary"
        size="sm"
        icon={<FileCheck2 size={14} />}
        onClick={() => void start()}
      >
        Vincular aprovação
      </Button>
    );
  return (
    <div className="w-full space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3 text-left">
      <Field
        id={`doc-${expenseId}`}
        label="Documento de aprovação"
        hint="Proposta assinada, orçamento aprovado, ata ou contrato."
      >
        <select
          id={`doc-${expenseId}`}
          className={controlClass}
          value={form.document}
          onChange={(e) => setForm({ ...form, document: e.target.value })}
        >
          <option value="">{docs === null ? "Carregando…" : "Sem documento (só registro)"}</option>
          {(docs ?? []).map((d) => (
            <option key={d.id} value={d.id}>
              {TYPE_LABEL[d.doc_type] ?? d.doc_type} · {d.original_filename}
            </option>
          ))}
        </select>
      </Field>
      <p className="text-xs text-muted">
        O documento não está na lista?{" "}
        <Link
          href={`/admin/enviar?condominio=${condominiumId}`}
          className="underline underline-offset-2"
        >
          Envie a proposta ou a ata
        </Link>{" "}
        e volte aqui.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <Field id={`by-${expenseId}`} label="Quem aprovou" required>
          <input
            id={`by-${expenseId}`}
            className={controlClass}
            value={form.approved_by}
            onChange={(e) => setForm({ ...form, approved_by: e.target.value })}
          />
        </Field>
        <Field id={`at-${expenseId}`} label="Data da aprovação" required>
          <input
            id={`at-${expenseId}`}
            type="date"
            className={controlClass}
            value={form.approved_at}
            onChange={(e) => setForm({ ...form, approved_at: e.target.value })}
          />
        </Field>
      </div>
      {error && (
        <p role="alert" className="text-[13px] text-danger">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={() => void save()}
          disabled={busy || form.approved_by.trim().length < 3 || !form.approved_at}
        >
          {busy ? "Salvando…" : "Salvar"}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
