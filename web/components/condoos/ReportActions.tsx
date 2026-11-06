"use client";

import { Download, Lock } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { buttonClass } from "@/components/ui/Button";

/** Monthly report for the management company: download, and close the month (which
 * publishes the report). The API refuses to close while the exception queue has items.
 * Render only when the month's competence exists; "Fechar mês" only when `canClose`. */
export function ReportActions({
  condominiumId,
  month,
  sent,
  canClose,
}: {
  condominiumId: string;
  month: string; // YYYY-MM
  sent: boolean;
  canClose: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function close() {
    if (
      !window.confirm(
        `Fechar a competência ${month.slice(5)}/${month.slice(0, 4)} e publicar o relatório?`,
      )
    )
      return;
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/condominiums/${condominiumId}/competences/${month}/close`, {
      method: "POST",
    });
    setBusy(false);
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      setMessage(body?.detail ?? "Não foi possível fechar a competência.");
      return;
    }
    router.refresh();
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex flex-wrap gap-2">
        <a
          href={`/api/condominiums/${condominiumId}/reports/${month}.pdf`}
          className={buttonClass("ghost", "sm")}
          title={sent ? "Relatório publicado" : "Prévia: a competência ainda está aberta"}
        >
          <Download size={14} aria-hidden /> {sent ? "PDF" : "Prévia"}
        </a>
        {!sent && canClose && (
          <button
            type="button"
            onClick={() => void close()}
            disabled={busy}
            className={buttonClass("secondary", "sm")}
          >
            <Lock size={14} aria-hidden /> {busy ? "Fechando…" : "Fechar mês"}
          </button>
        )}
      </div>
      {message && (
        <p role="alert" className="max-w-xs text-xs text-warning">
          {message}
        </p>
      )}
    </div>
  );
}
