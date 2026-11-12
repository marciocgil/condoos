"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

const field =
  "h-10 w-full rounded-[var(--radius-control)] border border-control bg-transparent px-3 text-sm";

/** The three items answered in place (D128): the mandate, the adhesion term and the approval
 * limit. Documents go through the usual upload. */
export function ImplantationAction({
  condominiumId,
  action,
}: {
  condominiumId: string;
  action: "mandato" | "termo" | "alcada";
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
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
