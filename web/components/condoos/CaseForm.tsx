"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { CASE_CATEGORY_LABEL, CASE_SEVERITY_LABEL, CASE_STATUS_LABEL } from "@/lib/labels";

interface Candidate {
  id: string;
  number: string;
  title: string;
  status: string;
}

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Opens a case (D75). Possible duplicates come back before anything is written: the
 * person links to the existing case or explains why this one is different. */
export function CaseForm({
  condos,
  finding,
  opportunity,
  detailPath,
  initialTitle,
}: {
  condos: { id: string; name: string }[];
  /** Prefill from another screen (e.g. renewing a compliance document, D112). */
  initialTitle?: string;
  finding?: { id: string; title: string; condominiumId: string };
  opportunity?: { id: string; title: string; condominiumId: string };
  /** e.g. "/condominio/{condo}/assuntos/{case}" (a string: functions cannot cross to the client). */
  detailPath: string;
}) {
  const detailHref = (condoId: string, caseId: string) =>
    detailPath.replace("{condo}", condoId).replace("{case}", caseId);
  const router = useRouter();
  const source = finding
    ? { type: "finding", origin: "finding", label: "achado", ...finding }
    : opportunity
      ? { type: "opportunity", origin: "opportunity", label: "oportunidade", ...opportunity }
      : null;
  const [condo, setCondo] = useState(source?.condominiumId ?? condos[0]?.id ?? "");
  const [form, setForm] = useState({
    title: source ? `Tratar: ${source.title}`.slice(0, 200) : (initialTitle ?? "").slice(0, 200),
    description: "",
    category: opportunity ? "contrato" : finding ? "financeiro" : "manutencao",
    severity: "media",
    next_action: "",
    next_action_due_at: inDays(7),
    resolution_criterion: "",
    requires_evidence: true,
  });
  const [linkReason, setLinkReason] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [anyway, setAnyway] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    const body = {
      ...form,
      origin: source ? source.origin : "human_request",
      links: source
        ? [{ target_type: source.type, target_id: source.id, reason: linkReason || undefined }]
        : [],
      create_anyway_reason: anyway || undefined,
    };
    try {
      const res = await fetch(`/api/condominiums/${condo}/cases`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (res.status === 409 && data?.candidates) {
        setCandidates(data.candidates);
        setError(String(data.detail));
      } else if (!res.ok) {
        const d = data?.detail;
        setError(
          typeof d === "string"
            ? d
            : (d?.message ??
                (Array.isArray(d)
                  ? d.map((x: { msg?: string }) => x.msg).join("; ")
                  : "Não foi possível abrir o assunto.")),
        );
      } else {
        router.push(detailHref(condo, data.id));
        router.refresh();
        return;
      }
    } catch {
      setError("Sem conexão com o servidor. Tente de novo.");
    }
    setBusy(false);
  }

  const set = (k: keyof typeof form) => (v: string | boolean) => setForm({ ...form, [k]: v });
  return (
    <Card>
      <CardTitle>Novo assunto</CardTitle>
      <div className="space-y-3">
        {source && (
          <p className="text-[13px] text-fg-2">
            A partir {source.type === "finding" ? "do achado" : "da oportunidade"}{" "}
            <q>{source.title}</q>. Ele continua com o próprio ciclo.
          </p>
        )}
        {condos.length > 1 && !source && (
          <Field id="c-condo" label="Condomínio" required>
            <select
              id="c-condo"
              className={controlClass}
              value={condo}
              onChange={(e) => setCondo(e.target.value)}
            >
              {condos.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field id="c-title" label="Título" required>
          <input
            id="c-title"
            className={controlClass}
            value={form.title}
            onChange={(e) => set("title")(e.target.value)}
          />
        </Field>
        <Field id="c-description" label="Descrição">
          <textarea
            id="c-description"
            rows={3}
            className={textareaClass}
            value={form.description}
            onChange={(e) => set("description")(e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field id="c-category" label="Categoria" required>
            <select
              id="c-category"
              className={controlClass}
              value={form.category}
              onChange={(e) => set("category")(e.target.value)}
            >
              {Object.entries(CASE_CATEGORY_LABEL).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field id="c-severity" label="Criticidade" required>
            <select
              id="c-severity"
              className={controlClass}
              value={form.severity}
              onChange={(e) => set("severity")(e.target.value)}
            >
              {Object.entries(CASE_SEVERITY_LABEL).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field id="c-next" label="Próxima ação" required hint="O que precisa acontecer agora.">
          <input
            id="c-next"
            className={controlClass}
            value={form.next_action}
            onChange={(e) => set("next_action")(e.target.value)}
          />
        </Field>
        <Field id="c-due" label="Prazo da próxima ação" required>
          <input
            id="c-due"
            type="date"
            className={controlClass}
            value={form.next_action_due_at}
            onChange={(e) => set("next_action_due_at")(e.target.value)}
          />
        </Field>
        <Field
          id="c-criterion"
          label="Critério de conclusão"
          required
          hint="O que comprova que o assunto foi resolvido."
        >
          <input
            id="c-criterion"
            className={controlClass}
            value={form.resolution_criterion}
            onChange={(e) => set("resolution_criterion")(e.target.value)}
          />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.requires_evidence}
            onChange={(e) => set("requires_evidence")(e.target.checked)}
          />
          Exigir evidência para resolver
        </label>
        {candidates.length > 0 && (
          <div
            role="alert"
            className="space-y-2 rounded-[var(--radius-card)] border border-warning/60 bg-bg-2 p-3"
          >
            <p className="text-sm font-medium">Pode já existir um assunto para isso:</p>
            <ul className="space-y-1 text-sm">
              {candidates.map((c) => (
                <li key={c.id}>
                  <a className="underline" href={detailHref(condo, c.id)}>
                    {c.number} — {c.title}
                  </a>{" "}
                  <span className="text-xs text-muted">
                    ({CASE_STATUS_LABEL[c.status] ?? c.status})
                  </span>
                </li>
              ))}
            </ul>
            <Field
              id="c-anyway"
              label="Por que abrir outro assunto?"
              hint="Obrigatório para seguir."
            >
              <input
                id="c-anyway"
                className={controlClass}
                value={anyway}
                onChange={(e) => setAnyway(e.target.value)}
              />
            </Field>
            {source && (
              <Field
                id="c-link-reason"
                label={`Por que ${source.type === "finding" ? "o achado" : "a oportunidade"} também pertence a este assunto?`}
              >
                <input
                  id="c-link-reason"
                  className={controlClass}
                  value={linkReason}
                  onChange={(e) => setLinkReason(e.target.value)}
                />
              </Field>
            )}
          </div>
        )}
        {error && candidates.length === 0 && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Button variant="primary" disabled={busy} onClick={() => void submit()}>
          Abrir assunto
        </Button>
      </div>
    </Card>
  );
}
