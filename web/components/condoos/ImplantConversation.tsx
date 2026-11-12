"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

type Lookup = {
  cnpj: string;
  already?: boolean;
  available?: boolean;
  found?: boolean;
  name?: string;
  status?: string;
  address?: string;
  is_condominium?: boolean | null;
};

const field =
  "h-11 w-full rounded-[var(--radius-control)] border border-control bg-transparent px-3 text-[15px]";

export function Bubble({ children, me = false }: { children: React.ReactNode; me?: boolean }) {
  return (
    <p
      className={
        me
          ? "max-w-[92%] justify-self-end rounded-[14px_14px_4px_14px] bg-elevated px-3.5 py-3 text-sm"
          : "max-w-[92%] rounded-[14px_14px_14px_4px] bg-surface px-3.5 py-3 text-sm leading-relaxed"
      }
    >
      {children}
    </p>
  );
}

export function Progress({
  step,
  total,
  label = "Implantar",
}: {
  step: number;
  total: number;
  label?: string;
}) {
  return (
    <div className="grid gap-1.5" aria-label={`Passo ${step} de ${total}`}>
      <span className="text-[12px] text-fg-2">
        {label} · passo {step} de {total}
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-elevated">
        <span
          className="block h-full rounded-full bg-success"
          style={{ width: `${(step / total) * 100}%` }}
        />
      </span>
    </div>
  );
}

/** Implanting a condominium as a conversation (D127, D128): one question per screen, the
 * CondoOS speaks first, every answer is saved, "Continuar depois" always works. */
export function ImplantConversation({ userName }: { userName: string }) {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cnpj, setCnpj] = useState("");
  const [found, setFound] = useState<Lookup | null>(null);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [units, setUnits] = useState("");
  const [id, setId] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const first = userName.split(" ")[0];

  async function lookup(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const r = await send<Lookup>("GET", `/implantation/cnpj/${cnpj.replace(/\D/g, "")}`);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    if (r.data.already) return setError("Este CNPJ já está no CondoOS. Fale com a equipe CondoOS.");
    setFound(r.data);
    setName(r.data.name ?? "");
    setAddress(r.data.address ?? "");
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const r = await send<{ id: string }>("POST", "/implantation", {
      cnpj: cnpj.replace(/\D/g, ""),
      name,
      address,
      units: Number(units),
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setId(r.data.id);
    setStep(3);
  }

  async function mandate(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setBusy(true);
    setError(null);
    const r = await send("PUT", `/condominiums/${id}/implantation/mandate`, {
      term_start: start,
      term_end: end || null,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setStep(4);
  }

  async function term(file: File | undefined) {
    if (!file || !id) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("files", file);
    const res = await fetch(`/api/condominiums/${id}/documents`, { method: "POST", body: form });
    const body = (await res.json().catch(() => null)) as
      { document_id?: string; error?: string }[] | null;
    const docId = body?.[0]?.document_id;
    if (!res.ok || !docId) {
      setBusy(false);
      return setError(body?.[0]?.error ?? "Não foi possível enviar o termo.");
    }
    const r = await send("POST", `/condominiums/${id}/implantation/term`, { document_id: docId });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.push(`/implantacao/${id}`);
  }

  const later = id ? (
    <Button variant="ghost" onClick={() => router.push(`/implantacao/${id}`)}>
      Continuar depois
    </Button>
  ) : null;

  return (
    <div className="grid gap-3" data-testid="implant-conversation">
      <Progress step={step} total={4} />
      {step === 1 && (
        <form onSubmit={lookup} className="grid gap-3">
          <Bubble>
            Vamos começar, {first}. Qual é o CNPJ do condomínio? Eu busco o nome e o endereço na
            Receita para você não digitar.
          </Bubble>
          <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="cnpj">
            CNPJ do condomínio
            <input
              id="cnpj"
              className={field}
              inputMode="numeric"
              value={cnpj}
              onChange={(e) => setCnpj(e.target.value)}
              required
            />
          </label>
          {!found && (
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? "Buscando…" : "Buscar na Receita"}
            </Button>
          )}
          {found && (
            <>
              <Bubble>
                {found.found ? (
                  <>
                    Encontrei: <b>{found.name}</b>
                    {found.address ? `, ${found.address}` : ""}. Situação na Receita:{" "}
                    {found.status?.toLowerCase() ?? "não informada"}.
                    {found.is_condominium === false &&
                      " Atenção: a Receita não registra este CNPJ como condomínio."}{" "}
                    É este?
                  </>
                ) : found.available === false ? (
                  "A Receita não respondeu agora. Pode seguir digitando o nome e o endereço."
                ) : (
                  "Não encontrei este CNPJ na Receita. Confira os números ou digite os dados."
                )}
              </Bubble>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  className="flex-1"
                  onClick={() => {
                    setFound(null);
                    setCnpj("");
                  }}
                >
                  Não é este
                </Button>
                <Button variant="primary" className="flex-1" onClick={() => setStep(2)}>
                  Sim, seguir
                </Button>
              </div>
            </>
          )}
        </form>
      )}
      {step === 2 && (
        <form onSubmit={create} className="grid gap-3">
          <Bubble>Confira o nome e o endereço. E quantas unidades tem o condomínio?</Bubble>
          <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="name">
            Nome
            <input
              id="name"
              className={field}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={3}
            />
          </label>
          <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="address">
            Endereço
            <input
              id="address"
              className={field}
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
              minLength={5}
            />
          </label>
          <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="units">
            Unidades
            <input
              id="units"
              className={field}
              inputMode="numeric"
              value={units}
              onChange={(e) => setUnits(e.target.value.replace(/\D/g, ""))}
              required
            />
          </label>
          <Button type="submit" variant="primary" disabled={busy || !units}>
            {busy ? "Salvando…" : "Salvar e seguir"}
          </Button>
        </form>
      )}
      {step === 3 && (
        <form onSubmit={mandate} className="grid gap-3">
          <Bubble>
            Pronto, o condomínio está salvo e já aparece em &ldquo;Continuar uma implantação&rdquo;.
            Desde quando você é síndica ou síndico, e até quando vai o mandato?
          </Bubble>
          <div className="grid grid-cols-2 gap-2">
            <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="start">
              Início
              <input
                id="start"
                type="date"
                className={field}
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </label>
            <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="end">
              Fim
              <input
                id="end"
                type="date"
                className={field}
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
          </div>
          <Button type="submit" variant="primary" disabled={busy}>
            Seguir
          </Button>
          {later}
        </form>
      )}
      {step === 4 && (
        <div className="grid gap-3">
          <Bubble>
            Último passo: para eu ler os documentos do condomínio, preciso do termo de adesão
            assinado pelo condomínio. Ele diz o que o CondoOS faz com os dados e por quanto tempo
            guarda. Se ainda não tiver, continue depois: eu lembro na lista.
          </Bubble>
          <label className="inline-flex cursor-pointer justify-center">
            <input
              type="file"
              accept=".pdf,image/*"
              className="sr-only"
              aria-label="Enviar o termo assinado"
              disabled={busy}
              onChange={(e) => void term(e.target.files?.[0])}
            />
            <span className="inline-flex h-11 w-full items-center justify-center rounded-[var(--radius-button)] bg-accent px-4 font-semibold text-accent-fg">
              {busy ? "Enviando…" : "Enviar o termo assinado"}
            </span>
          </label>
          {later}
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
