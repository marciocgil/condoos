"use client";

import { CheckCircle2, Circle, Clock, EyeOff, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FirstContractUpload } from "@/components/condoos/FirstContractUpload";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { send } from "@/lib/client";
import type { Launch, LaunchGoal, LaunchStep } from "@/lib/types";

const GOALS: { value: LaunchGoal; label: string }[] = [
  { value: "economizar", label: "Economizar dinheiro" },
  { value: "pendencias", label: "Organizar pendências" },
  { value: "fornecedores", label: "Controlar fornecedores" },
  { value: "panorama", label: "Ver um panorama" },
];

const SCREEN_PATH: Record<LaunchStep["screen"], string> = {
  enviar: "enviar",
  contratos: "contratos",
  assuntos: "assuntos",
};

/** The Launch journey card on "Hoje" (LB-005, D91). Everything shown comes from
 * ``GET /launch``: milestones and steps are derived from the data, so another device shows
 * exactly the same card. Only the síndico and the CondoOS admin change the preferences. */
export function JourneyCard({
  condominiumId,
  launch,
  canManage,
}: {
  condominiumId: string;
  launch: Launch;
  canManage: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Once a contract was sent from this card, its reading stays on screen even when the next
  // step changes (the page refreshes as the journey moves on).
  const [sent, setSent] = useState(false);
  const base = `/condominiums/${condominiumId}/launch`;

  async function act(method: "PUT" | "POST", path: string, body: unknown, done?: string) {
    setBusy(true);
    setError(null);
    const r = await send(method, `${base}${path}`, body);
    setBusy(false);
    if (!r.ok) setError(r.error);
    else {
      if (done) setNotice(done);
      router.refresh();
    }
  }

  if (launch.dismissed) {
    return canManage ? (
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          disabled={busy}
          onClick={() => void act("POST", "/dismiss", { dismissed: false })}
        >
          Mostrar a jornada
        </Button>
      </div>
    ) : null;
  }

  const doneCount = launch.milestones.filter((m) => m.done).length;
  const next = launch.milestones.find((m) => !m.done);
  const [primary, ...secondary] = launch.steps;

  return (
    <Card tone="highlight" aria-labelledby="journey-title" data-testid="journey-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 text-[13px] text-fg-2">
            <Sparkles size={14} aria-hidden /> Sua implantação · {doneCount} de{" "}
            {launch.milestones.length} marcos
          </p>
          <h2 id="journey-title" className="mt-1 text-[17px] leading-snug font-semibold">
            {next ? `Próximo marco: ${next.name}` : "Implantação concluída"}
          </h2>
        </div>
        {canManage && (
          <Button
            variant="ghost"
            size="sm"
            aria-label="Ocultar a jornada"
            icon={<EyeOff size={14} aria-hidden />}
            disabled={busy}
            onClick={() => void act("POST", "/dismiss", { dismissed: true })}
          >
            Ocultar
          </Button>
        )}
      </div>

      {!launch.goal_answered && canManage && (
        <div className="mt-4" role="group" aria-labelledby="goal-q">
          <p id="goal-q" className="text-sm">
            <strong>Sou seu assessor CondoOS.</strong> Vou conhecer seu condomínio, organizar as
            informações e começar a trabalhar. Você não precisa cadastrar tudo sozinho. Por onde
            quer começar?
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {GOALS.map((g) => (
              <button
                key={g.value}
                type="button"
                disabled={busy}
                className={`${buttonClass("secondary")} h-auto min-h-10 py-2 whitespace-normal`}
                onClick={() => void act("PUT", "/goal", { goal: g.value })}
              >
                {g.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            disabled={busy}
            className="mt-2 text-[13px] text-fg-2 underline-offset-2 hover:text-fg hover:underline"
            onClick={() => void act("PUT", "/goal", { goal: null })}
          >
            Prefiro decidir depois
          </button>
        </div>
      )}

      {launch.done_for_you.length > 0 && (
        <div className="mt-4">
          <p className="text-[13px] font-medium text-fg-2">O que já fiz por você</p>
          <ul className="mt-1 space-y-1 text-sm">
            {launch.done_for_you.slice(0, 3).map((item) => (
              <li key={item.key} className="flex items-center gap-2">
                <CheckCircle2 size={14} aria-hidden className="shrink-0 text-success" />
                {item.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      {primary && (
        <div className="mt-4 space-y-2" aria-label="Próximo passo">
          <p className="font-medium">{primary.title}</p>
          <p className="text-[13px] text-fg-2">
            {primary.why} <span className="text-muted">Ativa: {primary.unlocks}.</span>
          </p>
          {primary.key !== "enviar_contrato" && (
            <Link
              href={`/condominio/${condominiumId}/${SCREEN_PATH[primary.screen]}`}
              className={`${buttonClass(primary.key === "confirmar_contrato" ? "secondary" : "primary")} w-full`}
            >
              {primary.action_label}
            </Link>
          )}
          {canManage && (
            <Button
              variant="ghost"
              size="sm"
              icon={<Clock size={14} aria-hidden />}
              disabled={busy}
              onClick={() =>
                void act(
                  "POST",
                  "/postpone",
                  { step: primary.key },
                  "Tudo bem. Deixo isto guardado em Próximos passos.",
                )
              }
            >
              Fazer depois
            </Button>
          )}
        </div>
      )}

      {(primary?.key === "enviar_contrato" || sent) && (
        <div className="mt-2">
          <FirstContractUpload
            condominiumId={condominiumId}
            primary={primary?.key === "enviar_contrato"}
            onSent={() => setSent(true)}
          />
        </div>
      )}

      {secondary.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
          {secondary.map((s) => (
            <li key={s.key}>
              <Link
                href={`/condominio/${condominiumId}/${SCREEN_PATH[s.screen]}`}
                className="text-fg-2 hover:text-fg"
              >
                {s.title}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <details className="mt-3 border-t border-line pt-3 text-sm">
        <summary className="cursor-pointer text-[13px] text-fg-2">Ver os marcos</summary>
        <ol className="mt-2 space-y-2">
          {launch.milestones.map((m) => (
            <li key={m.key} className="flex items-start gap-2">
              {m.done ? (
                <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0 text-success" />
              ) : (
                <Circle size={16} aria-hidden className="mt-0.5 shrink-0 text-muted" />
              )}
              <span>
                {m.name}
                <span className="block text-[13px] text-muted">
                  {m.done ? "Concluído" : (m.missing[0] ?? "Pendente")}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </details>

      {notice && (
        <p role="status" className="mt-2 text-sm text-fg-2">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
