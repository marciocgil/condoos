"use client";

import { ChevronLeft, FileCheck2, Link2, Paperclip, Plus, Unlink } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { Timeline } from "@/components/ui/Timeline";
import { send } from "@/lib/client";
import { formatDate, formatDateTime } from "@/lib/format";
import {
  CASE_CATEGORY_LABEL,
  CASE_MOVE_LABEL,
  CASE_MOVE_NEEDS_REASON,
  CASE_ORIGIN_LABEL,
  CASE_SEVERITY_LABEL,
  CASE_STATUS_LABEL,
  LINK_TYPE_LABEL,
  TASK_MOVE_LABEL,
  TASK_STATUS_LABEL,
} from "@/lib/labels";
import type { CaseDetail, CaseEvent, CaseLink, CaseTask } from "@/lib/types";

import { CaseAttention, CaseStatusBadge } from "./CaseStatusBadge";

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function Feedback({ error }: { error: string | null }) {
  return error ? (
    <p role="alert" className="text-sm text-danger">
      {error}
    </p>
  ) : null;
}

function eventText(e: CaseEvent): ReactNode {
  const s = (v: string | null) => (v ? (CASE_STATUS_LABEL[v] ?? TASK_STATUS_LABEL[v] ?? v) : "—");
  switch (e.kind) {
    case "created":
      return "abriu o assunto";
    case "status_changed":
      return (
        <>
          mudou o estado: {s(e.from_value)} → {s(e.to_value)}
        </>
      );
    case "owner_changed":
      return "definiu o responsável";
    case "due_changed":
      return "mudou o prazo da próxima ação";
    case "next_action_changed":
      return <>mudou a próxima ação para “{e.to_value}”</>;
    case "linked":
      return (
        <>vinculou {(LINK_TYPE_LABEL[String(e.details.target_type)] ?? "registro").toLowerCase()}</>
      );
    case "unlinked":
      return "desfez um vínculo";
    case "evidence_added":
      return "anexou evidência";
    case "task_created":
      return <>criou a tarefa “{e.to_value}”</>;
    case "task_status_changed":
      return (
        <>
          mudou uma tarefa: {s(e.from_value)} → {s(e.to_value)}
        </>
      );
    case "task_due_changed":
      return "mudou o prazo de uma tarefa";
    case "comment":
      return "comentou";
    default:
      return "editou o assunto";
  }
}

