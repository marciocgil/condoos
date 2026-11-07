"use client";

import { CheckCircle2, Circle, Copy, UploadCloud, XCircle } from "lucide-react";
import { useEffect, useState, type ChangeEvent } from "react";

import { Logo } from "@/components/layout/Logo";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/format";
import type { PublicDelegation } from "@/lib/types";

const ACCEPT = ".pdf,.xml,.ofx,.csv,.ret,.txt,image/jpeg,image/png,image/webp";

interface Result {
  filename: string;
  duplicate: boolean;
  error: string | null;
}

/** The sender's page (D95): what was asked, until when, and the upload. Nothing of the
 * condominium is shown or downloadable here. */
export function PublicUpload({ token }: { token: string }) {
  const [info, setInfo] = useState<PublicDelegation | null>(null);
  const [missing, setMissing] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const path = `/api/public/delegations/${encodeURIComponent(token)}`;

  useEffect(() => {
    fetch(path)
      .then(async (r) => (r.ok ? setInfo((await r.json()) as PublicDelegation) : setMissing(true)))
      .catch(() => setMissing(true));
  }, [path]);

  async function upload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const r = await fetch(`${path}/files`, { method: "POST", body: form });
      if (r.status === 404) setMissing(true);
      else if (!r.ok) setError("Não foi possível enviar. Tente de novo.");
      else setResults([...(await r.json()), ...results]);
    } catch {
      setError("Sem conexão. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto min-h-dvh max-w-md space-y-5 px-4 pt-5 pb-16">
      <Logo />
      {missing ? (
        <Card>
          <h1 className="text-lg font-semibold">Link inválido ou fora do prazo</h1>
          <p className="mt-2 text-sm text-fg-2">Peça um novo link a quem enviou este.</p>
        </Card>
      ) : !info ? (
        <p className="text-sm text-fg-2">Carregando…</p>
      ) : (
        <>
          <div>
            <h1 className="text-xl font-semibold">Envio de documentos</h1>
            <p className="text-sm text-fg-2">
              Pedido do {info.condominium} para {info.recipient_name}, com prazo até{" "}
              {formatDate(info.due_date)}:
            </p>
          </div>
          <Card>
            <ul className="space-y-2 text-sm" aria-label="Documentos pedidos">
              {info.items.map((i) => (
                <li key={i.label} className="flex items-start gap-2">
                  {i.attended ? (
                    <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0 text-success" />
                  ) : (
                    <Circle size={16} aria-hidden className="mt-0.5 shrink-0 text-muted" />
                  )}
                  <span>
                    {i.label}
                    {i.attended && <span className="block text-[12px] text-fg-2">Recebido</span>}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          <label className="transition-ui flex cursor-pointer flex-col items-center justify-center rounded-[var(--radius-card)] border-2 border-dashed border-control bg-surface px-4 py-10 text-center hover:border-accent">
            <UploadCloud size={28} aria-hidden className="mb-2 text-fg-2" />
            <span className="font-medium">{busy ? "Enviando…" : "Escolher arquivos"}</span>
            <span className="mt-1 text-[13px] text-fg-2">
              PDF, foto (JPG, PNG) ou XML · até {info.remaining_files} arquivo(s)
            </span>
            <input
              type="file"
              multiple
              accept={ACCEPT}
              className="sr-only"
              aria-label="Escolher arquivos para enviar"
              disabled={busy}
              onChange={(e: ChangeEvent<HTMLInputElement>) => void upload(e.target.files)}
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
                        {r.error}
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
                    {r.error ? "Recusado" : r.duplicate ? "Já recebido antes" : "Recebido"}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[12px] text-muted">
            Este link serve só para enviar arquivos e vale até {formatDate(info.expires_at)}. Não é
            preciso criar conta.
          </p>
        </>
      )}
    </div>
  );
}
