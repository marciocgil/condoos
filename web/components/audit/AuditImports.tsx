"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";

const KINDS = [
  ["unidades", "Unidades", "unidade; bloco; fracao"],
  [
    "titulos",
    "Títulos (boletos)",
    "unidade; competencia; tipo; valor; vencimento; nosso numero; situacao; data pagamento; valor pago; competencia consumo",
  ],
  [
    "leituras",
    "Leituras de consumo",
    "unidade; competencia; servico; leitura anterior; leitura atual; consumo",
  ],
] as const;

type Result = {
  criados: number;
  atualizados: number;
  colunas_descartadas: string[];
  erros: string[];
};

/** CSV imports of units, titles and readings (D123). Name, document, e-mail and phone columns
 * are dropped before anything is stored. */
export function AuditImports({ condominiumId }: { condominiumId: string }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(kind: string, file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`/api/condominiums/${condominiumId}/audit/imports/${kind}`, {
      method: "POST",
      body: form,
    });
    setBusy(false);
    const body = (await res.json().catch(() => null)) as (Result & { detail?: string }) | null;
    if (!res.ok || !body) {
      setMessage(typeof body?.detail === "string" ? body.detail : "Não foi possível importar.");
      return;
    }
    const dropped = body.colunas_descartadas.length
      ? ` Colunas descartadas (não guardadas): ${body.colunas_descartadas.join(", ")}.`
      : "";
    const errors = body.erros.length
      ? ` ${body.erros.length} linha(s) com erro: ${body.erros.slice(0, 3).join(" ")}`
      : "";
    setMessage(`${body.criados} criado(s), ${body.atualizados} atualizado(s).${dropped}${errors}`);
    router.refresh();
  }

  return (
    <div className="space-y-3" data-testid="audit-imports">
      {KINDS.map(([kind, label, columns]) => (
        <div key={kind} className="flex flex-wrap items-center gap-3">
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label={`Importar ${label}`}
              disabled={busy}
              onChange={(e) => void upload(kind, e.target.files?.[0])}
            />
            <span className="inline-flex h-9 items-center gap-2 rounded-[var(--radius-button)] border border-control px-3 text-sm">
              <Upload size={14} aria-hidden /> {label}
            </span>
          </label>
          <span className="text-xs text-fg-2">Colunas: {columns}</span>
        </div>
      ))}
      <p className="text-xs text-fg-2">
        Colunas de nome, CPF, documento, e-mail ou telefone são descartadas antes de guardar. Fica
        guardada só a cópia sem nomes.
      </p>
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
      {busy && <Button disabled>Importando…</Button>}
    </div>
  );
}
