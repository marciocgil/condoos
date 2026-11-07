"use client";

import { AlertTriangle, CheckCircle2, Copy, Loader2, UploadCloud, XCircle } from "lucide-react";
import { useEffect, useState, type ChangeEvent, type ReactNode } from "react";

import { DOC_TYPE_LABEL } from "@/lib/labels";
import type { DocumentStatus, UploadResult } from "@/lib/types";

const ACCEPT = ".pdf,.xml,.ofx,.csv,.ret,.txt,image/jpeg,image/png,image/webp";
const POLL_MS = 2500;
const MAX_POLLS = 72; // three minutes; then the page says the reading goes on

const STATUS: Record<DocumentStatus["status"], { icon: ReactNode; tone: string }> = {
  lendo: { icon: <Loader2 size={14} className="animate-spin" />, tone: "text-fg-2" },
  lido: { icon: <CheckCircle2 size={14} className="text-success" />, tone: "text-fg-2" },
  revisao: { icon: <AlertTriangle size={14} className="text-warning" />, tone: "text-fg-2" },
  falhou: { icon: <XCircle size={14} />, tone: "text-danger" },
};

/** Upload of one or many files with follow-up (LB-033, D96): after sending, each file says
 * where it stands — reading, read (with its type), for review (with the reason) or could not
 * read — and a summary counts them. Duplicates and refused files say so at once. */
export function UploadForm({ condominiumId }: { condominiumId: string }) {
  const [results, setResults] = useState<UploadResult[]>([]);
  const [statuses, setStatuses] = useState<Record<string, DocumentStatus>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);

  const followed = results
    .filter((r) => r.document_id && !r.duplicate && !r.error)
    .map((r) => r.document_id as string);
  const key = followed.join(",");

  useEffect(() => {
    if (!key) return;
    let stop = false;
    let polls = 0;
    async function poll() {
      if (stop) return;
      polls += 1;
      try {
        const res = await fetch(
          `/api/condominiums/${condominiumId}/documents/status?ids=${encodeURIComponent(key)}`,
        );
        if (res.ok) {
          const list = (await res.json()) as DocumentStatus[];
          setStatuses(Object.fromEntries(list.map((d) => [d.id, d])));
          if (list.every((d) => d.status !== "lendo")) return;
        }
      } catch {
        // a network blip: try again on the next tick
      }
      if (polls >= MAX_POLLS) {
        setSlow(true);
        return;
      }
      setTimeout(() => void poll(), POLL_MS);
    }
    void poll();
    return () => {
      stop = true;
    };
  }, [condominiumId, key]);

  async function send(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    setStatuses({});
    setSlow(false);
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

  const known = Object.values(statuses);
  const count = (s: DocumentStatus["status"]) => known.filter((d) => d.status === s).length;
  const summary =
    followed.length > 0
      ? [
          `${count("lido")} de ${followed.length} lidos`,
          count("revisao") ? `${count("revisao")} para revisão` : null,
          count("falhou") ? `${count("falhou")} sem leitura` : null,
          followed.length - known.length + count("lendo")
            ? `${followed.length - known.length + count("lendo")} ainda lendo`
            : null,
        ]
          .filter(Boolean)
          .join(" · ")
      : null;

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
          Notas, boletos, recibos, contratos (PDF, foto ou XML) e extratos (OFX, CSV, CNAB). Pode
          enviar vários de uma vez: eu acompanho cada um.
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
      {summary && (
        <p role="status" className="text-sm text-fg-2" data-testid="upload-summary">
          {summary}
          {slow && " · a leitura continua; o resultado fica guardado."}
        </p>
      )}
      {results.length > 0 && (
        <ul
          className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface text-sm"
          aria-label="Resultado do envio"
        >
          {results.map((r, i) => {
            const st = r.document_id ? statuses[r.document_id] : undefined;
            const shown = r.error
              ? { icon: <XCircle size={14} />, tone: "text-danger", text: r.error }
              : r.duplicate
                ? { icon: <Copy size={14} />, tone: "text-fg-2", text: "Já recebido antes" }
                : st
                  ? {
                      ...STATUS[st.status],
                      text:
                        st.status === "lido"
                          ? `Lido: ${DOC_TYPE_LABEL[st.doc_type] ?? st.doc_type}`
                          : st.detail,
                    }
                  : { ...STATUS.lendo, text: "Recebido · lendo…" };
            return (
              <li
                key={`${r.filename}-${i}`}
                className="flex items-start justify-between gap-3 px-4 py-3"
                data-status={st?.status ?? (r.error ? "erro" : r.duplicate ? "repetido" : "lendo")}
              >
                <span className="break-all">{r.filename}</span>
                <span
                  className={`inline-flex max-w-[60%] shrink-0 items-start gap-1 text-right ${shown.tone}`}
                >
                  <span aria-hidden className="mt-0.5">
                    {shown.icon}
                  </span>
                  {shown.text}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
