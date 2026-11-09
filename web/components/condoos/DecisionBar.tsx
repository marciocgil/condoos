"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, buttonClass, type ButtonVariant } from "@/components/ui/Button";
import { textareaClass } from "@/components/ui/Field";
import { ACTION_LABEL } from "@/lib/labels";

// Actions that require a comment (spec §7).
const NEEDS_COMMENT = new Set(["contestar", "descartar", "solicitar_evidencia"]);
const ORDER = [
  "validar",
  "confirmar",
  "contestar",
  "ignorar",
  "solicitar_evidencia",
  "descartar",
  "reabrir",
];
const COMMENT_LABEL: Record<string, string> = {
  contestar: "Por que você contesta este achado?",
  descartar: "Motivo do descarte",
  solicitar_evidencia: "Que evidência falta para decidir?",
};
// What each of the síndico's decisions does, said before the click (LB-086, D108). Follows
// ``findings/decisions.py`` and the risk rule: ignored findings leave the amount at risk.
const EFFECT: Record<string, string> = {
  confirmar:
    "Confirmar: você concorda que é um ponto a tratar. Ele segue no valor em risco e no relatório.",
  contestar:
    "Contestar: você discorda e diz por quê. O motivo fica na trilha e o ponto segue no relatório como contestado.",
  ignorar: "Ignorar: o ponto sai do valor em risco. A decisão fica registrada e pode ser revista.",
};
const VARIANT: Record<string, ButtonVariant> = {
  validar: "primary",
  confirmar: "primary",
  descartar: "danger",
};

/** Decision buttons for a finding. Only the actions the API allows are shown. */
export function DecisionBar({
  condominiumId,
  findingId,
  actions,
  nextHref,
  homeHref,
}: {
  condominiumId: string;
  findingId: string;
  actions: string[];
  /** The síndico's next point waiting for a decision, if any, and the way back to Hoje. */
  nextHref?: string | null;
  homeHref?: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (actions.length === 0 && !done) return null;

  async function send(action: string, text?: string) {
    setBusy(true);
    setError(null);
    const res = await fetch(`/api/condominiums/${condominiumId}/findings/${findingId}/decisions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action, comment: text ?? null }),
    });
    setBusy(false);
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      setError(body?.detail ?? "Não foi possível registrar a decisão.");
      return;
    }
    setPending(null);
    setComment("");
    setDone(`Decisão registrada: ${ACTION_LABEL[action]?.button ?? action}.`);
    router.refresh();
  }

  const sorted = [...actions].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
  const effects = sorted.filter((a) => EFFECT[a]);
  return (
    <div className="space-y-3">
      {effects.length > 0 && !done && (
        <ul className="space-y-1 text-[13px] text-fg-2" data-testid="decision-effects">
          {effects.map((a) => (
            <li key={a}>{EFFECT[a]}</li>
          ))}
        </ul>
      )}
      <div
        className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap"
        role="group"
        aria-label="Decisão sobre o achado"
      >
        {sorted.map((action) => (
          <Button
            key={action}
            // After a decision the next point is the primary action (one lime button).
            variant={done ? "secondary" : (VARIANT[action] ?? "secondary")}
            disabled={busy}
            aria-expanded={NEEDS_COMMENT.has(action) ? pending === action : undefined}
            onClick={() =>
              NEEDS_COMMENT.has(action)
                ? setPending(pending === action ? null : action)
                : send(action)
            }
          >
            {ACTION_LABEL[action]?.button ?? action}
          </Button>
        ))}
      </div>
      {pending && (
        <div className="space-y-2 rounded-[var(--radius-card)] border border-line bg-bg-2 p-4">
          <label htmlFor="decision-comment" className="text-[13px] font-medium">
            {COMMENT_LABEL[pending] ?? "Motivo"}
          </label>
          <textarea
            id="decision-comment"
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className={textareaClass}
            placeholder="Escreva o motivo (obrigatório)"
          />
          <div className="flex gap-2">
            <Button
              variant="primary"
              disabled={busy || comment.trim().length < 5}
              onClick={() => send(pending, comment)}
            >
              Enviar {ACTION_LABEL[pending]?.button.toLowerCase()}
            </Button>
            <Button variant="ghost" onClick={() => setPending(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {done && !error && (
        <div className="space-y-2">
          <p role="status" className="text-sm text-success">
            {done}
          </p>
          {homeHref && (
            <div className="flex flex-wrap gap-2">
              {nextHref ? (
                <Link href={nextHref} className={buttonClass("primary", "sm")}>
                  Próximo ponto de atenção
                </Link>
              ) : (
                <p className="text-sm">Tudo decidido por enquanto.</p>
              )}
              <Link href={homeHref} className={buttonClass("secondary", "sm")}>
                Voltar ao Hoje
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
