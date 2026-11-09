"use client";

import { CheckCircle2, Circle, Clock, FileSearch, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CapabilityReadinessList } from "@/components/condoos/CapabilityReadiness";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { send } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { Launch, LaunchGoal, LaunchStep } from "@/lib/types";

const GOALS: { key: LaunchGoal; label: string }[] = [
  { key: "economizar", label: "Economizar dinheiro" },
  { key: "pendencias", label: "Organizar pendências" },
  { key: "fornecedores", label: "Controlar fornecedores" },
  { key: "panorama", label: "Ver um panorama" },
];

/** Where a step leads, with the step itself so the screen can say what was asked (LB-080). */
export function stepHref(condominiumId: string, step: LaunchStep): string {
  const sep = step.href.includes("?") ? "&" : "?";
  const withStep = step.href.startsWith("enviar")
    ? `${step.href}${sep}passo=${step.key}`
    : step.href;
  return `/condominio/${condominiumId}/${withStep}`;
}

/** Documents with the CondoOS team (LB-081, D108): what and since when, no promised deadline. */
function InReview({ launch }: { launch: Launch }) {
  const { total, items } = launch.in_review;
  if (total === 0) return null;
  return (
    <div className="mt-4" data-testid="journey-in-review">
      <h3 className="text-[13px] font-medium text-fg-2">Com a equipe CondoOS</h3>
      <ul className="mt-1 space-y-1 text-sm">
        {items.map((d) => (
          <li key={d.id} className="flex items-start gap-2">
            {d.state === "lendo" ? (
              <Loader2 size={14} aria-hidden className="mt-1 shrink-0 text-info" />
            ) : (
              <FileSearch size={14} aria-hidden className="mt-1 shrink-0 text-info" />
            )}
            <span className="min-w-0 break-words">
              {d.doc_type_label} {d.filename}:{" "}
              {d.state === "lendo" ? "em leitura" : "em conferência"} desde{" "}
              {formatDateTime(d.since)}
            </span>
          </li>
        ))}
      </ul>
      {total > items.length && (
        <p className="mt-1 text-[13px] text-fg-2">e mais {total - items.length}.</p>
      )}
      <p className="mt-1 text-[12px] text-muted">
        Assim que a conferência terminar, o resultado aparece aqui e nas telas do documento.
      </p>
    </div>
  );
}

