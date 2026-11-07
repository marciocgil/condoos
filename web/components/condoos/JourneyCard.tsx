"use client";

import { CheckCircle2, Circle, Clock, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CapabilityReadinessList } from "@/components/condoos/CapabilityReadiness";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { send } from "@/lib/client";
import type { Launch, LaunchGoal } from "@/lib/types";

const GOALS: { key: LaunchGoal; label: string }[] = [
  { key: "economizar", label: "Economizar dinheiro" },
  { key: "pendencias", label: "Organizar pendências" },
  { key: "fornecedores", label: "Controlar fornecedores" },
  { key: "panorama", label: "Ver um panorama" },
];

/** Launch journey card (LB-005, D89) on the síndico's "Hoje": what was done, the next steps
 * (one primary), the milestones and what each capability needs. Milestones are facts from
 * the data; nothing here turns anything on. */
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

      {launch.next_steps.length > 0 && (
        <div className="mt-4">
          <h3 className="text-[13px] font-medium text-fg-2">Próximos passos</h3>
          <ul className="mt-2 space-y-3">
            {launch.next_steps.map((s) => (
              <li key={s.key} data-testid={`step-${s.key}`}>
                <p className="text-sm">{s.why}</p>
                <p className="text-[13px] text-fg-2">Desbloqueia: {s.unlocks}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Link
                    href={`/condominio/${condominiumId}/${s.href}`}
                    className={buttonClass(s.primary ? "primary" : "secondary", "sm")}
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
        </div>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-[13px] text-fg-2 hover:text-fg">
          Marcos e o que cada função precisa
        </summary>
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
