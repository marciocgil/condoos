"use client";

import { CheckCircle2, Copy, UploadCloud, XCircle } from "lucide-react";
import { useState, type ChangeEvent } from "react";

import { BatchProgress } from "@/components/condoos/BatchProgress";
import { FirstValueCard } from "@/components/condoos/FirstValueCard";
import { Button } from "@/components/ui/Button";
import type { UploadResult } from "@/lib/types";

// The first-value card follows at most this many new documents of one upload (LB-007).
const MAX_CARDS = 3;
/** What to do about a refused file (LB-022): the API says why, this says how to fix it. */
function remedy(error: string): string {
  if (error.startsWith("Arquivo vazio"))
    return "Escolha o arquivo de novo; ele chegou sem conteúdo.";
  if (error.startsWith("Arquivo maior"))
    return "Envie só as páginas necessárias ou uma versão comprimida do PDF.";
  if (error.includes("não aceito")) return "Envie em PDF, foto (JPG, PNG), XML, OFX, CSV ou CNAB.";
  return "Tente de novo com o arquivo original.";
}

const ACCEPT = ".pdf,.xml,.ofx,.csv,.ret,.txt,image/jpeg,image/png,image/webp";

export function UploadForm({ condominiumId }: { condominiumId: string }) {
  const [results, setResults] = useState<UploadResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    try {
      const res = await fetch(`/api/condominiums/${condominiumId}/documents`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) setError("Não foi possível enviar. Tente de novo.");
      else setResults((await res.json()) as UploadResult[]);
    } catch {
      setError("Sem conexão. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <label
        className="transition-ui flex cursor-pointer flex-col items-center justify-center rounded-[var(--radius-card)] border-2 border-dashed border-control bg-surface px-4 py-10 text-center hover:border-accent"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void send(e.dataTransfer.files);
        }}
      >
        <UploadCloud size={28} aria-hidden className="mb-2 text-fg-2" />
        <span className="font-medium">
          {busy ? "Enviando…" : "Toque para escolher ou tire uma foto"}
        </span>
        <span className="mt-1 text-[13px] text-fg-2">
          Notas, boletos, recibos, contratos, convenção, atas, apólices, laudos e balancetes (PDF,
          foto ou XML) e extratos (OFX, CSV, CNAB)
        </span>
        <input
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          aria-label="Escolher arquivos"
          disabled={busy}
          onChange={(e: ChangeEvent<HTMLInputElement>) => void send(e.target.files)}
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {results.length > 0 && (
        <ul
          className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface text-sm"
          aria-label="Resultado do envio"
        >
          {results.map((r, i) => (
            <li
              key={`${r.filename}-${i}`}
              className="flex items-start justify-between gap-3 px-4 py-3"
            >
              <span className="min-w-0 break-all">
                {r.filename}
                {r.error && (
                  <span className="mt-0.5 block text-[13px] break-normal text-fg-2">
                    {remedy(r.error)}
                  </span>
                )}
              </span>
              <span
                className={`inline-flex shrink-0 items-center gap-1 ${r.error ? "text-danger" : "text-fg-2"}`}
              >
                {r.error ? (
                  <XCircle size={14} aria-hidden />
                ) : r.duplicate ? (
                  <Copy size={14} aria-hidden />
                ) : (
                  <CheckCircle2 size={14} aria-hidden className="text-success" />
                )}
                {r.error ?? (r.duplicate ? "Já recebido antes" : "Recebido")}
              </span>
            </li>
          ))}
        </ul>
      )}
      {results.filter((r) => r.document_id && !r.error).length > 1 && (
        <BatchProgress
          condominiumId={condominiumId}
          documentIds={results
            .filter((r) => r.document_id && !r.error)
            .map((r) => r.document_id as string)}
        />
      )}
      {results
        .filter((r) => r.document_id && !r.error)
        .slice(0, MAX_CARDS)
        .map((r) => (
          <FirstValueCard
            key={r.document_id}
            condominiumId={condominiumId}
            documentId={r.document_id as string}
            duplicate={r.duplicate}
          />
        ))}
      {results.some((r) => r.document_id && !r.error) && (
        // One way back to the guide after any upload (LB-080, D108). A full load, so Hoje
        // shows what was just sent (in review, next step) and never a cached copy.
        <Button
          variant="primary"
          data-testid="continue-guide"
          onClick={() => window.location.assign(`/condominio/${condominiumId}/resumo`)}
        >
          Continuar o guia
        </Button>
      )}
    </div>
  );
}
