"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Bubble, Progress } from "@/components/condoos/ImplantConversation";
import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";
import type { ExitInfo } from "@/lib/exit";
import { formatDate } from "@/lib/format";

const field =
  "h-11 w-full rounded-[var(--radius-control)] border border-control bg-transparent px-3 text-[15px]";
const option =
  "transition-ui w-full rounded-[var(--radius-control)] border px-3.5 py-3 text-left text-[15px]";

function Dossier({ id }: { id: string }) {
  return (
    <a
      href={`/api/condominiums/${id}/exit/dossier.pdf`}
      className="inline-flex items-center gap-2 text-sm font-medium underline-offset-2 hover:underline"
      data-testid="exit-dossier"
    >
      <Download size={16} aria-hidden /> Baixar o dossiê do meu período
    </a>
  );
}

/** Leaving a condominium as a short conversation (D127 decision 4, D129): why, when, what
 * happens before confirming. Nothing is deleted; a later date can be undone. */
export function ExitConversation({ info }: { info: ExitInfo }) {
  const [step, setStep] = useState(1);
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [when, setWhen] = useState<"hoje" | "mandato" | "outra">(
    info.mandate_end ? "mandato" : "hoje",
  );
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ applied: boolean; on: string } | null>(null);
  const id = info.condominium.id;
  const on =
    when === "hoje" ? info.today : when === "mandato" ? (info.mandate_end ?? info.today) : other;
  const today = on === info.today;

  async function confirm() {
    setBusy(true);
    setError(null);
    const r = await send<{ applied: boolean }>("POST", `/condominiums/${id}/exit`, {
      reason,
      note,
      on,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setDone({ applied: r.data.applied, on });
    setStep(3);
  }

  return (
    <div className="grid gap-3" data-testid="exit-conversation">
      <Progress step={step} total={3} label="Encerrar" />
      {step === 1 && (
        <>
          <Bubble>
            Você vai deixar de ser síndico do <b>{info.condominium.name}</b>. Por quê?
          </Bubble>
          <div className="grid gap-2" role="radiogroup" aria-label="Motivo">
            {info.reasons.map((r) => (
              <button
                key={r.key}
                type="button"
                role="radio"
                aria-checked={reason === r.key}
                onClick={() => setReason(r.key)}
                className={`${option} ${reason === r.key ? "border-accent bg-elevated" : "border-line"}`}
              >
                {r.label}
              </button>
            ))}
          </div>
          {reason === "outro" && (
            <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="note">
              Em poucas palavras
              <input
                id="note"
                className={field}
                value={note}
                maxLength={300}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          )}
          <Button
            variant="primary"
            disabled={!reason || (reason === "outro" && note.trim().length < 5)}
            onClick={() => setStep(2)}
          >
            Continuar
          </Button>
        </>
      )}
      {step === 2 && (
        <>
          <Bubble>Quando a sua saída vale?</Bubble>
          <div className="grid gap-2" role="radiogroup" aria-label="Quando">
            {info.mandate_end && (
              <button
                type="button"
                role="radio"
                aria-checked={when === "mandato"}
                onClick={() => setWhen("mandato")}
                className={`${option} ${when === "mandato" ? "border-accent bg-elevated" : "border-line"}`}
              >
                No fim do mandato, {formatDate(info.mandate_end)}
              </button>
            )}
            <button
              type="button"
              role="radio"
              aria-checked={when === "hoje"}
              onClick={() => setWhen("hoje")}
              className={`${option} ${when === "hoje" ? "border-accent bg-elevated" : "border-line"}`}
            >
              Hoje
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={when === "outra"}
              onClick={() => setWhen("outra")}
              className={`${option} ${when === "outra" ? "border-accent bg-elevated" : "border-line"}`}
            >
              Outra data
            </button>
            {when === "outra" && (
              <label className="grid gap-1 text-[13px] text-fg-2" htmlFor="on">
                Até 90 dias
                <input
                  id="on"
                  type="date"
                  className={field}
                  min={info.today}
                  max={info.max_date}
                  value={other}
                  onChange={(e) => setOther(e.target.value)}
                />
              </label>
            )}
          </div>
          {on && (
            <Bubble>
              Combinado. {today ? "A partir de agora" : `A partir de ${formatDate(on)}`}:
              <span className="mt-2 block">• seu acesso a este condomínio termina;</span>
              <span className="block">
                • os envios e lembretes automáticos param até o próximo síndico;
              </span>
              <span className="block">
                • nada é apagado: documentos e histórico ficam guardados por {info.retention_years}{" "}
                anos, à espera do próximo síndico.
              </span>
              {!today && (
                <span className="mt-2 block">Até lá tudo continua, e dá para desfazer.</span>
              )}
            </Bubble>
          )}
          <Dossier id={id} />
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <Button variant="ghost" className="flex-1" onClick={() => history.back()}>
              Desistir
            </Button>
            <Button
              variant="primary"
              className="flex-1"
              disabled={busy || !on}
              onClick={confirm}
              data-testid="exit-confirm"
            >
              {today
                ? "Encerrar hoje"
                : `Encerrar em ${!on ? "…" : on.slice(0, 4) === info.today.slice(0, 4) ? formatDate(on).slice(0, 5) : formatDate(on)}`}
            </Button>
          </div>
        </>
      )}
      {step === 3 && done && (
        <>
          <Bubble>
            {done.applied
              ? `Pronto. Seu acesso ao ${info.condominium.name} terminou e as automações estão pausadas. Nada foi apagado.`
              : `Saída marcada para ${formatDate(done.on)}. Até lá tudo continua como hoje; se mudar de ideia, é só desfazer.`}
          </Bubble>
          {/* Full load: the access changed, so the start screen must be read again. */}
          <Button variant="primary" onClick={() => window.location.assign("/")}>
            Voltar ao início
          </Button>
        </>
      )}
    </div>
  );
}

/** A later exit already marked: show it and allow undoing it. */
export function ExitPending({ info }: { info: ExitInfo }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const p = info.pending!;
  async function undo() {
    setBusy(true);
    const r = await send("POST", `/condominiums/${info.condominium.id}/exit/cancel`);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    window.location.assign(`/encerrar/${info.condominium.id}`);
  }
  return (
    <div
      className="grid gap-3 rounded-[var(--radius-card)] bg-surface p-4"
      data-testid="exit-pending"
    >
      <p className="text-[15px] font-semibold">Saída marcada para {formatDate(p.on)}</p>
      <p className="text-[13px] text-fg-2">
        {p.reason}. Até lá tudo continua; no dia seguinte seu acesso termina e as automações param.
        Nada é apagado.
      </p>
      <Dossier id={info.condominium.id} />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button variant="ghost" disabled={busy} onClick={undo}>
        Desfazer a saída
      </Button>
    </div>
  );
}