/** Assunto 360° (spec §7.4): header, next action, tasks, evidence and links, timeline. */
export function CaseDetailView({
  detail: c,
  backHref,
  backLabel,
  findingPath,
  casePath,
}: {
  detail: CaseDetail;
  backHref: string;
  backLabel: string;
  /** Path templates with "{id}" (strings: functions cannot cross to the client). */
  findingPath: string;
  casePath: string;
}) {
  const findingHref = (id: string) => findingPath.replace("{id}", id);
  const caseHref = (id: string) => casePath.replace("{id}", id);
  const router = useRouter();
  const base = `/condominiums/${c.condominium_id}/cases/${c.id}`;
  const open = !["resolvido", "cancelado"].includes(c.status);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function act(method: "POST" | "PATCH", path: string, body: unknown): Promise<boolean> {
    setBusy(true);
    setError(null);
    const r = await send(method, `${base}${path}`, body);
    setBusy(false);
    if (!r.ok) {
      setError(r.error);
      return false;
    }
    router.refresh();
    return true;
  }

  // --- moves
  const [move, setMove] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [until, setUntil] = useState(inDays(30));
  // Moves that need a reason open a small form; only "Confirmar" sends them.
  async function doMove(to: string, confirmed = false) {
    const needs =
      CASE_MOVE_NEEDS_REASON.has(to) ||
      (c.status === "aguardando_validacao" && to === "em_execucao");
    if (needs && !confirmed) {
      setMove(move === to ? null : to);
      setReason("");
      return;
    }
    const ok = await act("POST", "/transitions", {
      to,
      reason: reason || undefined,
      suspended_until: to === "suspenso_justificadamente" ? until : undefined,
    });
    if (ok) setMove(null);
  }

  // --- next action
  const [editing, setEditing] = useState(false);
  const [next, setNext] = useState({
    next_action: c.next_action ?? "",
    due: (c.next_action_due_at ?? "").slice(0, 10),
    reason: "",
  });

  // --- tasks
  const [taskForm, setTaskForm] = useState({
    title: "",
    who: "",
    label: "",
    due: inDays(3),
    requires_evidence: false,
  });
  const [taskReason, setTaskReason] = useState<Record<string, string>>({});

  async function moveTask(t: CaseTask, to: string, file?: File) {
    let evidence: string | undefined;
    if (to === "concluida" && t.requires_evidence) {
      if (!file) {
        setError("Esta tarefa exige evidência: escolha o arquivo antes de concluir.");
        return;
      }
      const id = await upload(file, `Evidência da tarefa: ${t.title}`);
      if (!id) return;
      evidence = id;
    }
    await act("PATCH", `/tasks/${t.id}`, {
      status: to,
      reason: taskReason[t.id] || undefined,
      evidence_document_id: evidence,
    });
  }

  // --- evidence
  const [file, setFile] = useState<File | null>(null);
  const [fileNote, setFileNote] = useState("");
  async function upload(f: File, note: string): Promise<string | null> {
    setBusy(true);
    setError(null);
    const data = new FormData();
    data.append("file", f);
    if (note) data.append("description", note);
    try {
      const res = await fetch(`/api${base}/evidence/upload`, { method: "POST", body: data });
      const body = await res.json().catch(() => null);
      setBusy(false);
      if (!res.ok) {
        setError(
          typeof body?.detail === "string" ? body.detail : "Não foi possível anexar o arquivo.",
        );
        return null;
      }
      const links = (body?.links ?? []) as CaseLink[];
      const added = links.filter((l) => l.as_evidence && l.active).at(-1);
      router.refresh();
      return added?.target_id ?? null;
    } catch {
      setBusy(false);
      setError("Sem conexão com o servidor. Tente de novo.");
      return null;
    }
  }

  // --- comment
  const [comment, setComment] = useState("");

  const evidence = c.links.filter((l) => l.as_evidence && l.active);
  const linked = c.links.filter((l) => !l.as_evidence && l.active);
  const undone = c.links.filter((l) => !l.active);

  function linkHref(l: CaseLink): string | null {
    if (l.target_type === "finding") return findingHref(l.target_id);
    if (l.target_type === "case") return caseHref(l.target_id);
    if (l.target_type === "document")
      return `/api/condominiums/${c.condominium_id}/documents/${l.target_id}/file`;
    return null;
  }

  async function unlink(l: CaseLink) {
    const why = window.prompt("Por que desfazer este vínculo? (mínimo de 5 caracteres)");
    if (!why) return;
    await act("POST", `/links/${l.id}/unlink`, { reason: why });
  }

  function LinkRow({ l }: { l: CaseLink }) {
    const href = linkHref(l);
    return (
      <li className="flex items-start justify-between gap-2 py-2">
        <span className="min-w-0">
          <span className="text-xs text-muted">
            {LINK_TYPE_LABEL[l.target_type] ?? l.target_type} ·{" "}
          </span>
          {href ? (
            <a href={href} className="underline">
              {l.label}
            </a>
          ) : (
            l.label
          )}
          {l.reason && <span className="block text-xs text-fg-2">{l.reason}</span>}
          <span className="block text-xs text-muted">
            {l.linked_by} · {formatDateTime(l.linked_at)}
            {l.unlinked_at && ` · desfeito em ${formatDateTime(l.unlinked_at)}`}
          </span>
        </span>
        {c.can_manage && open && l.active && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Desfazer vínculo com ${l.label}`}
            onClick={() => void unlink(l)}
          >
            <Unlink size={14} aria-hidden />
          </Button>
        )}
      </li>
    );
  }

  return (
    <article className="space-y-5" aria-labelledby="case-title">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> {backLabel}
      </Link>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-muted tabular-nums">{c.number}</span>
          <CaseStatusBadge status={c.status} />
          <Badge tone="neutral">
            Criticidade {CASE_SEVERITY_LABEL[c.severity]?.toLowerCase() ?? c.severity}
          </Badge>
          <CaseAttention flags={c.attention} />
        </div>
        <h1 id="case-title" className="text-xl font-semibold">
          {c.title}
        </h1>
        <p className="text-[13px] text-fg-2">
          {CASE_CATEGORY_LABEL[c.category] ?? c.category} · origem:{" "}
          {CASE_ORIGIN_LABEL[c.origin] ?? c.origin} · {c.condominium_name} · aberto por{" "}
          {c.created_by} em {formatDateTime(c.created_at)}
        </p>
      </header>

      <Card tone={c.attention.length ? "highlight" : "default"}>
        <CardTitle
          action={
            c.can_manage && open && !editing ? (
              <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                Alterar
              </Button>
            ) : undefined
          }
        >
          Próxima ação
        </CardTitle>
        {c.status === "suspenso_justificadamente" ? (
          <p className="text-sm">
            Suspenso até {c.suspended_until ? formatDate(c.suspended_until) : "—"}:{" "}
            {c.suspension_reason}
          </p>
        ) : (
          <dl className="grid gap-1 text-sm">
            <div>
              <dt className="sr-only">Ação</dt>
              <dd className="font-medium">{c.next_action ?? "—"}</dd>
            </div>
            <div className="text-fg-2">
              <dt className="inline">Responsável: </dt>
              <dd className="inline">{c.owner?.name ?? "sem responsável"}</dd>
              {c.next_action_due_at && <> · prazo {formatDateTime(c.next_action_due_at)}</>}
            </div>
          </dl>
        )}
        {editing && (
          <div className="mt-3 space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
            <Field id="n-action" label="Próxima ação">
              <input
                id="n-action"
                className={controlClass}
                value={next.next_action}
                onChange={(e) => setNext({ ...next, next_action: e.target.value })}
              />
            </Field>
            <Field id="n-due" label="Prazo">
              <input
                id="n-due"
                type="date"
                className={controlClass}
                value={next.due}
                onChange={(e) => setNext({ ...next, due: e.target.value })}
              />
            </Field>
            <Field
              id="n-reason"
              label="Motivo da mudança de prazo"
              hint="Obrigatório se o prazo mudar."
            >
              <input
                id="n-reason"
                className={controlClass}
                value={next.reason}
                onChange={(e) => setNext({ ...next, reason: e.target.value })}
              />
            </Field>
            {c.people.length > 0 && (
              <p className="text-xs text-muted">
                Para trocar o responsável, use a lista de tarefas ou peça a quem gerencia.
              </p>
            )}
            <div className="flex gap-2">
              <Button
                variant="primary"
                disabled={busy}
                onClick={async () => {
                  const changes: Record<string, string> = {};
                  if (next.next_action !== (c.next_action ?? ""))
                    changes.next_action = next.next_action;
                  if (next.due !== (c.next_action_due_at ?? "").slice(0, 10))
                    changes.next_action_due_at = next.due;
                  if (await act("PATCH", "", { ...changes, reason: next.reason || undefined }))
                    setEditing(false);
                }}
              >
                Salvar
              </Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        )}
      </Card>

      {c.allowed_transitions.length > 0 && (
        <section aria-label="Mudar o estado" className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {c.allowed_transitions.map((to) => (
              <Button
                key={to}
                variant={
                  to === "resolvido" ? "primary" : to === "cancelado" ? "danger" : "secondary"
                }
                disabled={busy}
                aria-expanded={CASE_MOVE_NEEDS_REASON.has(to) ? move === to : undefined}
                onClick={() => void doMove(to)}
              >
                {CASE_MOVE_LABEL[to] ?? to}
              </Button>
            ))}
          </div>
          {move && (
            <div className="space-y-2 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
              {move === "resolvido" && (
                <p className="text-[13px] text-fg-2">
                  Critério de conclusão: {c.resolution_criterion}
                </p>
              )}
              <Field
                id="m-reason"
                label={move === "resolvido" ? "Como o critério foi atendido?" : "Motivo"}
                required
              >
                <textarea
                  id="m-reason"
                  rows={2}
                  className={textareaClass}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </Field>
              {move === "suspenso_justificadamente" && (
                <Field id="m-until" label="Suspenso até" required>
                  <input
                    id="m-until"
                    type="date"
                    className={controlClass}
                    value={until}
                    onChange={(e) => setUntil(e.target.value)}
                  />
                </Field>
              )}
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={busy || reason.trim().length < 5}
                  onClick={() => void doMove(move, true)}
                >
                  Confirmar: {CASE_MOVE_LABEL[move]?.toLowerCase()}
                </Button>
                <Button variant="ghost" onClick={() => setMove(null)}>
                  Cancelar
                </Button>
              </div>
            </div>
          )}
        </section>
      )}
      <Feedback error={error} />

      <Card>
        <CardTitle>Contexto</CardTitle>
        {c.description && <p className="mb-2 text-sm whitespace-pre-line">{c.description}</p>}
        <p className="text-[13px] text-fg-2">
          Critério de conclusão: {c.resolution_criterion}
          {c.requires_evidence ? " · exige evidência" : ""}
        </p>
      </Card>

      <Card>
        <CardTitle>Tarefas</CardTitle>
        {c.tasks.length === 0 && <p className="text-sm text-fg-2">Nenhuma tarefa ainda.</p>}
        <ul className="divide-y divide-line">
          {c.tasks.map((t) => (
            <li key={t.id} className="space-y-2 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{t.title}</span>
                <Badge
                  tone={
                    t.status === "concluida"
                      ? "success"
                      : t.status === "bloqueada"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {TASK_STATUS_LABEL[t.status] ?? t.status}
                </Badge>
                {t.overdue && <Badge tone="danger">Atrasada</Badge>}
                {t.requires_evidence && (
                  <Badge tone="info" icon={<FileCheck2 size={12} />}>
                    Exige evidência
                  </Badge>
                )}
              </div>
              <p className="text-xs text-fg-2">
                {t.assignee?.name ?? t.assignee_label ?? "—"} · prazo {formatDateTime(t.due_at)}
                {t.blocked_reason && ` · bloqueada: ${t.blocked_reason}`}
              </p>
              {t.allowed_moves.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  {t.allowed_moves.includes("concluida") && t.requires_evidence && (
                    <input
                      type="file"
                      aria-label={`Evidência para concluir ${t.title}`}
                      className="text-xs"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  )}
                  {(t.allowed_moves.includes("bloqueada") ||
                    t.allowed_moves.includes("cancelada")) && (
                    <input
                      aria-label={`Motivo para a tarefa ${t.title}`}
                      placeholder="Motivo (bloquear ou cancelar)"
                      className={`${controlClass} h-8 w-48 text-[13px]`}
                      value={taskReason[t.id] ?? ""}
                      onChange={(e) => setTaskReason({ ...taskReason, [t.id]: e.target.value })}
                    />
                  )}
                  {t.allowed_moves.map((m) => (
                    <Button
                      key={m}
                      size="sm"
                      variant={m === "concluida" ? "primary" : "secondary"}
                      disabled={busy}
                      onClick={() => void moveTask(t, m, file ?? undefined)}
                    >
                      {TASK_MOVE_LABEL[m] ?? m}
                    </Button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
        {c.can_manage && open && (
          <div className="mt-3 space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
            <p className="text-[13px] font-medium">Nova tarefa</p>
            <Field id="t-title" label="O que fazer" required>
              <input
                id="t-title"
                className={controlClass}
                value={taskForm.title}
                onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field id="t-who" label="Quem faz">
                <select
                  id="t-who"
                  className={controlClass}
                  value={taskForm.who}
                  onChange={(e) => setTaskForm({ ...taskForm, who: e.target.value })}
                >
                  <option value="">Pessoa sem acesso (informe o nome)</option>
                  {c.people.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field id="t-due" label="Prazo" required>
                <input
                  id="t-due"
                  type="date"
                  className={controlClass}
                  value={taskForm.due}
                  onChange={(e) => setTaskForm({ ...taskForm, due: e.target.value })}
                />
              </Field>
            </div>
            {!taskForm.who && (
              <Field id="t-label" label="Nome de quem faz" hint="Ex.: zelador, prestador.">
                <input
                  id="t-label"
                  className={controlClass}
                  value={taskForm.label}
                  onChange={(e) => setTaskForm({ ...taskForm, label: e.target.value })}
                />
              </Field>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={taskForm.requires_evidence}
                onChange={(e) => setTaskForm({ ...taskForm, requires_evidence: e.target.checked })}
              />
              Exigir evidência para concluir
            </label>
            <Button
              icon={<Plus size={14} aria-hidden />}
              disabled={busy}
              onClick={async () => {
                const ok = await act("POST", "/tasks", {
                  title: taskForm.title,
                  assignee_user_id: taskForm.who || undefined,
                  assignee_label: taskForm.who ? undefined : taskForm.label,
                  due_at: taskForm.due,
                  requires_evidence: taskForm.requires_evidence,
                });
                if (ok)
                  setTaskForm({
                    title: "",
                    who: "",
                    label: "",
                    due: inDays(3),
                    requires_evidence: false,
                  });
              }}
            >
              Criar tarefa
            </Button>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Evidências</CardTitle>
        {evidence.length === 0 ? (
          <p className="text-sm text-fg-2">Nenhuma evidência anexada.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {evidence.map((l) => (
              <LinkRow key={l.id} l={l} />
            ))}
          </ul>
        )}
        {c.can_add_evidence && (
          <div className="mt-3 space-y-2 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
            <Field id="e-file" label="Arquivo (foto, laudo, nota)">
              <input
                id="e-file"
                type="file"
                className="text-sm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </Field>
            <Field id="e-note" label="O que este arquivo comprova">
              <input
                id="e-note"
                className={controlClass}
                value={fileNote}
                onChange={(e) => setFileNote(e.target.value)}
              />
            </Field>
            <Button
              icon={<Paperclip size={14} aria-hidden />}
              disabled={busy || !file}
              onClick={async () => {
                if (file && (await upload(file, fileNote))) {
                  setFile(null);
                  setFileNote("");
                }
              }}
            >
              Anexar evidência
            </Button>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Vínculos</CardTitle>
        {linked.length === 0 && c.cited_by.length === 0 ? (
          <p className="text-sm text-fg-2">Nenhum registro vinculado.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {linked.map((l) => (
              <LinkRow key={l.id} l={l} />
            ))}
            {c.cited_by.map((x) => (
              <li key={x.id} className="py-2">
                <span className="text-xs text-muted">Citado pelo assunto · </span>
                <a className="underline" href={caseHref(x.id)}>
                  <Link2 size={12} className="mr-1 inline" aria-hidden />
                  {x.number} — {x.title}
                </a>
              </li>
            ))}
          </ul>
        )}
        {undone.length > 0 && (
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-fg-2">
              Vínculos desfeitos ({undone.length})
            </summary>
            <ul className="divide-y divide-line">
              {undone.map((l) => (
                <LinkRow key={l.id} l={l} />
              ))}
            </ul>
          </details>
        )}
      </Card>

      {c.can_comment && (
        <div className="space-y-2">
          <Field id="c-comment" label="Comentário">
            <textarea
              id="c-comment"
              rows={2}
              className={textareaClass}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </Field>
          <Button
            disabled={busy || comment.trim().length < 2}
            onClick={async () => {
              if (await act("POST", "/comments", { body: comment })) setComment("");
            }}
          >
            Comentar
          </Button>
        </div>
      )}

      <section aria-labelledby="case-history">
        <h2 id="case-history" className="mb-3 text-base font-semibold">
          Linha do tempo
        </h2>
        <Timeline
          label="Linha do tempo do assunto"
          items={[...c.events].reverse().map((e) => ({
            id: e.id,
            when: formatDateTime(e.at),
            who: e.who,
            what: eventText(e),
            detail: e.reason ? <q>{e.reason}</q> : undefined,
          }))}
        />
      </section>
    </article>
  );
}
