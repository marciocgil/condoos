"use client";

import { useState, type ChangeEvent } from "react";

import type { UploadResult } from "@/lib/types";

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
      if (!res.ok) {
        setError("Não foi possível enviar. Tente de novo.");
      } else {
        setResults((await res.json()) as UploadResult[]);
      }
    } catch {
      setError("Sem conexão. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <label
        className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-white px-4 py-10 text-center hover:border-brand-600"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void send(e.dataTransfer.files);
        }}
      >
        <span className="font-medium">
          {busy ? "Enviando…" : "Toque para escolher ou tire uma foto"}
        </span>
        <span className="mt-1 text-sm text-gray-500">
          Notas, boletos, recibos, contratos (PDF, foto ou XML) e extratos (OFX, CSV, CNAB)
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
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {results.length > 0 && (
        <ul
          className="divide-y divide-gray-100 rounded-xl bg-white text-sm shadow-sm"
          aria-label="Resultado do envio"
        >
          {results.map((r, i) => (
            <li
              key={`${r.filename}-${i}`}
              className="flex items-start justify-between gap-3 px-4 py-3"
            >
              <span className="break-all">{r.filename}</span>
              <span className={r.error ? "text-red-700" : "text-gray-600"}>
                {r.error ?? (r.duplicate ? "Já recebido antes" : "Recebido")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
