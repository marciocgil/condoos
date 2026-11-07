"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { ActionDetail, ActionPayload, ActionTypes } from "@/lib/types";

export interface ActionDraft {
  action_type: string;
  title: string;
  cost_cap: string;
  payload: ActionPayload;
}

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Ask for an action (D83), or adjust one that is still open. The approver will see exactly
 * these fields; nothing is sent by the system. */
export function ActionForm({
  condominiumId,
  types,
  caseId,
  initial,
  actionId,
  detailPath,
  onDone,
}: {
  condominiumId: string;
  types: ActionTypes["types"];
  caseId?: string;
  initial?: ActionDraft;
  actionId?: string; // adjusting an existing request
  detailPath: string; // "{id}" is replaced
  onDone?: () => void;
}) {
  const router = useRouter();
  const [key] = useState(newKey); // one key per form: a double click never creates two
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [form, setForm] = useState<ActionDraft>(
    initial ?? {
      action_type: types[0]?.code ?? "",
      title: "",
      cost_cap: "0",
      payload: { effect: "", reason: "", executor: "", due_date: "", risks: "" },
    },
  );
  const type = types.find((t) => t.code === form.action_type);
  const set = (field: keyof ActionPayload, value: string) =>
    setForm({ ...form, payload: { ...form.payload, [field]: value } });

  async function submit() {
    setBusy(true);
    setError(null);
    const payload: ActionPayload = {
      effect: form.payload.effect.trim(),
      reason: form.payload.reason.trim(),
      executor: form.payload.executor.trim(),
      due_date: form.payload.due_date || null,
      risks: (form.payload.risks ?? "").trim(),
    };
    const cost = form.cost_cap.replace(",", ".") || "0";
    const base = `/condominiums/${condominiumId}/actions`;
    const r = actionId
      ? await send<ActionDetail>("PATCH", `${base}/${actionId}`, {
          title: form.title,
          payload,
          cost_cap: cost,
          comment: comment || undefined,
        })
      : await send<ActionDetail>("POST", base, {
          action_type: form.action_type,
          title: form.title,
          payload,
          cost_cap: cost,
          idempotency_key: key,
          case_id: caseId,
        });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    if (onDone) {
      onDone();
      router.refresh();
    } else {
      router.push(detailPath.replace("{id}", r.data.id));
    }
  }

  const ready =
    form.title.trim().length >= 5 &&
    form.payload.effect.trim().length >= 10 &&
    form.payload.reason.trim().length >= 10 &&
    form.payload.executor.trim().length >= 3;

  return (
    <Card>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {!actionId && (
          <Field id="a-type" label="Tipo de ação" required>
            <select
              id="a-type"
              className={controlClass}
              value={form.action_type}
              onChange={(e) => setForm({ ...form, action_type: e.target.value })}
            >
              {types.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field id="a-title" label="O que será autorizado" required>
          <input
            id="a-title"
            className={controlClass}
            value={form.title}
            maxLength={200}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </Field>
        <Field
          id="a-effect"
          label="Efeito exato depois da aprovação"
          required
          hint="Escreva o que exatamente será feito. Uma aprovação genérica não autoriza nada além disso."
        >
          <textarea
            id="a-effect"
            rows={3}
            className={textareaClass}
            value={form.payload.effect}
            onChange={(e) => set("effect", e.target.value)}
          />
        </Field>
        <Field id="a-reason" label="Por quê, e o impacto de não agir" required>
          <textarea
            id="a-reason"
            rows={2}
            className={textareaClass}
            value={form.payload.reason}
            onChange={(e) => set("reason", e.target.value)}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="a-executor" label="Quem executará" required>
            <input
              id="a-executor"
              className={controlClass}
              value={form.payload.executor}
              onChange={(e) => set("executor", e.target.value)}
            />
          </Field>
          <Field id="a-due" label="Prazo">
            <input
              id="a-due"
              type="date"
              className={controlClass}
              value={form.payload.due_date ?? ""}
              onChange={(e) => set("due_date", e.target.value)}
            />
          </Field>
        </div>
        <Field
          id="a-cost"
          label="Teto de custo (R$)"
          required
          hint={
            type?.zero_cost_only
              ? "Este tipo só é permitido sem custo (R$ 0,00)."
              : "Inclusive se for R$ 0,00. Custo acima do teto exige nova aprovação."
          }
        >
          <input
            id="a-cost"
            inputMode="decimal"
            className={controlClass}
            value={form.cost_cap}
            onChange={(e) => setForm({ ...form, cost_cap: e.target.value })}
          />
        </Field>
        <Field id="a-risks" label="Riscos, exceções e alternativas">
          <textarea
            id="a-risks"
            rows={2}
            className={textareaClass}
            value={form.payload.risks ?? ""}
            onChange={(e) => set("risks", e.target.value)}
          />
        </Field>
        {actionId && (
          <Field id="a-comment" label="O que mudou">
            <input
              id="a-comment"
              className={controlClass}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </Field>
        )}
        <p className="text-xs text-muted">
          O CondoOS não envia nada a ninguém: depois da aprovação, uma pessoa executa e registra o
          que foi feito. Pagamento, contratação e multa nunca passam por aqui.
        </p>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <Button type="submit" variant="primary" disabled={busy || !ready}>
            {actionId ? "Salvar ajuste" : "Enviar para aprovação"}
          </Button>
          {onDone && (
            <Button type="button" variant="ghost" onClick={onDone}>
              Cancelar
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
