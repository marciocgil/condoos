"use client";

import { BellOff, BellRing, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { ComplianceList } from "@/lib/types";

/** The weekly compliance e-mail (D109): off until the síndico turns it on; only to the
 * condominium's síndico, only when something expired or expires within 30 days. */
export function ComplianceReminderCard({
  condominiumId,
  reminders,
}: {
  condominiumId: string;
  reminders: ComplianceList["reminders"];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    const r = await send("PUT", `/condominiums/${condominiumId}/compliance/reminders`, {
      enabled: !reminders.enabled,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.refresh();
  }

  return (
    <Card aria-label="Resumo semanal por e-mail">
      <CardTitle
        action={
          reminders.enabled ? (
            <Badge tone="success" icon={<BellRing size={12} />}>
              Ligado
            </Badge>
          ) : (
            <Badge tone="neutral" icon={<BellOff size={12} />}>
              Desligado
            </Badge>
          )
        }
      >
        Resumo semanal por e-mail
      </CardTitle>
      <p className="text-[13px] text-fg-2">
        Às segundas-feiras, a partir das 8h, o síndico recebe no próprio e-mail a lista do que
        venceu ou vence nos próximos 30 dias: só o nome da obrigação e a data, com o link para o
        CondoOS. Sem nada para avisar, nenhum e-mail sai. Pode ser pausado em Ajustes.
      </p>
      {reminders.last_sent_at && (
        <p className="mt-1 text-[13px] text-fg-2">
          Último envio aceito pelo servidor: {formatDateTime(reminders.last_sent_at)}
        </p>
      )}
      {reminders.can_change ? (
        <div className="mt-3">
          <Button
            size="sm"
            variant={reminders.enabled ? "secondary" : "primary"}
            disabled={busy}
            onClick={toggle}
            icon={<Mail size={14} aria-hidden />}
          >
            {reminders.enabled ? "Desligar o resumo" : "Ligar o resumo semanal"}
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-[13px] text-muted">Só o síndico liga ou desliga.</p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
