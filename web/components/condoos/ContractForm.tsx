"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";

const INDEXES = [
  ["IPCA", "IPCA"],
  ["IGPM", "IGP-M"],
  ["INPC", "INPC"],
  ["FIXO", "Fixo (sem índice)"],
  ["NENHUM", "Sem reajuste"],
  ["OUTRO", "Outro (descrever)"],
] as const;
const MONTHS = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

export interface ContractFormValues {
  supplier_cnpj: string;
  supplier_name: string;
  object: string;
  scope: string; // one item per line
  monthly_value: string;
  adjustment_index: string;
  adjustment_index_other: string;
  adjustment_base_month: string;
  start_date: string;
  end_date: string;
  indeterminate: boolean;
  billing_frequency_months: string;
}

export const EMPTY_CONTRACT: ContractFormValues = {
  supplier_cnpj: "",
  supplier_name: "",
  object: "",
  scope: "",
  monthly_value: "",
  adjustment_index: "IPCA",
  adjustment_index_other: "",
  adjustment_base_month: "",
  start_date: "",
  end_date: "",
  indeterminate: true, // most condominium contracts have no end date
  billing_frequency_months: "1",
};

const FREQUENCIES = [
  ["1", "Mensal"],
  ["2", "Bimestral"],
  ["3", "Trimestral"],
  ["6", "Semestral"],
  ["12", "Anual"],
  ["0", "Sob demanda (sem faturamento fixo)"],
] as const;

/** Typed registration of a contract, for when there is no document to send (D67). */
export function ContractForm({
  condominiumId,
  contractId,
  initial,
}: {
  condominiumId: string;
  contractId?: string;
  initial: ContractFormValues;
}) {
  const router = useRouter();
  const [f, setF] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const indexed = ["IPCA", "IGPM", "INPC", "OUTRO"].includes(f.adjustment_index);
  // D68: without another month in the contract, the adjustment is in the start month.
  const startMonth = f.start_date ? String(Number(f.start_date.slice(5, 7))) : "";

  async function save() {
    setBusy(true);
    setError(null);
    const body = {
      supplier_cnpj: f.supplier_cnpj,
      supplier_name: f.supplier_name,
      object: f.object,
      scope_items: f.scope
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      monthly_value: f.monthly_value,
      adjustment_index: f.adjustment_index,
      adjustment_base_month:
        indexed && f.adjustment_base_month ? Number(f.adjustment_base_month) : null,
      start_date: f.start_date,
      end_date: f.end_date || null,
    };
    const r = contractId
      ? await send("PUT", `/condominiums/${condominiumId}/contracts/${contractId}`, body)
      : await send("POST", `/condominiums/${condominiumId}/contracts`, body);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.push("/admin/contratos");
    router.refresh();
  }

  const set = (k: keyof ContractFormValues) => (e: { target: { value: string } }) =>
    setF({ ...f, [k]: e.target.value });

  return (
    <Card className="max-w-2xl">
      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="c-cnpj" label="CNPJ do fornecedor" required>
            <input
              id="c-cnpj"
              className={controlClass}
              value={f.supplier_cnpj}
              onChange={set("supplier_cnpj")}
              placeholder="00.000.000/0000-00"
            />
          </Field>
          <Field id="c-supplier" label="Razão social" required>
            <input
              id="c-supplier"
              className={controlClass}
              value={f.supplier_name}
              onChange={set("supplier_name")}
            />
          </Field>
        </div>
        <Field id="c-object" label="Objeto" required>
          <input
            id="c-object"
            className={controlClass}
            value={f.object}
            onChange={set("object")}
            placeholder="Ex.: Portaria 24 horas"
          />
        </Field>
        <Field
          id="c-scope"
          label="Itens do escopo"
          hint="Um por linha. Usados na regra de serviço fora do escopo (R04)."
        >
          <textarea
            id="c-scope"
            rows={3}
            className={`${controlClass} h-auto py-2`}
            value={f.scope}
            onChange={set("scope")}
          />
        </Field>
        <div className="grid gap-4 md:grid-cols-3">
          <Field id="c-value" label="Valor mensal (R$)" required>
            <input
              id="c-value"
              inputMode="decimal"
              className={controlClass}
              value={f.monthly_value}
              onChange={set("monthly_value")}
              placeholder="1.250,00"
            />
          </Field>
          <Field id="c-index" label="Índice de reajuste" required>
            <select
              id="c-index"
              className={controlClass}
              value={f.adjustment_index}
              onChange={set("adjustment_index")}
            >
              {INDEXES.map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="c-base" label="Mês do reajuste" hint="Padrão: mês do início da vigência.">
            <select
              id="c-base"
              className={controlClass}
              value={f.adjustment_base_month}
              onChange={set("adjustment_base_month")}
              disabled={!indexed}
            >
              <option value="">
                {startMonth ? `Mês do início (${MONTHS[Number(startMonth) - 1]})` : "Mês do início"}
              </option>
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field
          id="c-freq"
          label="Faturamento"
          hint="Em quais meses deve chegar NF deste contrato (acompanhado em Pendências)."
        >
          <select
            id="c-freq"
            className={controlClass}
            value={f.billing_frequency_months}
            onChange={set("billing_frequency_months")}
          >
            {FREQUENCIES.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {f.adjustment_index === "OUTRO" && (
          <Field
            id="c-other"
            label="Qual índice ou critério"
            required
            hint="Ex.: IGP-DI, IPC-Fipe, dissídio coletivo da categoria."
          >
            <input
              id="c-other"
              className={controlClass}
              maxLength={120}
              value={f.adjustment_index_other}
              onChange={set("adjustment_index_other")}
            />
          </Field>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            id="c-start"
            label="Início da vigência"
            required
            hint="Se o contrato não informar, use a data da assinatura."
          >
            <input
              id="c-start"
              type="date"
              className={controlClass}
              value={f.start_date}
              onChange={set("start_date")}
            />
          </Field>
          <Field id="c-end" label="Fim da vigência">
            <label className="mb-2 flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={f.indeterminate}
                onChange={(e) => setF({ ...f, indeterminate: e.target.checked })}
              />
              Prazo indeterminado
            </label>
            {!f.indeterminate && (
              <input
                id="c-end"
                type="date"
                className={controlClass}
                value={f.end_date}
                onChange={set("end_date")}
              />
            )}
          </Field>
        </div>
        {error && (
          <p role="alert" className="text-[13px] text-danger">
            {error}
          </p>
        )}
        <p className="text-xs text-muted">
          Ao salvar, as regras dos meses em aberto são reavaliadas com os novos termos.
        </p>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => void save()} disabled={busy}>
            {busy ? "Salvando…" : contractId ? "Salvar alterações" : "Cadastrar contrato"}
          </Button>
          <Button variant="ghost" onClick={() => router.push("/admin/contratos")}>
            Cancelar
          </Button>
        </div>
      </div>
    </Card>
  );
}
