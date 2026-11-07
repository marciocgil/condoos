"use client";

import {
  Ban,
  CheckCircle2,
  Clock,
  Copy,
  FileClock,
  Link2,
  Send,
  type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDate } from "@/lib/format";
import type { Delegation, DelegationLink, DelegationStatus } from "@/lib/types";

const STATUS: Record<DelegationStatus, { label: string; tone: BadgeTone; icon: LucideIcon }> = {
  rascunho: { label: "Rascunho", tone: "neutral", icon: FileClock },
  link_gerado: { label: "Link gerado, falta enviar", tone: "info", icon: Link2 },
  compartilhado: { label: "Enviado por você", tone: "info", icon: Send },
  arquivo_recebido: { label: "Arquivos recebidos", tone: "success", icon: CheckCircle2 },
  concluido: { label: "Concluído", tone: "success", icon: CheckCircle2 },
  revogado: { label: "Revogado", tone: "danger", icon: Ban },
  expirado: { label: "Link vencido", tone: "warning", icon: Clock },
};

function NewRequest({ base }: { base: string }) {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", scope: "", items: "", due: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setBusy(true);
    setError(null);
    const r = await send("POST", base, {
      recipient_name: form.name,
      recipient_email: form.email.trim() || null,
      scope: form.scope,
      items: form.items
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      due_date: form.due || null,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setForm({ name: "", email: "", scope: "", items: "", due: "" });
    router.refresh();
  }
  return (
    <Card aria-labelledby="novo-pedido">
      <CardTitle>
        <span id="novo-pedido">Novo pedido de documentos</span>
      </CardTitle>
      <div className="space-y-3">
        <Field id="d-name" label="Para quem (nome)">
          <input
            id="d-name"
            className={controlClass}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Administradora, fornecedor, zelador…"
          />
        </Field>
        <Field id="d-email" label="E-mail (opcional, só para sua referência)">
          <input
            id="d-email"
            type="email"
            className={controlClass}
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field id="d-scope" label="Assunto">
          <input
            id="d-scope"
            className={controlClass}
            value={form.scope}
            onChange={(e) => setForm({ ...form, scope: e.target.value })}
            placeholder="Contratos vigentes e notas de outubro"
          />
        </Field>
        <Field id="d-items" label="Documentos esperados (um por linha)">
          <textarea
            id="d-items"
            className={`${controlClass} min-h-24`}
            value={form.items}
            onChange={(e) => setForm({ ...form, items: e.target.value })}
          />
        </Field>
        <Field id="d-due" label="Prazo (opcional)">
          <input
            id="d-due"
            type="date"
            className={controlClass}
            value={form.due}
            onChange={(e) => setForm({ ...form, due: e.target.value })}
          />
        </Field>
        <Button variant="secondary" disabled={busy} onClick={() => void save()}>
          Salvar rascunho
        </Button>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Card>
  );
}

function RequestCard({
  base,
  req,
  canManage,
  canAuthorize,
}: {
  base: string;
  req: Delegation;
  canManage: boolean;
  canAuthorize: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<DelegationLink | null>(null);
  const [copied, setCopied] = useState(false);
  const url = `${base}/${req.id}`;
  const st = STATUS[req.status];
  const open = !["concluido", "revogado"].includes(req.status);
  const done = req.items.filter((i) => i.done).length;

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setError(null);
    const r = await send<DelegationLink>("POST", `${url}/${path}`, body);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    if (path === "authorize") setLink(r.data);
    router.refresh();
  }

  return (
    <Card aria-label={`Pedido para ${req.recipient_name}`} data-testid="delegation">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{req.recipient_name}</p>
          <p className="text-[13px] text-fg-2">{req.scope}</p>
        </div>
        <Badge tone={st.tone} icon={<st.icon size={12} />}>
          {st.label}
        </Badge>
      </div>
      <p className="mt-2 text-[13px] text-muted">
        {done} de {req.items.length} documentos recebidos · {req.files_received}{" "}
        {req.files_received === 1 ? "arquivo" : "arquivos"} pelo link
        {req.link_expires_at && open ? ` · link até ${formatDate(req.link_expires_at)}` : ""}
      </p>
      <ul className="mt-3 space-y-1.5 text-sm">
        {req.items.map((item, i) => (
          <li key={i}>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={item.done}
                disabled={!canManage || busy || req.status === "revogado"}
                onChange={() =>
                  void act("items", {
                    done: req.items.map((x, j) => (j === i ? !x.done : x.done)),
                  })
                }
              />
              {item.label}
            </label>
          </li>
        ))}
      </ul>

      {link && (
        <div className="mt-4 space-y-2 rounded-[var(--radius-button)] border border-accent/60 bg-elevated p-3">
          <p className="text-[13px] font-medium">
            Link criado. Copie o texto e envie pelo seu canal: o CondoOS não envia nada.
          </p>
          <pre className="text-[13px] whitespace-pre-wrap text-fg-2">{link.message}</pre>
          <Button
            variant="primary"
            size="sm"
            icon={<Copy size={14} aria-hidden />}
            onClick={() => {
              void navigator.clipboard?.writeText(link.message).then(() => setCopied(true));
            }}
          >
            {copied ? "Texto copiado" : "Copiar o texto"}
          </Button>
        </div>
      )}

      {open && (canManage || canAuthorize) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {canAuthorize && (
            <Button
              variant={req.status === "rascunho" ? "primary" : "secondary"}
              size="sm"
              icon={<Link2 size={14} aria-hidden />}
              disabled={busy}
              onClick={() => void act("authorize")}
            >
              {req.status === "rascunho" ? "Autorizar e gerar o link" : "Gerar um link novo"}
            </Button>
          )}
          {canManage && req.status === "link_gerado" && (
            <Button
              variant="secondary"
              size="sm"
              icon={<Send size={14} aria-hidden />}
              disabled={busy}
              onClick={() => void act("shared")}
            >
              Já enviei o link
            </Button>
          )}
          {canManage && (
            <>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => void act("conclude")}
              >
                Concluir
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<Ban size={14} aria-hidden />}
                disabled={busy}
                onClick={() => void act("revoke")}
              >
                Revogar o link
              </Button>
            </>
          )}
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

/** Requests for documents to third parties (LF4, D97): the síndico authorizes a send-only
 * link and sends the ready text through their own channel; nothing is sent by the system. */
export function DelegationsPanel({
  condominiumId,
  requests,
  canManage,
  canAuthorize,
}: {
  condominiumId: string;
  requests: Delegation[];
  canManage: boolean;
  canAuthorize: boolean;
}) {
  const base = `/condominiums/${condominiumId}/delegations`;
  return (
    <div className="space-y-4">
      {canManage && <NewRequest base={base} />}
      {requests.length === 0 ? (
        <p className="text-sm text-fg-2">Nenhum pedido ainda.</p>
      ) : (
        requests.map((r) => (
          <RequestCard
            key={r.id}
            base={base}
            req={r}
            canManage={canManage}
            canAuthorize={canAuthorize}
          />
        ))
      )}
    </div>
  );
}
