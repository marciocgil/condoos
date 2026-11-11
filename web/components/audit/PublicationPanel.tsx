"use client";

import { History, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Publication } from "@/lib/audit";
import { PUBLICATION_LABEL } from "@/lib/audit";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";

/** Sending the month's farol to the síndico (D124) and revalidating past months. */
export function PublicationPanel({
  condominiumId,
  competencia,
  latest,
  canSubmit,
  canRun,
  waitingReview,
}: {
  condominiumId: string;
  competencia: string;
  latest: Publication | null;
  canSubmit: boolean;
  canRun: boolean;
  waitingReview: number;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setMessage(null);
    const r = await send("POST", `/condominiums/${condominiumId}/audit/publications`, {
      competencia,
    });
    setBusy(false);
    setMessage(r.ok ? "Enviado ao síndico." : r.error);
    if (r.ok) router.refresh();
  }

  async function revalidate() {
    setBusy(true);
    setMessage(null);
    const r = await send<{ meses: { competencia: string; mudancas: string[] }[] }>(
      "POST",
      `/condominiums/${condominiumId}/audit/revalidate`,
      { months: 6, until: competencia },
    );
    setBusy(false);
    if (!r.ok) {
      setMessage(r.error);
      return;
    }
    const changed = r.data.meses.filter((m) => m.mudancas.length > 0);
    setMessage(
      changed.length === 0
        ? "Seis meses revalidados: nenhum status mudou."
        : `Seis meses revalidados. Mudou: ${changed
            .map((m) => `${m.competencia} (${m.mudancas.join("; ")})`)
            .join(" · ")}`,
    );
    router.refresh();
  }

  return (
    <div className="space-y-2" data-testid="publication-panel">
      <p className="text-sm">
        {latest ? (
          <>
            <strong>{PUBLICATION_LABEL[latest.status]}</strong> · enviado em{" "}
            {formatDateTime(latest.submitted_at)}
            {latest.submitted_by ? ` por ${latest.submitted_by}` : ""}
            {latest.decided_at
              ? ` · decidido em ${formatDateTime(latest.decided_at)}${latest.decided_by ? ` por ${latest.decided_by}` : ""}`
              : ""}
            {latest.reason ? ` · ${latest.reason}` : ""}
            {latest.changed_since ? " · o farol mudou depois da aprovação (revalidação)" : ""}
          </>
        ) : (
          "Ainda não enviado ao síndico."
        )}
      </p>
      <p className="text-xs text-fg-2">
        O síndico aprova a versão que viu; se um resultado mudar depois do envio, o envio é
        substituído e precisa ser refeito. A aprovação libera a leitura do farol pelo corpo
        diretivo; não é aprovação das contas (isso é o DOC-03).
      </p>
      <div className="flex flex-wrap gap-2">
        {canSubmit && (
          <Button
            variant="primary"
            icon={<Send size={14} aria-hidden />}
            disabled={busy || waitingReview > 0}
            onClick={() => void submit()}
          >
            {waitingReview > 0
              ? `Revise ${waitingReview} controle(s) antes de enviar`
              : "Enviar ao síndico"}
          </Button>
        )}
        {canRun && (
          <Button
            icon={<History size={14} aria-hidden />}
            disabled={busy}
            onClick={() => void revalidate()}
          >
            Revalidar os últimos 6 meses
          </Button>
        )}
      </div>
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
