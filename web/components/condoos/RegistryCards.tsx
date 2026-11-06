"use client";

import { Pencil, Plus, Trash2, UserCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDate } from "@/lib/format";
import { ROLE_LABEL } from "@/lib/labels";
import type { Settings } from "@/lib/types";

const POSITIONS = ["sindico", "subsindico", "conselheiro"] as const;

function Feedback({ error, ok }: { error: string | null; ok: string | null }) {
  if (error)
    return (
      <p role="alert" className="text-[13px] text-danger">
        {error}
      </p>
    );
  if (ok)
    return (
      <p role="status" className="text-[13px] text-success">
        {ok}
      </p>
    );
  return null;
}

/** Name, units, address and retention of the condominium. CNPJ is fixed (identifies it). */
export function ProfileCard({
  condominiumId,
  profile,
}: {
  condominiumId: string;
  profile: Settings["profile"];
}) {
  const router = useRouter();
  const [form, setForm] = useState({ ...profile });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    setOk(null);
    const r = await send("PUT", `/condominiums/${condominiumId}/profile`, {
      name: form.name,
      units: Number(form.units),
      address: form.address,
      retention_years: Number(form.retention_years),
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOk("Dados salvos.");
    router.refresh();
  }

  return (
    <Card>
      <CardTitle>Dados do condomínio</CardTitle>
      <div className="space-y-3">
        <Field id="p-name" label="Nome" required>
          <input
            id="p-name"
            className={controlClass}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field id="p-cnpj" label="CNPJ" hint="Identifica o condomínio e não muda.">
          <input id="p-cnpj" className={controlClass} value={form.cnpj} disabled />
        </Field>
        <Field id="p-address" label="Endereço" required>
          <input
            id="p-address"
            className={controlClass}
            value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field id="p-units" label="Unidades" required>
            <input
              id="p-units"
              type="number"
              min={1}
              className={controlClass}
              value={form.units}
              onChange={(e) => setForm({ ...form, units: Number(e.target.value) })}
            />
          </Field>
          <Field id="p-retention" label="Retenção (anos)" hint="Documentos fiscais; mínimo 5.">
            <input
              id="p-retention"
              type="number"
              min={5}
              max={30}
              className={controlClass}
              value={form.retention_years}
              onChange={(e) => setForm({ ...form, retention_years: Number(e.target.value) })}
            />
          </Field>
        </div>
        <Feedback error={error} ok={ok} />
        <Button variant="primary" onClick={() => void save()} disabled={busy}>
          {busy ? "Salvando…" : "Salvar dados"}
        </Button>
      </div>
    </Card>
  );
}

type BoardRow = Settings["board"][number];
const EMPTY_BOARD = { full_name: "", position: "conselheiro", term_start: "", term_end: "" };

/** Board members (used by rule R08). Editing re-evaluates the open months. */
export function BoardCard({
  condominiumId,
  board,
}: {
  condominiumId: string;
  board: Settings["board"];
}) {
  const router = useRouter();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [form, setForm] = useState(EMPTY_BOARD);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function start(row: BoardRow | null) {
    setError(null);
    setEditing(row?.id ?? "new");
    setForm(
      row
        ? {
            full_name: row.full_name,
            position: row.position,
            term_start: row.term_start ?? "",
            term_end: row.term_end ?? "",
          }
        : EMPTY_BOARD,
    );
  }

  async function save() {
    setBusy(true);
    setError(null);
    const body = { ...form, term_end: form.term_end || null };
    const r =
      editing === "new"
        ? await send("POST", `/condominiums/${condominiumId}/board`, body)
        : await send("PUT", `/condominiums/${condominiumId}/board/${editing}`, body);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setEditing(null);
    router.refresh();
  }

  async function remove(row: BoardRow) {
    if (!row.id || !window.confirm(`Remover ${row.full_name} do corpo diretivo?`)) return;
    const r = await send("DELETE", `/condominiums/${condominiumId}/board/${row.id}`);
    if (!r.ok) return setError(r.error);
    router.refresh();
  }

  return (
    <Card>
      <CardTitle
        action={
          editing === null ? (
            <Button variant="ghost" size="sm" icon={<Plus size={14} />} onClick={() => start(null)}>
              Adicionar
            </Button>
          ) : undefined
        }
      >
        Corpo diretivo
      </CardTitle>
      <p className="mb-2 text-xs text-muted">
        Usado na regra de conflito de interesse (R08): use o nome completo.
      </p>
      <ul className="divide-y divide-line text-sm">
        {board.map((b) => (
          <li key={b.id ?? b.full_name} className="flex items-center justify-between gap-2 py-2">
            <span className="min-w-0">
              <span className="block truncate">{b.full_name}</span>
              <span className="text-xs text-muted">
                {ROLE_LABEL[b.position] ?? b.position}
                {b.term_start && ` · desde ${formatDate(b.term_start)}`}
                {b.term_end && ` até ${formatDate(b.term_end)}`}
                {b.has_login && " · com acesso"}
              </span>
            </span>
            {b.id && (
              <span className="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Editar ${b.full_name}`}
                  onClick={() => start(b)}
                >
                  <Pencil size={14} aria-hidden />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remover ${b.full_name}`}
                  onClick={() => void remove(b)}
                >
                  <Trash2 size={14} aria-hidden />
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {editing !== null && (
        <div className="mt-3 space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
          <Field id="b-name" label="Nome completo" required>
            <input
              id="b-name"
              className={controlClass}
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </Field>
          <Field id="b-position" label="Cargo" required>
            <select
              id="b-position"
              className={controlClass}
              value={form.position}
              onChange={(e) => setForm({ ...form, position: e.target.value })}
            >
              {POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {ROLE_LABEL[p]}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="b-start" label="Início do mandato" required>
              <input
                id="b-start"
                type="date"
                className={controlClass}
                value={form.term_start}
                onChange={(e) => setForm({ ...form, term_start: e.target.value })}
              />
            </Field>
            <Field id="b-end" label="Fim do mandato">
              <input
                id="b-end"
                type="date"
                className={controlClass}
                value={form.term_end}
                onChange={(e) => setForm({ ...form, term_end: e.target.value })}
              />
            </Field>
          </div>
          <Feedback error={error} ok={null} />
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => void save()}
              disabled={busy || form.full_name.trim().length < 3 || !form.term_start}
            >
              {busy ? "Salvando…" : "Salvar"}
            </Button>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      {editing === null && <Feedback error={error} ok={null} />}
    </Card>
  );
}

/** Logins of the condominium (board roles). Company-wide accesses are listed, not removed. */
export function MembersCard({
  condominiumId,
  members,
}: {
  condominiumId: string;
  members: Settings["members"];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", role: "sindico" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function add() {
    setBusy(true);
    setError(null);
    setOk(null);
    const r = await send("POST", `/condominiums/${condominiumId}/members`, form);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setOk(
      `Acesso criado. ${form.name} entra com o e-mail ${form.email} (link de acesso, sem senha).`,
    );
    setOpen(false);
    setForm({ name: "", email: "", role: "sindico" });
    router.refresh();
  }

  async function remove(m: Settings["members"][number]) {
    if (
      !m.id ||
      !window.confirm(`Remover o acesso de ${m.name} (${ROLE_LABEL[m.role] ?? m.role})?`)
    )
      return;
    const r = await send("DELETE", `/condominiums/${condominiumId}/members/${m.id}`);
    if (!r.ok) return setError(r.error);
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
              Dar acesso
            </Button>
          ) : undefined
        }
      >
        Pessoas com acesso
      </CardTitle>
      <ul className="divide-y divide-line text-sm">
        {members.map((m) => (
          <li key={`${m.email}-${m.role}`} className="flex items-center justify-between gap-2 py-2">
            <span className="min-w-0">
              <span className="block truncate">{m.name}</span>
              <span className="text-xs text-muted">
                {ROLE_LABEL[m.role] ?? m.role} ·{" "}
                {m.scope === "administradora" ? "toda a carteira" : "este condomínio"}
              </span>
            </span>
            {m.id && (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remover acesso de ${m.name}`}
                onClick={() => void remove(m)}
              >
                <Trash2 size={14} aria-hidden />
              </Button>
            )}
          </li>
        ))}
      </ul>
      {open && (
        <div className="mt-3 space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
          <Field id="m-name" label="Nome" required>
            <input
              id="m-name"
              className={controlClass}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field
            id="m-email"
            label="E-mail"
            required
            hint="A pessoa entra com um link enviado a este e-mail."
          >
            <input
              id="m-email"
              type="email"
              className={controlClass}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field id="m-role" label="Papel" required>
            <select
              id="m-role"
              className={controlClass}
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {ROLE_LABEL[p]}
                </option>
              ))}
            </select>
          </Field>
          <Feedback error={error} ok={null} />
          <div className="flex gap-2">
            <Button
              variant="primary"
              icon={<UserCheck size={16} />}
              onClick={() => void add()}
              disabled={busy || form.name.trim().length < 3 || !form.email.includes("@")}
            >
              {busy ? "Salvando…" : "Dar acesso"}
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      {!open && <Feedback error={error} ok={ok} />}
    </Card>
  );
}
