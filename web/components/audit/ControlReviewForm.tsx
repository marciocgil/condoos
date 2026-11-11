"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, controlClass, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { ControlStatusCode } from "@/lib/types";

const OPTIONS: [ControlStatusCode, string][] = [
  ["VALIDADO", "Validado"],
  ["COM_RESSALVA", "Com ressalva"],
  ["PENDENTE", "Pendente"],
  ["DIVERGENTE", "Divergente"],
  ["NAO_AVALIADO", "Não avaliado"],
  ["NAO_APLICAVEL", "Não aplicável"],
];

/** Internal human review of a result: confirm, or reclassify with a reason (a new result
 * supersedes the old one; nothing is edited in place). */
export function ControlReviewForm({
  condominiumId,
  resultId,
  current,
}: {
  condominiumId: string;
  resultId: string;
  current: ControlStatusCode;
}) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState<ControlStatusCode>(current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(decision: "confirmar" | "reclassificar") {
    setBusy(true);
    setError(null);
    const r = await send(
      "POST",
      `/condominiums/${condominiumId}/audit/results/${resultId}/review`,
      {
        decision,
        status: decision === "reclassificar" ? status : null,
        reason,
      },
    );
    setBusy(false);
    if (!r.ok) setError(r.error);
    else {
      setReason("");
      router.refresh();
    }
  }

  return (
    <div className="space-y-3" data-testid="control-review">
      <Field
        id="review-reason"
        label="Motivo da revisão"
        required
        hint="Fica na trilha: quem revisou, quando e por quê."
      >
        <textarea
          id="review-reason"
          className={textareaClass}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
      <div className="flex flex-wrap items-end gap-2">
        <Button
          variant="primary"
          disabled={busy || reason.trim().length < 10}
          onClick={() => void act("confirmar")}
        >
          Confirmar resultado
        </Button>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-fg-2">ou reclassificar para</span>
          <select
            className={controlClass}
            value={status}
            onChange={(e) => setStatus(e.target.value as ControlStatusCode)}
          >
            {OPTIONS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <Button
          disabled={busy || reason.trim().length < 10 || status === current}
          onClick={() => void act("reclassificar")}
        >
          Reclassificar
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
