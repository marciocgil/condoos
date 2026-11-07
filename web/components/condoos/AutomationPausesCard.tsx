"use client";

import { PauseCircle, PlayCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { AutomationPauses } from "@/lib/types";

/** Kill switch (FR-007; D83): pause automations in this condominium until resumed. */
export function AutomationPausesCard({
  condominiumId,
  pauses,
}: {
  condominiumId: string;
  pauses: AutomationPauses;
}) {
  const router = useRouter();
  const base = `/condominiums/${condominiumId}/automation-pauses`;
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ automation_type: "*", reason: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(path: string, body?: unknown) {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}${path}`, body);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOpen(false);
    setForm({ automation_type: "*", reason: "" });
    router.refresh();
  }

  return (
    <Card>
      <CardTitle>Pausar automações</CardTitle>
      {pauses.active.length === 0 ? (
        <p className="text-sm text-fg-2">
          <Badge tone="success" icon={<PlayCircle size={12} />}>
            Automações ativas
          </Badge>
        </p>
      ) : (
        <ul className="space-y-2">
          {pauses.active.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>
                <Badge tone="warning" icon={<PauseCircle size={12} />}>
                  Pausado: {p.label}
                </Badge>
                <span className="mt-1 block text-xs text-muted">
                  {p.reason} · {p.paused_by}, {formatDateTime(p.paused_at)}
                </span>
              </span>
              {pauses.can_pause && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void call(`/${p.id}/resume`)}
                >
                  Retomar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted">
        Enquanto pausado, nenhum pedido novo é aceito e o que já foi aprovado espera na fila.
      </p>
      {pauses.can_pause && !open && (
        <Button className="mt-3" size="sm" variant="secondary" onClick={() => setOpen(true)}>
          <PauseCircle size={14} aria-hidden /> Pausar
        </Button>
      )}
      {open && (
        <div className="mt-3 space-y-3 border-t border-line pt-3">
          <Field id="pause-type" label="O que pausar">
            <select
              id="pause-type"
              className={controlClass}
              value={form.automation_type}
              onChange={(e) => setForm({ ...form, automation_type: e.target.value })}
            >
              {pauses.types.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="pause-reason" label="Motivo" required>
            <input
              id="pause-reason"
              className={controlClass}
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })}
            />
          </Field>
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={busy || form.reason.trim().length < 5}
              onClick={() => void call("", form)}
            >
              Confirmar pausa
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
