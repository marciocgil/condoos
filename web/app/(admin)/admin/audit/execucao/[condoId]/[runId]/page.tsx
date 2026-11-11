import { Bot, ChevronLeft, Cpu } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatMonthTitle } from "@/lib/format";
import type { AuditRunDetail } from "@/lib/types";

const STAGE: Record<string, [BadgeTone, string]> = {
  concluida: ["success", "Concluída"],
  com_pendencias: ["warning", "Com pendências"],
  pulada: ["neutral", "Não ativada neste ciclo"],
  falhou: ["danger", "Falhou"],
  em_execucao: ["info", "Em execução"],
  aguardando: ["neutral", "Aguardando"],
};

/** One audit run: stages 1–8 and what each agent did, with the prompt version it used. */
export default async function RunPage({
  params,
}: {
  params: Promise<{ condoId: string; runId: string }>;
}) {
  const { condoId, runId } = await params;
  const run = await apiGet<AuditRunDetail>(`/condominiums/${condoId}/audit/runs/${runId}`);
  return (
    <>
      <Link
        href={`/admin/audit?condominio=${condoId}&competencia=${run.competencia}`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Farol
      </Link>
      <PageHeader
        title={`Execução ${run.number} · ${formatMonthTitle(`${run.competencia}-01`)}`}
        subtitle={`Iniciada ${formatDateTime(run.started_at)}${run.finished_at ? `, concluída ${formatDateTime(run.finished_at)}` : ""}. Motor ${String(run.summary.motor ?? "")}.`}
      />
      <ol className="mb-8 space-y-3" aria-label="Etapas">
        {run.stages.map((s) => {
          const [tone, label] = STAGE[s.status] ?? ["neutral", s.status];
          return (
            <li
              key={s.stage}
              className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
              data-testid={`stage-${s.stage}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[13px] text-fg-2">Etapa {s.stage}</span>
                <span className="font-medium">{s.name}</span>
                <Badge tone={tone}>{label}</Badge>
              </div>
              <pre className="mt-2 max-h-48 overflow-auto text-[12px] whitespace-pre-wrap text-fg-2">
                {JSON.stringify(s.detail, null, 2)}
              </pre>
            </li>
          );
        })}
      </ol>
      <h2 className="mb-3 text-lg font-semibold">Agentes nesta execução</h2>
      <div className="space-y-3">
        {run.agents.map((a) => (
          <Card key={a.agent_id} data-testid={`agent-run-${a.agent_id}`}>
            <div className="flex flex-wrap items-center gap-2">
              {a.llm_invoked ? <Bot size={16} aria-hidden /> : <Cpu size={16} aria-hidden />}
              <Link
                href={`/admin/audit/agentes/${a.agent_id}`}
                className="font-medium hover:underline"
              >
                {a.agent_id} — {a.name}
              </Link>
              <Badge tone="neutral">prompt v{a.prompt_version ?? "—"}</Badge>
              <Badge tone={a.llm_invoked ? "info" : "neutral"}>
                {a.llm_invoked ? `IA chamada (${a.model ?? ""})` : "IA não chamada"}
              </Badge>
              <span className="text-xs text-fg-2">{a.duration_ms} ms</span>
            </div>
            {a.runtime_prompt_sha256 && (
              <p className="mt-1 text-xs text-fg-2">
                Prompt efetivo desta chamada:{" "}
                <span className="font-mono">{a.runtime_prompt_sha256}</span>
              </p>
            )}
            {a.warnings.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-warning">
                {a.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            {a.unresolved.length > 0 && (
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-fg-2">
                  {a.unresolved.length} item(ns) não resolvido(s)
                </summary>
                <ul className="mt-1 list-disc pl-5 text-fg-2">
                  {a.unresolved.slice(0, 50).map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              </details>
            )}
            <details className="mt-2 text-sm">
              <summary className="cursor-pointer text-fg-2">Saída estruturada</summary>
              <pre className="mt-1 max-h-64 overflow-auto text-[12px] whitespace-pre-wrap">
                {JSON.stringify(a.output, null, 2)}
              </pre>
            </details>
          </Card>
        ))}
      </div>
    </>
  );
}
