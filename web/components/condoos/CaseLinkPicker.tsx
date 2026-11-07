"use client";

import { Link2, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { CASE_STATUS_LABEL } from "@/lib/labels";

const TYPES: Record<string, string> = {
  contract: "Contrato",
  document: "Documento",
  supplier: "Fornecedor",
  expense: "Despesa",
  finding: "Achado",
  case: "Outro assunto",
};

interface Candidate {
  target_type: string;
  target_id: string;
  label: string;
  detail: string;
  in_open_cases: string[];
}

/** Search and link a record from the case screen (FR-027, CB-028). A record already in
 * another open case needs a reason, as the API requires. */
export function CaseLinkPicker({
  condominiumId,
  caseId,
}: {
  condominiumId: string;
  caseId: string;
}) {
  const router = useRouter();
  const base = `/condominiums/${condominiumId}/cases/${caseId}`;
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("contract");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Candidate[] | null>(null);
  const [chosen, setChosen] = useState<Candidate | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    setBusy(true);
    setError(null);
    setChosen(null);
    const qs = new URLSearchParams({ tipo: type, q });
    const res = await fetch(`/api${base}/link-candidates?${qs.toString()}`, {
      cache: "no-store",
    });
    setBusy(false);
    if (!res.ok) return setError("Não foi possível buscar agora. Tente de novo.");
    setRows((await res.json()) as Candidate[]);
  }

  async function link(c: Candidate) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}/links`, {
      target_type: c.target_type,
      target_id: c.target_id,
      reason: reason.trim() || undefined,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOpen(false);
    setRows(null);
    setChosen(null);
    setReason("");
    setQ("");
    router.refresh();
  }

  if (!open)
    return (
      <Button
        className="mt-3"
        variant="secondary"
        size="sm"
        icon={<Link2 size={14} />}
        onClick={() => setOpen(true)}
      >
        Vincular registro
      </Button>
    );

  return (
    <div className="mt-3 space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <Field id="lk-type" label="Tipo">
          <select
            id="lk-type"
            className={controlClass}
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setRows(null);
            }}
          >
            {Object.entries(TYPES).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <div className="min-w-0 flex-1 basis-40">
          <Field id="lk-q" label="Buscar">
            <input
              id="lk-q"
              className={controlClass}
              value={q}
              placeholder="Nome, objeto, número…"
              onChange={(e) => setQ(e.target.value)}
            />
          </Field>
        </div>
        <Button type="submit" size="sm" disabled={busy} icon={<Search size={14} />}>
          Buscar
        </Button>
      </form>
      {rows && rows.length === 0 && (
        <p className="text-sm text-fg-2">Nada encontrado com essa busca.</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="divide-y divide-line text-sm" aria-label="Registros encontrados">
          {rows.map((r) => (
            <li key={r.target_id} className="flex items-center justify-between gap-2 py-2">
              <span className="min-w-0">
                <span className="block truncate">{r.label}</span>
                <span className="text-xs text-muted">
                  {r.target_type === "case" ? (CASE_STATUS_LABEL[r.detail] ?? r.detail) : r.detail}
                  {r.in_open_cases.length > 0 && ` · já no assunto ${r.in_open_cases.join(", ")}`}
                </span>
              </span>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                aria-label={`Vincular ${r.label}`}
                onClick={() => (r.in_open_cases.length > 0 ? setChosen(r) : void link(r))}
              >
                Vincular
              </Button>
            </li>
          ))}
        </ul>
      )}
      {chosen && (
        <div className="space-y-2">
          <Field
            id="lk-reason"
            label={`Por que também pertence a este assunto? (já está no ${chosen.in_open_cases.join(", ")})`}
            required
          >
            <input
              id="lk-reason"
              className={controlClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <Button
            variant="primary"
            size="sm"
            disabled={busy || reason.trim().length < 5}
            onClick={() => void link(chosen)}
          >
            Confirmar vínculo
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
        Fechar
      </Button>
    </div>
  );
}
