"use client";

import { CheckCircle2, Copy, UploadCloud, XCircle } from "lucide-react";
import { useState, type ChangeEvent } from "react";

interface Received {
  filename: string;
  accepted: boolean;
  duplicate: boolean;
  error: string | null;
}

/** Send-only upload of a delegation link (D97): says what was received, nothing more. */
export function PublicUpload({ token }: { token: string }) {
  const [results, setResults] = useState<Received[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const res = await fetch(`/api/submit/${encodeURIComponent(token)}`, {
        method: "POST",
        body: form,
      });
      const data = (await res.json().catch(() => null)) as Received[] | { detail?: string } | null;
      if (!res.ok || !Array.isArray(data)) {
        setError(
          (data && !Array.isArray(data) && typeof data.detail === "string" && data.detail) ||
            "Não foi possível enviar. Tente de novo.",
        );
      } else setResults((prev) => [...data, ...prev]);
    } catch {
      setError("Sem conexão. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <label className="transition-ui flex cursor-pointer flex-col items-center justify-center rounded-[var(--radius-card)] border-2 border-dashed border-control bg-surface px-4 py-10 text-center hover:border-accent">
        <UploadCloud size={28} aria-hidden className="mb-2 text-fg-2" />
        <span className="font-medium">{busy ? "Enviando…" : "Escolher arquivos"}</span>
        <span className="mt-1 text-[13px] text-fg-2">Até 10 de cada vez.</span>
        <input
          type="file"
          multiple
          accept=".pdf,.xml,image/jpeg,image/png,image/webp"
          className="sr-only"
          aria-label="Escolher arquivos para enviar"
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
          aria-label="Arquivos enviados"
          className="divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface text-sm"
        >
          {results.map((r, i) => (
            <li
              key={`${r.filename}-${i}`}
              className="flex items-start justify-between gap-3 px-4 py-3"
            >
              <span className="break-all">{r.filename}</span>
              <span
                className={`inline-flex shrink-0 items-center gap-1 ${r.accepted ? "text-fg-2" : "text-danger"}`}
              >
                {!r.accepted ? (
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
    </div>
  );
}
