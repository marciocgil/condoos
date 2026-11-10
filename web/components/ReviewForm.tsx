"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { buttonClass } from "@/components/ui/Button";
import { controlClass, textareaClass } from "@/components/ui/Field";
import { DOC_TYPE_LABEL } from "@/lib/labels";
import type { FieldSpec, ProvenanceItem, Review } from "@/lib/types";

const INDEXES = [
  ["IPCA", "IPCA"],
  ["IGPM", "IGP-M"],
  ["INPC", "INPC"],
  ["FIXO", "Valor fixo"],
  ["NENHUM", "Sem reajuste"],
  ["OUTRO", "Outro (descreva abaixo)"],
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

  const confOf = (spec: FieldSpec) => (sameType ? review.confidence[spec.name] : undefined);
  const isLow = (spec: FieldSpec) => {
    const conf = confOf(spec);
    return conf === undefined || conf < review.threshold;
  };
  // Why a field is pending: the reason the reading gave for it (D120, A2).
  const reasonOf = (spec: FieldSpec) =>
    sameType
      ? review.reasons.find((r) => r.startsWith(`${spec.label}:`) || r.startsWith(`${spec.label} `))
      : undefined;
  const hasValue = (spec: FieldSpec) => (values[spec.name] ?? "").trim() !== "";
  // D120: a one-off contract needs the total instead of the monthly value and the index.
  const oneOff = (values.natureza ?? "") === "pontual";
  const isRequired = (spec: FieldSpec) => {
    if (docType !== "contrato") return spec.required;
    if (oneOff && (spec.name === "valor_mensal" || spec.name === "indice_reajuste")) return false;
    if (oneOff && spec.name === "valor_total") return true;
    return spec.required;
  };
  const groups: { key: string; title: string; specs: FieldSpec[] }[] = [
    {
      key: "pendentes",
      title: "A conferir",
      specs: specs.filter((s) => isRequired(s) && (isLow(s) || errors[s.name])),
    },
    {
      key: "conferidos",
      title: "Lidos com confiança",
      specs: specs.filter((s) => isRequired(s) && !isLow(s) && !errors[s.name]),
    },
    { key: "opcionais", title: "Opcionais", specs: specs.filter((s) => !isRequired(s)) },
  ];

  function renderField(spec: FieldSpec, group: string) {
    const conf = confOf(spec);
    const optional = group === "opcionais";
    const emptyOptional = optional && !hasValue(spec) && !errors[spec.name];
    const low = !emptyOptional && isLow(spec);
    const reason = reasonOf(spec);
    const id = `f-${spec.name}`;
    const common = {
      id,
      name: spec.name,
      value: values[spec.name] ?? "",
      "aria-invalid": Boolean(errors[spec.name]),
      className: `mt-1 w-full rounded-[var(--radius-control)] border bg-bg-2 px-3 py-2 text-fg ${
        errors[spec.name]
          ? "border-danger"
          : low
            ? "border-warning/60 bg-warning/10"
            : "border-control"
      }`,
    };
    const onChange = (v: string) => setValues((prev) => ({ ...prev, [spec.name]: v }));
    return (
      <div key={spec.name}>
        <label htmlFor={id} className="flex items-baseline justify-between text-sm font-medium">
          <span>
            {spec.label}
            {isRequired(spec) && <span className="text-danger"> *</span>}
          </span>
          {emptyOptional ? (
            <span className="text-xs font-normal text-muted" data-testid={`opt-${spec.name}`}>
              opcional, não encontrado
            </span>
          ) : (
            low && (
              <span className="text-xs font-normal text-warning" data-testid={`low-${spec.name}`}>
                {conf === undefined || conf === 0
                  ? "não encontrado"
                  : `confiança ${Math.round(conf * 100)}%`}
              </span>
            )
          )}
        </label>
        {spec.kind === "list" || spec.name === "discriminacao" || spec.name === "objeto" ? (
          <textarea {...common} rows={3} onChange={(e) => onChange(e.target.value)} />
        ) : spec.kind === "nature" ? (
          <select {...common} onChange={(e) => onChange(e.target.value)}>
            <option value="">—</option>
            <option value="continuo">Contínuo (mensalidade)</option>
            <option value="pontual">Pontual (valor total)</option>
          </select>
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
        {low && reason && !errors[spec.name] && (
          <p className="mt-1 text-xs text-warning" data-testid={`motivo-${spec.name}`}>
            Por que conferir: {reason.slice(spec.label.length).replace(/^[:\s]+/, "")}
          </p>
        )}
        {sameType && <Provenance item={review.provenance?.[spec.name]} />}
        {errors[spec.name] && (
          <p className="mt-1 text-xs text-danger" role="alert">
            {errors[spec.name]}
          </p>
        )}
      </div>
    );
  }

  return (
    <form
      onSubmit={save}
      className="space-y-4 rounded-[var(--radius-card)] border border-line bg-surface p-5"
      noValidate
    >
      <label className="block">
        <span className="text-sm font-medium">Tipo do documento</span>
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className={`mt-1 ${controlClass}`}
        >
          {review.reviewable_types.map((t) => (
            <option key={t} value={t}>
              {DOC_TYPE_LABEL[t] ?? t}
            </option>
          ))}
        </select>
      </label>

      {groups.map(
        (group) =>
          group.specs.length > 0 && (
            <fieldset key={group.key} className="space-y-4" data-testid={`grupo-${group.key}`}>
              <legend className="mb-2 text-xs font-semibold tracking-wide text-fg-2 uppercase">
                {group.title}
              </legend>
              {group.specs.map((spec) => renderField(spec, group.key))}
            </fieldset>
          ),
      )}

      {message && (
        <p role="status" className="text-sm text-danger">
          {message}
        </p>
      )}

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={saving} className={buttonClass("primary")}>
          {saving ? "Salvando…" : "Salvar correção"}
        </button>
        <button
          type="button"
          onClick={() => setDiscarding((d) => !d)}
          className={buttonClass("secondary")}
        >
          Descartar documento
        </button>
      </div>
      {discarding && (
        <div className="space-y-2 rounded-[var(--radius-control)] border border-control p-3">
          <label htmlFor="motivo" className="text-sm font-medium">
            Motivo do descarte
          </label>
          <textarea
            id="motivo"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className={textareaClass}
            placeholder="Ex.: documento de outro condomínio, arquivo duplicado"
          />
          <button type="button" onClick={discard} className={buttonClass("danger", "sm")}>
            Confirmar descarte
          </button>
        </div>
      )}
    </form>
  );
}

const SOURCE_LABEL: Record<string, string> = {
  xml: "XML da nota",
  texto: "texto do documento",
  ia: "leitura por IA",
  pessoa: "conferido por uma pessoa",
  inferido: "presumido por regra, não lido no texto",
};

/** Where the value came from (CB-030): source, page and excerpt; never an invented excerpt. */
function Provenance({ item }: { item?: ProvenanceItem }) {
  if (!item) return null;
  if (item.source === "nao_disponivel")
    return <p className="mt-1 text-xs text-muted">Não disponível no documento.</p>;
  return (
    <p className="mt-1 text-xs text-fg-2">
      {item.status === "confirmado" ? "Confirmado" : "Origem"}:{" "}
      {SOURCE_LABEL[item.source] ?? item.source}
      {item.evidence ? ` · confirmado: ${item.evidence}` : ""}
      {item.page ? ` · pág. ${item.page}` : ""}
      {item.excerpt ? (
        <>
          {" "}
          — <q className="text-muted">{item.excerpt}</q>
        </>
      ) : item.source === "ia" ? (
        " · trecho não localizado no texto: confira no arquivo"
      ) : item.source === "inferido" && item.rule ? (
        ` — ${item.rule}`
      ) : null}
    </p>
  );
}
