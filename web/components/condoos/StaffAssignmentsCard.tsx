"use client";

import { CheckCircle2, CircleSlash, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import { ROLE_LABEL } from "@/lib/labels";
import type { StaffAssignment } from "@/lib/types";

const ROLES = ["condoos_reviewer", "condoos_admin"] as const;

/** CondoOS staff assigned to this condominium (D77, CB-018). Only a CondoOS admin assigned
 * here sees this card; the person must already hold the CondoOS role. */
export function StaffAssignmentsCard({
  condominiumId,
  assignments,
}: {
  condominiumId: string;
  assignments: StaffAssignment[];
}) {
  const router = useRouter();
  const base = `/condominiums/${condominiumId}/assignments`;
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    email: "",
    platform_role: "condoos_reviewer",
    reason: "",
    valid_until: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function add() {
    setBusy(true);
    setError(null);
    setOk(null);
    // A date means the end of that day in Brasília.
    const until = form.valid_until ? `${form.valid_until}T23:59:59-03:00` : null;
    const r = await send("POST", base, { ...form, valid_until: until });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOk(`Atribuição criada para ${form.email}.`);
    setOpen(false);
    setForm({ email: "", platform_role: "condoos_reviewer", reason: "", valid_until: "" });
    router.refresh();
  }

  async function remove(a: StaffAssignment) {
    if (!window.confirm(`Remover a atribuição de ${a.name} (${ROLE_LABEL[a.platform_role]})?`))
      return;
    setError(null);
    const r = await send<{ message: string }>("DELETE", `${base}/${a.id}`);
    if (!r.ok) return setError(r.error);
    setOk(r.data.message);
    router.refresh();
  }

  return (
    <Card>
      <CardTitle
        action={
          !open ? (
            <Button
              variant="ghost"
              size="sm"
              icon={<Plus size={14} />}
              onClick={() => setOpen(true)}
            >
              Atribuir
            </Button>
          ) : undefined
        }
      >
        Equipe CondoOS
      </CardTitle>
      {assignments.length === 0 ? (
        <p className="text-sm text-fg-2">Ninguém da equipe CondoOS atribuído.</p>
      ) : (
        <ul className="divide-y divide-line text-sm" aria-label="Equipe CondoOS atribuída">
          {assignments.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 py-2">
              <span className="min-w-0">
                <span className="block truncate">{a.name}</span>
                <span className="text-xs text-muted">
                  {ROLE_LABEL[a.platform_role] ?? a.platform_role} · {a.reason}
                  {a.valid_until && ` · até ${formatDateTime(a.valid_until)}`}
                </span>
                <span className="mt-1 block">
                  {a.active ? (
                    <Badge tone="success" icon={<CheckCircle2 size={12} />}>
                      Ativa
                    </Badge>
                  ) : (
                    <Badge tone="neutral" icon={<CircleSlash size={12} />}>
                      Encerrada
                    </Badge>
                  )}
                </span>
              </span>
              {a.active && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remover atribuição de ${a.name}`}
                  onClick={() => void remove(a)}
                >
                  <Trash2 size={14} aria-hidden />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {open && (
        <div className="mt-3 space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
          <Field
            id="s-email"
            label="E-mail"
            required
            hint="A pessoa precisa já ter o papel na equipe CondoOS."
          >
            <input
              id="s-email"
              type="email"
              className={controlClass}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field id="s-role" label="Papel" required>
            <select
              id="s-role"
              className={controlClass}
              value={form.platform_role}
              onChange={(e) => setForm({ ...form, platform_role: e.target.value })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </Field>
          <Field id="s-reason" label="Motivo" required>
            <input
              id="s-reason"
              className={controlClass}
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })}
            />
          </Field>
          <Field id="s-until" label="Até (opcional)" hint="Sem data, vale até ser removida.">
            <input
              id="s-until"
              type="date"
              className={controlClass}
              value={form.valid_until}
              onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
            />
          </Field>
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={busy || !form.email || form.reason.trim().length < 5}
              onClick={() => void add()}
            >
              Atribuir
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
      {ok && (
        <p role="status" className="mt-2 text-sm text-success">
          {ok}
        </p>
      )}
    </Card>
  );
}
