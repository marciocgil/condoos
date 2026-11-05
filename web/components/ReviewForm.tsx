"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { DOC_TYPE_LABEL } from "@/lib/labels";
import type { FieldSpec, Review } from "@/lib/types";

const INDEXES = [
  ["IPCA", "IPCA"],
  ["IGPM", "IGP-M"],
  ["INPC", "INPC"],
  ["FIXO", "Valor fixo"],
  ["NENHUM", "Sem reajuste"],
] as const;

function toInput(spec: FieldSpec, value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join("\n");
  return String(value);
}

function fromInput(spec: FieldSpec, raw: string): unknown {
  const v = raw.trim();
  if (!v) return null;
  if (spec.kind === "list")
    return v
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
  return v;
}

export function ReviewForm({ review }: { review: Review }) {
  const router = useRouter();
  const [docType, setDocType] = useState(
    review.reviewable_types.includes(review.doc_type)
      ? review.doc_type
      : (review.reviewable_types[0] ?? ""),
  );
  const [values, setValues] = useState<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const specs of Object.values(review.fields_by_type)) {
      for (const spec of specs) out[spec.name] = toInput(spec, review.values[spec.name]);
    }
    return out;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [reason, setReason] = useState("");

  const specs = review.fields_by_type[docType] ?? [];
  const sameType = docType === review.doc_type;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setErrors({});
    setMessage(null);
    const payload: Record<string, unknown> = {};
    for (const spec of specs) payload[spec.name] = fromInput(spec, values[spec.name] ?? "");
    const res = await fetch(
      `/api/condominiums/${review.condominium_id}/documents/${review.document_id}/review`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ doc_type: docType, values: payload }),
      },
    );
    setSaving(false);
    if (res.ok) {
      router.push("/admin/fila");
      router.refresh();
      return;
    }
    const body = (await res.json().catch(() => null)) as {
      detail?: { message?: string; fields?: Record<string, string> } | string;
    } | null;
    if (body && typeof body.detail === "object" && body.detail) {
      setErrors(body.detail.fields ?? {});
      setMessage(body.detail.message ?? "Verifique os campos.");
    } else {
      setMessage(typeof body?.detail === "string" ? body.detail : "Não foi possível salvar.");
    }
  }

  async function discard() {
    const res = await fetch(
      `/api/condominiums/${review.condominium_id}/documents/${review.document_id}/review/discard`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ motivo: reason }),
      },
    );
    if (res.ok) {
      router.push("/admin/fila");
      router.refresh();
    } else {
      setMessage("Informe o motivo do descarte (mínimo de 5 caracteres).");
    }
  }

  return (
    <form onSubmit={save} className="space-y-4 rounded-xl bg-white p-5 shadow-sm" noValidate>
      <label className="block">
        <span className="text-sm font-medium">Tipo do documento</span>
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2"
        >
          {review.reviewable_types.map((t) => (
            <option key={t} value={t}>
              {DOC_TYPE_LABEL[t] ?? t}
            </option>
          ))}
        </select>
      </label>

      {specs.map((spec) => {
        const conf = sameType ? review.confidence[spec.name] : undefined;
        const low = conf === undefined || conf < review.threshold;
        const id = `f-${spec.name}`;
        const common = {
          id,
          name: spec.name,
          value: values[spec.name] ?? "",
          "aria-invalid": Boolean(errors[spec.name]),
          className: `mt-1 w-full rounded-lg border px-3 py-2 ${
            errors[spec.name]
              ? "border-red-500"
              : low
                ? "border-amber-400 bg-amber-50"
                : "border-gray-300"
          }`,
        };
        const onChange = (v: string) => setValues((prev) => ({ ...prev, [spec.name]: v }));
        return (
          <div key={spec.name}>
            <label htmlFor={id} className="flex items-baseline justify-between text-sm font-medium">
              <span>
                {spec.label}
                {spec.required && <span className="text-red-600"> *</span>}
              </span>
              {low && (
                <span
                  className="text-xs font-normal text-amber-700"
                  data-testid={`low-${spec.name}`}
                >
                  {conf === undefined || conf === 0
                    ? "não encontrado"
                    : `confiança ${Math.round(conf * 100)}%`}
                </span>
              )}
            </label>
            {spec.kind === "list" || spec.name === "discriminacao" || spec.name === "objeto" ? (
              <textarea {...common} rows={3} onChange={(e) => onChange(e.target.value)} />
            ) : spec.kind === "index" ? (
              <select {...common} onChange={(e) => onChange(e.target.value)}>
                <option value="">—</option>
                {INDEXES.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            ) : (
              <input
                {...common}
                type={spec.kind === "date" ? "date" : spec.kind === "month" ? "month" : "text"}
                inputMode={
                  spec.kind === "money" || spec.kind === "cnpj" || spec.kind === "doc"
                    ? "decimal"
                    : undefined
                }
                onChange={(e) => onChange(e.target.value)}
              />
            )}
            {errors[spec.name] && (
              <p className="mt-1 text-xs text-red-700" role="alert">
                {errors[spec.name]}
              </p>
            )}
          </div>
        );
      })}

      {message && (
        <p role="status" className="text-sm text-red-700">
          {message}
        </p>
      )}

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-brand-600 px-5 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {saving ? "Salvando…" : "Salvar correção"}
        </button>
        <button
          type="button"
          onClick={() => setDiscarding((d) => !d)}
          className="rounded-lg border border-gray-300 px-5 py-2 text-gray-700"
        >
          Descartar documento
        </button>
      </div>
      {discarding && (
        <div className="space-y-2 rounded-lg border border-gray-200 p-3">
          <label htmlFor="motivo" className="text-sm font-medium">
            Motivo do descarte
          </label>
          <textarea
            id="motivo"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
            placeholder="Ex.: documento de outro condomínio, arquivo duplicado"
          />
          <button
            type="button"
            onClick={discard}
            className="rounded-lg bg-gray-800 px-4 py-2 text-sm text-white"
          >
            Confirmar descarte
          </button>
        </div>
      )}
    </form>
  );
}
