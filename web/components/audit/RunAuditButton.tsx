"use client";

import { Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

/** Runs the audit of the month (A0). Results whose inputs did not change are kept. */
export function RunAuditButton({
  condominiumId,
  competencia,
}: {
  condominiumId: string;
  competencia: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setMessage(null);
    const r = await send<{
      number: number;
      summary: { novos_resultados: number; reutilizados: number };
    }>("POST", `/condominiums/${condominiumId}/audit/runs`, { competencia });
    setBusy(false);
    if (!r.ok) {
      setMessage(r.error);
      return;
    }
    setMessage(
      `Execução ${r.data.number}: ${r.data.summary.novos_resultados} resultado(s) novo(s), ${r.data.summary.reutilizados} sem mudança.`,
    );
    router.refresh();
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="primary"
        icon={<Play size={16} aria-hidden />}
        disabled={busy}
        onClick={() => void run()}
      >
        {busy ? "Auditando…" : "Rodar auditoria do mês"}
      </Button>
      {message && (
        <p role="status" className="text-xs text-fg-2">
          {message}
        </p>
      )}
    </div>
  );
}
