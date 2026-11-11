"use client";

import { Copy } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, controlClass, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { PromptVersion } from "@/lib/types";

export function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size="sm"
      icon={<Copy size={14} aria-hidden />}
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => setDone(true));
      }}
    >
      {done ? "Copiado" : "Copiar"}
    </Button>
  );
}

/** Draft → test → submit → approval by another person → active; rollback. Nothing edits a
 * version in place: a change is always a new version. */
export function PromptGovernance({
  agentId,
  versions,
  canManage,
  canApprove,
}: {
  agentId: string;
  versions: PromptVersion[];
  canManage: boolean;
  canApprove: boolean;
}) {
  const router = useRouter();
  const active = versions.find((v) => v.status === "ACTIVE");
  const [text, setText] = useState(active?.text ?? "");
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const open = versions.filter((v) => v.status === "DRAFT" || v.status === "IN_REVIEW");
  const previous = versions.filter((v) => v.status === "ARCHIVED" && v.activated_at);

  async function call(path: string, body?: unknown, ok = "Feito.") {
    setBusy(true);
    setMessage(null);
    const r = await send<{
      passed?: boolean;
      results?: { check: string; passed: boolean; detail: string }[];
    }>("POST", path, body);
    setBusy(false);
    if (!r.ok) {
      setMessage(r.error);
      return;
    }
    if (r.data.results) {
      const failed = r.data.results.filter((x) => !x.passed);
      setMessage(
        r.data.passed ? "Testes passaram." : "Falhou: " + failed.map((x) => x.detail).join("; "),
      );
    } else setMessage(ok);
    router.refresh();
  }

  return (
    <div className="space-y-6" data-testid="prompt-governance">
      {canManage && (
        <div className="space-y-3">
          <p className="text-sm font-medium">Novo rascunho (a partir da versão ativa)</p>
          <Field
            id="draft-text"
            label="Texto do prompt do agente"
            hint="Só a parte do agente. A regra de segurança e a tarefa são da aplicação."
          >
            <textarea
              id="draft-text"
              className={textareaClass}
              rows={10}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          <Field id="draft-note" label="O que muda e por quê" required>
            <input
              id="draft-note"
              className={controlClass}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
          <Button
            disabled={busy || note.trim().length < 10 || text.trim() === active?.text}
            onClick={() =>
              void call(
                `/audit/agents/${agentId}/prompt-drafts`,
                { text, note },
                "Rascunho criado.",
              )
            }
          >
            Criar rascunho
          </Button>
        </div>
      )}
      {open.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium">Em andamento</p>
          {open.map((v) => (
            <div
              key={v.id}
              className="rounded-[var(--radius-control)] border border-control p-3 text-sm"
            >
              <p>
                Versão {v.version} · {v.status === "DRAFT" ? "Rascunho" : "Em revisão"} ·{" "}
                {v.author ?? "—"}: {v.change_note}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {canManage && v.status === "DRAFT" && (
                  <>
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() => void call(`/audit/prompt-versions/${v.id}/test`)}
                    >
                      Testar no sandbox
                    </Button>
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        void call(
                          `/audit/prompt-versions/${v.id}/submit`,
                          undefined,
                          "Enviada para revisão.",
                        )
                      }
                    >
                      Enviar para revisão
                    </Button>
                  </>
                )}
                {canManage && (
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={busy}
                    onClick={() =>
                      void call(`/audit/prompt-versions/${v.id}/discard`, undefined, "Descartada.")
                    }
                  >
                    Descartar
                  </Button>
                )}
              </div>
              {v.status === "IN_REVIEW" && canApprove && (
                <div className="mt-3 flex flex-wrap items-end gap-2">
                  <Field
                    id={`approve-${v.id}`}
                    label="Motivo da aprovação (outra pessoa que não o autor)"
                  >
                    <input
                      id={`approve-${v.id}`}
                      className={controlClass}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </Field>
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={busy || reason.trim().length < 10}
                    onClick={() =>
                      void call(
                        `/audit/prompt-versions/${v.id}/approve`,
                        { reason },
                        "Aprovada e ativada.",
                      )
                    }
                  >
                    Aprovar e ativar
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {canManage && previous.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Voltar a uma versão anterior</p>
          <Field id="rollback-reason" label="Motivo da volta">
            <input
              id="rollback-reason"
              className={controlClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            {previous.map((v) => (
              <Button
                key={v.id}
                size="sm"
                disabled={busy || reason.trim().length < 10}
                onClick={() =>
                  void call(
                    `/audit/prompt-versions/${v.id}/rollback`,
                    { reason },
                    `Versão ${v.version} ativa de novo.`,
                  )
                }
              >
                Voltar para a versão {v.version}
              </Button>
            ))}
          </div>
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
