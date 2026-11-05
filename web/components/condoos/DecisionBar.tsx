"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, type ButtonVariant } from "@/components/ui/Button";
import { textareaClass } from "@/components/ui/Field";
import { ACTION_LABEL } from "@/lib/labels";

// Actions that require a comment (spec §7).
const NEEDS_COMMENT = new Set(["contestar", "descartar"]);
const ORDER = ["validar", "confirmar", "contestar", "ignorar", "descartar", "reabrir"];
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
}: {
  condominiumId: string;
  findingId: string;
  actions: string[];
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (actions.length === 0) return null;

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
  return (
    <div className="space-y-3">
      <div
        className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap"
        role="group"
        aria-label="Decisão sobre o achado"
      >
        {sorted.map((action) => (
          <Button
            key={action}
            variant={VARIANT[action] ?? "secondary"}
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
            {pending === "contestar" ? "Por que você contesta este achado?" : "Motivo do descarte"}
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
        <p role="status" className="text-sm text-success">
          {done}
        </p>
      )}
    </div>
  );
}