function Milestones({ launch }: { launch: Launch }) {
  return (
    <>
      <ol className="mt-2 space-y-2 text-sm" aria-label="Marcos">
        {launch.milestones.map((m) => (
          <li key={m.key} className="flex items-start gap-2">
            {m.done ? (
              <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0 text-success" />
            ) : (
              <Circle size={16} aria-hidden className="mt-0.5 shrink-0 text-muted" />
            )}
            <span>
              <span className="font-medium">{m.title}</span>{" "}
              <span className="text-fg-2">({m.done ? "alcançado" : "pendente"})</span>
              <span className="block text-[13px] text-fg-2">{m.criterion}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-4">
        <CapabilityReadinessList items={launch.readiness} />
      </div>
      <p className="mt-3 text-[12px] text-muted">
        Marcos mostram o caminho; o que cada função pode fazer depende só dos dados acima, e toda
        ação continua precisando da sua aprovação.
      </p>
    </>
  );
}

/** Launch journey card (LB-005, D89; guided steps LB-080, D108) on the síndico's "Hoje".
 * One step in focus with the progress of the chosen goal; the others wait in a collapsed
 * line. Once the assessor evaluated a month (LM3) the card shrinks to one line and the
 * month's routine leads (LB-082). Milestones and progress are facts from the data; nothing
 * here turns anything on. */
export function JourneyCard({ condominiumId, launch }: { condominiumId: string; launch: Launch }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/condominiums/${condominiumId}/launch`;

  async function act(method: "PUT" | "POST", path: string, body: unknown) {
    setBusy(true);
    setError(null);
    const r = await send(method, `${base}${path}`, body);
    setBusy(false);
    if (!r.ok) setError(r.error);
    else router.refresh();
  }

  const done = launch.milestones.filter((m) => m.done).length;
  const current = launch.milestones.find((m) => !m.done);
  const operating = launch.milestones.some((m) => m.key === "LM3" && m.done);
  const [focus, ...later] = launch.next_steps;
  const { done: stepsDone, total: stepsTotal } = launch.progress;

  if (operating) {
    return (
      <Card aria-labelledby="journey-title" data-testid="journey-card">
        <details>
          <summary className="cursor-pointer text-sm">
            <span id="journey-title" className="font-medium">
              Implantação
            </span>
            <span className="text-fg-2">
              : {done} de {launch.milestones.length} marcos
              {current ? ` · próximo: ${current.title}` : " · todos alcançados"}
            </span>
          </summary>
          <InReview launch={launch} />
          <Milestones launch={launch} />
        </details>
      </Card>
    );
  }

  return (
    <Card aria-labelledby="journey-title" data-testid="journey-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="journey-title" className="text-[15px] font-semibold">
            Implantação do seu assessor
          </h2>
          <p className="text-[13px] text-fg-2">
            {done} de {launch.milestones.length} marcos
            {current ? ` · próximo: ${current.title}` : " · todos alcançados"}
          </p>
        </div>
        {launch.can_manage && (
          <Button
            variant="ghost"
            size="sm"
            aria-label="Ocultar implantação"
            icon={<X size={14} aria-hidden />}
            disabled={busy}
            onClick={() => void act("PUT", "/dismissed", { dismissed: true })}
          >
            Ocultar
          </Button>
        )}
      </div>

      {launch.goal === null && launch.can_manage && (
        <div className="mt-4">
          <p className="text-sm">
            Sou seu assessor CondoOS. Vou conhecer seu condomínio, organizar as informações e
            começar a trabalhar. Você não precisa cadastrar tudo sozinho.
          </p>
          <p className="mt-2 text-sm font-medium">Por onde quer começar?</p>
          <ul className="mt-2 flex flex-wrap gap-2" aria-label="Objetivo inicial">
            {GOALS.map((g) => (
              <li key={g.key}>
                <button
                  type="button"
                  disabled={busy}
                  className="transition-ui inline-flex h-9 items-center rounded-full border border-control bg-surface px-4 text-sm hover:bg-elevated disabled:opacity-50"
                  onClick={() => void act("PUT", "/goal", { goal: g.key })}
                >
                  {g.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {launch.done_for_you.length > 0 && (
        <div className="mt-4">
          <h3 className="text-[13px] font-medium text-fg-2">O que já fiz por você</h3>
          <ul className="mt-1 space-y-1 text-sm">
            {launch.done_for_you.map((d) => (
              <li key={d.key} className="flex items-center gap-2">
                <CheckCircle2 size={14} aria-hidden className="text-success" />
                <span className="tabular">
                  {d.count} {d.label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <InReview launch={launch} />

      {focus && (
        <div className="mt-4" data-testid={`step-${focus.key}`}>
          <h3 className="text-[13px] font-medium text-fg-2" data-testid="journey-progress">
            Passo {Math.min(stepsDone + 1, stepsTotal)} de {stepsTotal}
          </h3>
          <p className="mt-1 text-[15px] font-medium">{focus.label}</p>
          <p className="mt-1 text-sm">{focus.why}</p>
          <p className="text-[13px] text-fg-2">Libera: {focus.unlocks}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Link href={stepHref(condominiumId, focus)} className={buttonClass("primary", "sm")}>
              {focus.label}
            </Link>
            {launch.can_manage && (
              <Button
                variant="ghost"
                size="sm"
                icon={<Clock size={14} aria-hidden />}
                disabled={busy}
                onClick={() => void act("POST", "/postpone", { step: focus.key })}
              >
                Fazer depois
              </Button>
            )}
          </div>
        </div>
      )}

      {!focus && launch.goal !== null && stepsDone >= stepsTotal && (
        <p className="mt-4 flex items-center gap-2 text-sm" data-testid="journey-progress">
          <CheckCircle2 size={14} aria-hidden className="text-success" />
          Passos do seu objetivo concluídos. Eu sigo acompanhando e aviso aqui o que mudar.
        </p>
      )}

      {later.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-[13px] text-fg-2 hover:text-fg">
            Depois: {later.map((s) => s.label).join(" · ")}
          </summary>
          <ul className="mt-2 space-y-3">
            {later.map((s) => (
              <li key={s.key} data-testid={`step-${s.key}`}>
                <p className="text-sm">{s.why}</p>
                <p className="text-[13px] text-fg-2">Libera: {s.unlocks}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Link
                    href={stepHref(condominiumId, s)}
                    className={buttonClass("secondary", "sm")}
                  >
                    {s.label}
                  </Link>
                  {launch.can_manage && (
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Clock size={14} aria-hidden />}
                      disabled={busy}
                      onClick={() => void act("POST", "/postpone", { step: s.key })}
                    >
                      Fazer depois
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-[13px] text-fg-2 hover:text-fg">
          Marcos e o que cada função precisa
        </summary>
        <Milestones launch={launch} />
      </details>

      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}

/** Shown when the card was hidden: brings it back. */
export function JourneyReopen({ condominiumId }: { condominiumId: string }) {
  const router = useRouter();
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={async () => {
        await send("PUT", `/condominiums/${condominiumId}/launch/dismissed`, { dismissed: false });
        router.refresh();
      }}
    >
      Mostrar implantação
    </Button>
  );
}
