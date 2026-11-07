"use client";

import { FileSignature, Ruler } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";

/** After the condominium approves (CB-063): record the agreement with its document, then the
 * CondoOS review measures the result from later invoices. Nothing here pays or sends. */
export function OpportunityFollowUp({
  condominiumId,
  opportunityId,
  actions,
}: {
  condominiumId: string;
  opportunityId: string;
  actions: string[];
}) {
  const router = useRouter();
  const base = `/condominiums/${condominiumId}/opportunities/${opportunityId}`;
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ agreed_amount: "", one_time_cost: "0", comment: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function contracted() {
    if (!file) return;
    setBusy(true);
    setError(null);
    const data = new FormData();
    data.append("file", file);
    data.append("agreed_amount", form.agreed_amount.replace(",", "."));
    data.append("one_time_cost", form.one_time_cost.replace(",", ".") || "0");
    if (form.comment.trim()) data.append("comment", form.comment.trim());
    const res = await fetch(`/api${base}/contracted`, { method: "POST", body: data });
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    setBusy(false);
    if (!res.ok) {
      setError(
        typeof body?.detail === "string" ? body.detail : "Não foi possível registrar agora.",
      );
      return;
    }
    setOpen(false);
    router.refresh();
  }

  async function measure() {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}/measurement`);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.refresh();
  }

  if (actions.length === 0) return null;
  return (
    <section aria-label="Acompanhamento da economia" className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {actions.includes("registrar_contratacao") && !open && (
          <Button
            variant="primary"
            icon={<FileSignature size={14} />}
            onClick={() => setOpen(true)}
          >
            Registrar contratação
          </Button>
        )}
        {actions.includes("medir_resultado") && (
          <Button
            variant="secondary"
            icon={<Ruler size={14} />}
            disabled={busy}
            onClick={() => void measure()}
          >
            Medir economia nas faturas
          </Button>
        )}
      </div>
      {open && (
        <div className="space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
          <Field
            id="ct-file"
            label="Documento do acordo"
            required
            hint="Aditivo, proposta aceita ou e-mail do fornecedor confirmando o novo valor."
          >
            <input
              id="ct-file"
              type="file"
              className={controlClass}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="ct-amount" label="Novo valor mensal (R$)" required>
              <input
                id="ct-amount"
                inputMode="decimal"
                className={controlClass}
                value={form.agreed_amount}
                onChange={(e) => setForm({ ...form, agreed_amount: e.target.value })}
              />
            </Field>
            <Field id="ct-cost" label="Custo da mudança (R$)">
              <input
                id="ct-cost"
                inputMode="decimal"
                className={controlClass}
                value={form.one_time_cost}
                onChange={(e) => setForm({ ...form, one_time_cost: e.target.value })}
              />
            </Field>
          </div>
          <Field id="ct-comment" label="Observação">
            <input
              id="ct-comment"
              className={controlClass}
              value={form.comment}
              onChange={(e) => setForm({ ...form, comment: e.target.value })}
            />
          </Field>
          <div className="flex gap-2">
            <Button
              variant="primary"
              disabled={busy || !file || !form.agreed_amount}
              onClick={() => void contracted()}
            >
              Confirmar contratação
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      <p className="text-xs text-muted">
        O CondoOS não paga nem negocia: registra o acordo feito por vocês e confere as faturas
        seguintes.
      </p>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
