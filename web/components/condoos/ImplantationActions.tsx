"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, buttonClass } from "@/components/ui/Button";
import { send } from "@/lib/client";

const field =
  "h-10 w-full rounded-[var(--radius-control)] border border-control bg-transparent px-3 text-sm";

// What each document item asks for and how the file is sent (D130). ``tipo`` tells the
// reading what the file is when it cannot tell by itself (ata and convention only).
const UPLOADS: Record<string, { hint: string; accept: string; label: string; tipo?: string }> = {
  ata: {
    hint: "A ata da assembleia que elegeu você, em PDF ou foto.",
    accept: ".pdf,image/*",
    label: "Enviar a ata da eleição",
    tipo: "ata",
  },
  convencao: {
    hint: "A convenção registrada, em PDF ou foto.",
    accept: ".pdf,image/*",
    label: "Enviar a convenção",
    tipo: "convencao",
  },
  extrato: {
    hint: "O extrato do último mês de cada conta, no formato OFX (ou CSV), baixado no site do banco. Extrato em PDF não é importado.",
    accept: ".ofx,.csv,.txt",
    label: "Enviar extratos",
  },
  contratos: {
    hint: "Os contratos de portaria, limpeza, elevadores e outros serviços contínuos.",
    accept: ".pdf,image/*",
    label: "Enviar contratos",
  },
  contas: {
    hint: "Notas fiscais, boletos e comprovantes do último mês. Pode mandar tudo junto.",
    accept: ".pdf,.xml,image/*",
    label: "Enviar as contas",
  },
};

/** Each implantation item answered where it is (D128, D130): the mandate, the adhesion term
 * and the approval limit by form; documents by an upload that says what to send. */
export function ImplantationAction({
  condominiumId,
  action,
}: {
  condominiumId: string;
  action: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const base = `/condominiums/${condominiumId}/implantation`;

  async function done(r: { ok: boolean; error?: string }) {
    setBusy(false);
    if (!r.ok) return setError(r.error ?? "Não foi possível salvar.");
    router.refresh();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    if (action === "mandato")
      return done(await send("PUT", `${base}/mandate`, { term_start: a, term_end: b || null }));
    return done(await send("PUT", `${base}/limit`, { value: a, source: b }));
  }

  async function term(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("files", file);
    const res = await fetch(`/api/condominiums/${condominiumId}/documents`, {
      method: "POST",
      body: form,
    });
    const body = (await res.json().catch(() => null)) as { document_id?: string }[] | null;
    const docId = body?.[0]?.document_id;
    if (!res.ok || !docId) return done({ ok: false, error: "Não foi possível enviar o termo." });
    return done(await send("POST", `${base}/term`, { document_id: docId }));
  }

  async function upload(files: FileList | null, tipo?: string) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    setSent(null);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    const query = tipo ? `?tipo=${tipo}` : "";
    const res = await fetch(`/api/condominiums/${condominiumId}/documents${query}`, {
      method: "POST",
      body: form,
    });
    const body = (await res.json().catch(() => null)) as { error?: string | null }[] | null;
    setBusy(false);
    const failed = (body ?? []).filter((r) => r.error).map((r) => r.error);
    if (!res.ok || !body) return setError("Não foi possível enviar. Tente de novo.");
    if (failed.length) setError(failed.join(" "));
    const ok = body.length - failed.length;
    if (ok > 0) {
      setSent(
        `${ok} arquivo(s) recebido(s). Eu leio em alguns minutos; o item fica verde quando eu reconhecer o documento.`,
      );
      router.refresh();
    }
  }

  const up = UPLOADS[action];
  if (up)
    return (
      <div className="grid gap-1.5" data-testid={`implant-upload-${action}`}>
        <p className="text-[12.5px] text-fg-2">{up.hint}</p>
        <label className="inline-flex cursor-pointer">
          <input
            type="file"
            multiple
            accept={up.accept}
            className="sr-only"
            aria-label={up.label}
            disabled={busy}
            onChange={(e) => void upload(e.target.files, up.tipo)}
          />
          <span className="inline-flex h-10 w-full items-center justify-center rounded-[var(--radius-button)] bg-accent px-4 text-sm font-semibold text-accent-fg">
            {busy ? "Enviando…" : up.label}
          </span>
        </label>
        {sent && (
          <p role="status" className="text-[12.5px] text-success">
            {sent}
          </p>
        )}
        {error && <p className="text-[13px] text-danger">{error}</p>}
      </div>
    );
  if (action === "dados")
    return (
      <Link href={`/condominio/${condominiumId}/ajustes`} className={buttonClass("secondary")}>
        Ajustar em Configurações
      </Link>
    );
  if (action === "termo")
    return (
      <div className="grid gap-1">
        <label className="inline-flex cursor-pointer">
          <input
            type="file"
            accept=".pdf,image/*"
            className="sr-only"
            aria-label="Enviar o termo assinado"
            disabled={busy}
            onChange={(e) => void term(e.target.files?.[0])}
          />
          <span className="inline-flex h-10 w-full items-center justify-center rounded-[var(--radius-button)] bg-accent px-4 text-sm font-semibold text-accent-fg">
            {busy ? "Enviando…" : "Enviar o termo assinado"}
          </span>
        </label>
        {error && <p className="text-[13px] text-danger">{error}</p>}
      </div>
    );
  return (
    <form onSubmit={submit} className="grid gap-2">
      {action === "mandato" ? (
        <div className="grid grid-cols-2 gap-2">
          <label className="grid gap-1 text-[12px] text-fg-2">
            Início do mandato
            <input
              type="date"
              className={field}
              value={a}
              onChange={(e) => setA(e.target.value)}
              required
            />
          </label>
          <label className="grid gap-1 text-[12px] text-fg-2">
            Fim
            <input type="date" className={field} value={b} onChange={(e) => setB(e.target.value)} />
          </label>
        </div>
      ) : (
        <>
          <label className="grid gap-1 text-[12px] text-fg-2">
            Até quanto o síndico aprova sozinho (R$)
            <input
              className={field}
              inputMode="decimal"
              value={a}
              onChange={(e) => setA(e.target.value)}
              required
            />
          </label>
          <label className="grid gap-1 text-[12px] text-fg-2">
            Onde isso está escrito (convenção, artigo ou ata)
            <input
              className={field}
              value={b}
              onChange={(e) => setB(e.target.value)}
              required
              minLength={10}
            />
          </label>
        </>
      )}
      <Button type="submit" variant="primary" disabled={busy}>
        Salvar
      </Button>
      {error && <p className="text-[13px] text-danger">{error}</p>}
    </form>
  );
}
