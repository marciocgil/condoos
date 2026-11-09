"use client";

import { ArrowUp, Banknote, FileSignature, FileText, Loader2, Receipt, Store } from "lucide-react";
import { BarChart3, ShieldAlert, ShieldCheck, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import { cx } from "@/components/ui/cx";
import { textareaClass } from "@/components/ui/Field";
import type { ChatCitation, ChatMessage, ChatScreen, SuggestedAction } from "@/lib/types";

type Variant = "sindico" | "admin";

const SUGGESTIONS = [
  "Qual o valor em risco no último mês?",
  "Quanto pagamos de portaria pelo contrato?",
  "O que a convenção diz sobre gastos com obras?",
  "Compare a conta de água dos dois últimos meses.",
];

const ICON: Record<ChatCitation["kind"], LucideIcon> = {
  achado: ShieldAlert,
  despesa: Receipt,
  contrato: FileSignature,
  documento: FileText,
  movimento: Banknote,
  fornecedor: Store,
  resumo: BarChart3,
  obrigacao: ShieldCheck,
};

/** Where a citation opens: the screen that shows the record, or the original file. */
function citationHref(c: ChatCitation, condoId: string, variant: Variant): string | null {
  const sindico = `/condominio/${condoId}`;
  switch (c.kind) {
    case "achado":
      return variant === "sindico"
        ? `${sindico}/achados/${c.id}`
        : `/admin/achados/${condoId}/${c.id}`;
    case "contrato":
      return variant === "sindico" ? `${sindico}/contratos` : "/admin/contratos";
    case "documento":
      return `/api/condominiums/${condoId}/documents/${c.id}/file`;
    case "despesa":
    case "movimento":
      return variant === "sindico" ? `${sindico}/historico` : null;
    case "fornecedor":
      return variant === "admin" ? "/admin/fornecedores" : null;
    case "obrigacao":
      return variant === "sindico"
        ? `${sindico}/conformidade/${c.id}`
        : `/admin/conformidade/${condoId}/${c.id}`;
    case "resumo":
      return variant === "sindico" && /^\d{4}-\d{2}$/.test(c.id)
        ? `${sindico}/resumo?competencia=${c.id}`
        : variant === "sindico"
          ? `${sindico}/resumo`
          : "/admin/carteira";
  }
}

function actionHref(a: SuggestedAction, condoId: string, variant: Variant): string | null {
  if (a.tipo === "abrir_achado" && a.id) {
    return citationHref({ kind: "achado", id: a.id, ref: "", label: "" }, condoId, variant);
  }
  if (a.tipo === "ver_contrato") {
    return citationHref({ kind: "contrato", id: a.id ?? "", ref: "", label: "" }, condoId, variant);
  }
  if (a.tipo === "ver_despesas") {
    return variant === "sindico" ? `/condominio/${condoId}/historico` : null;
  }
  return null;
}

const DEFAULT_LABEL: Record<SuggestedAction["tipo"], string> = {
  abrir_achado: "Abrir achado",
  ver_contrato: "Ver contrato",
  ver_despesas: "Ver histórico de despesas",
};

/** Amounts in bold, as in the mockup ("R$ 4.880"). */
function emphasize(text: string): ReactNode[] {
  return text.split(/(R\$\s?[\d.]+(?:,\d{2})?)/g).map((part, i) =>
    /^R\$/.test(part) ? (
      <strong key={i} className="tabular font-semibold text-fg">
        {part}
      </strong>
    ) : (
      part
    ),
  );
}

function Citations({
  items,
  condoId,
  variant,
}: {
  items: ChatCitation[];
  condoId: string;
  variant: Variant;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-xs font-medium tracking-wide text-fg-2 uppercase">Fontes</p>
      <ul className="flex flex-wrap gap-1.5">
        {items.map((c) => {
          const Icon = ICON[c.kind] ?? FileText;
          const href = citationHref(c, condoId, variant);
          const chip = cx(
            "inline-flex max-w-full items-center gap-1.5 rounded-full border border-line bg-bg-2 px-2.5 py-1 text-xs text-fg",
            href && "transition-ui hover:border-control",
          );
          const body = (
            <>
              <Icon size={13} aria-hidden className="shrink-0 text-info" />
              <span className="truncate">{c.label}</span>
            </>
          );
          return (
            <li key={c.ref} className="max-w-full">
              {href === null ? (
                <span className={chip}>{body}</span>
              ) : c.kind === "documento" ? (
                <a href={href} target="_blank" rel="noreferrer" className={chip}>
                  {body}
                </a>
              ) : (
                <Link href={href} className={chip}>
                  {body}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** "Pergunte ao CondoOS": read-only answers with sources and at most one suggested action. */
export function ChatPanel({
  condominiumId,
  condominiumName,
  initial,
  screen,
  variant,
}: {
  condominiumId: string;
  condominiumName: string;
  initial: ChatMessage[];
  screen: ChatScreen;
  variant: Variant;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(initial);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, busy]);

  async function ask(text: string) {
    const q = text.trim();
    if (q.length < 2 || busy) return;
    setBusy(true);
    setError(null);
    setQuestion("");
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: q,
      citations: [],
      suggested_action: null,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, optimistic]);
    try {
      const res = await fetch(`/api/condominiums/${condominiumId}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q, screen }),
      });
      const body = (await res.json().catch(() => null)) as
        (ChatMessage & { detail?: string }) | null;
      if (!res.ok || !body) {
        setError(body?.detail ?? "Não foi possível responder agora. Tente de novo.");
        setMessages((m) => m.filter((x) => x.id !== optimistic.id));
        setQuestion(q);
        return;
      }
      setMessages((m) => [...m, body]);
    } catch {
      setError("Sem conexão com o servidor. Tente de novo.");
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setQuestion(q);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-[22px] leading-tight font-semibold">Pergunte ao CondoOS</h1>
        <p className="mt-0.5 text-sm text-fg-2">{condominiumName}</p>
        {screen.screen === "achado" && screen.finding_id && (
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs text-fg-2">
            <ShieldAlert size={13} aria-hidden className="text-info" />
            Respondendo sobre o achado que você estava vendo
          </p>
        )}
      </div>

      <div role="log" aria-live="polite" aria-busy={busy} className="flex flex-col gap-3">
        {messages.length === 0 && !busy && (
          <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
            <p className="text-sm text-fg-2">
              Pergunte sobre despesas, achados, contratos, fornecedores ou documentos deste
              condomínio. Toda resposta mostra de onde veio cada número.
            </p>
            <ul className="mt-3 flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => void ask(s)}
                    className="transition-ui w-full rounded-[var(--radius-control)] border border-line bg-bg-2 px-3 py-2 text-left text-sm hover:border-control"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {messages.map((m) =>
          m.role === "user" ? (
            <div
              key={m.id}
              className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-elevated px-4 py-2.5 text-sm"
            >
              <span className="sr-only">Você perguntou: </span>
              {m.content}
            </div>
          ) : (
            <article
              key={m.id}
              className="rounded-[var(--radius-card)] border border-info/60 bg-surface px-4 py-3"
            >
              <span className="sr-only">Resposta do CondoOS: </span>
              <p className="text-[15px] leading-relaxed whitespace-pre-line text-fg">
                {emphasize(m.content)}
              </p>
              <Citations items={m.citations} condoId={condominiumId} variant={variant} />
              {m.suggested_action &&
                (() => {
                  const href = actionHref(m.suggested_action, condominiumId, variant);
                  if (!href) return null;
                  return (
                    <Link
                      href={href}
                      className="transition-ui mt-3 flex h-10 w-full items-center justify-center rounded-[var(--radius-button)] border border-info/60 bg-info/10 text-sm font-medium text-fg hover:bg-info/20"
                    >
                      {m.suggested_action.rotulo ?? DEFAULT_LABEL[m.suggested_action.tipo]}
                    </Link>
                  );
                })()}
            </article>
          ),
        )}
        {busy && (
          <p className="inline-flex items-center gap-2 text-sm text-fg-2">
            <Loader2 size={16} aria-hidden className="animate-spin" />
            Consultando os dados do condomínio…
          </p>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-[var(--radius-control)] border border-danger/50 px-3 py-2 text-sm text-danger"
        >
          {error}
        </p>
      )}

      <form onSubmit={onSubmit} className="sticky bottom-24 flex flex-col gap-1.5 bg-bg pt-2">
        <label htmlFor="chat-question" className="sr-only">
          Sua pergunta
        </label>
        <div className="flex items-end gap-2">
          <textarea
            id="chat-question"
            rows={2}
            maxLength={1000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void ask(question);
              }
            }}
            placeholder="Pergunte sobre o condomínio…"
            className={cx(textareaClass, "min-h-11 resize-none")}
          />
          <button
            type="submit"
            disabled={busy || question.trim().length < 2}
            className={cx(buttonClass("primary"), "h-11 w-11 shrink-0 px-0")}
            aria-label="Enviar pergunta"
          >
            <ArrowUp size={18} aria-hidden />
          </button>
        </div>
        <p className="text-xs text-fg-2">
          Só dados deste condomínio. O assistente só consulta; decisões são tomadas nas telas.
        </p>
      </form>
    </div>
  );
}
