"use client";

import { CheckCircle2, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

/** The síndico approves the farol exactly as seen (its hash goes with the decision), or
 * returns it with a reason (D124). */
export function AuditPublicationDecision({
  condominiumId,
  publicationId,
  sha256,
}: {
  condominiumId: string;
  publicationId: string;
  sha256: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [returning, setReturning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function decide(approve: boolean) {
    setBusy(true);
    setMessage(null);
    const r = await send(
      "POST",
      `/condominiums/${condominiumId}/audit/publications/${publicationId}/decision`,
      { approve, sha256, reason: approve ? null : reason },
    );
    setBusy(false);
    if (!r.ok) {
      setMessage(r.error);
      return;
    }
    setMessage(approve ? "Farol aprovado." : "Farol devolvido à equipe CondoOS.");
    router.refresh();
  }

  return (
    <div className="space-y-2" data-testid="publication-decision">
      {returning ? (
        <>
          <label className="flex flex-col gap-1 text-sm">
            O que precisa mudar?
            <textarea
              className="min-h-20 rounded-[var(--radius-button)] border border-control bg-transparent p-2 text-sm"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={busy || reason.trim().length < 10}
              onClick={() => void decide(false)}
            >
              Devolver com este motivo
            </Button>
            <Button variant="ghost" onClick={() => setReturning(false)}>
              Cancelar
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            icon={<CheckCircle2 size={16} aria-hidden />}
            disabled={busy}
            onClick={() => void decide(true)}
          >
            Aprovar este farol
          </Button>
          <Button
            variant="secondary"
            icon={<Undo2 size={16} aria-hidden />}
            onClick={() => setReturning(true)}
          >
            Devolver
          </Button>
        </div>
      )}
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
