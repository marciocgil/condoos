import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { AgentTabs } from "@/components/audit/AgentTabs";
import { CopyButton, PromptGovernance } from "@/components/audit/PromptGovernance";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatMonthTitle } from "@/lib/format";
import type { AgentDetail } from "@/lib/types";

const STATUS: Record<string, [BadgeTone, string]> = {
  ACTIVE: ["success", "Ativa"],
  DRAFT: ["neutral", "Rascunho"],
  IN_REVIEW: ["warning", "Em revisão"],
  ARCHIVED: ["neutral", "Arquivada"],
};

/** One agent: what it does, the full prompt in force (with the boundaries of what the
 * application controls), every version, comparison, governance and the runs that used it. */
export default async function AgentPage({
  params,
  searchParams,
}: {
  params: Promise<{ agentId: string }>;
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { agentId } = await params;
  const sp = await searchParams;
  const agent = await apiGet<AgentDetail>(`/audit/agents/${agentId}`);
  const active = agent.versions.find((v) => v.status === "ACTIVE");
  const numbers = agent.versions.map((v) => v.version).sort((x, y) => x - y);
  const b = Number(sp.b ?? active?.version ?? numbers.at(-1));
  const a = Number(
    sp.a ?? numbers.filter((n) => n < b).at(-1) ?? numbers.find((n) => n !== b) ?? b,
  );
  const diff =
    a !== b
      ? await apiGet<{ lines: { kind: string; text: string }[] }>(
          `/audit/agents/${agentId}/diff?a=${a}&b=${b}`,
        )
      : null;
  return (
    <>
      <Link
        href="/admin/audit/agentes"
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Agentes & Prompts
      </Link>
      <PageHeader title={`${agent.id} — ${agent.name}`} subtitle={agent.purpose} />
      <AgentTabs active="agentes" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Card data-testid="active-prompt">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>Prompt em vigor{active ? ` · versão ${active.version}` : ""}</CardTitle>
              {active && <CopyButton text={active.text} />}
            </div>
            {active ? (
              <>
                <p className="mt-1 text-xs text-fg-2">
                  SHA-256 <span className="font-mono">{active.sha256}</span> ·{" "}
                  {active.author ?? "—"} · ativada{" "}
                  {active.activated_at ? formatDateTime(active.activated_at) : "—"} · origem{" "}
                  {active.source} · modelo {active.model_role}
                </p>
                <p className="mt-3 text-xs font-semibold text-fg-2">{agent.boundaries.agent}</p>
                <pre
                  className="mt-1 rounded-[var(--radius-control)] border border-line bg-bg-2 p-3 text-[13px] whitespace-pre-wrap"
                  data-testid="prompt-text"
                >
                  {active.text}
                </pre>
                <p className="mt-3 text-xs font-semibold text-fg-2">{agent.boundaries.safety}</p>
                <pre className="mt-1 rounded-[var(--radius-control)] border border-line bg-bg-2 p-3 text-[13px] whitespace-pre-wrap text-fg-2">
                  {agent.boundaries.safety_rule}
                </pre>
                <p className="mt-3 text-xs font-semibold text-fg-2">{agent.boundaries.task}</p>
                <p className="mt-1 text-[13px] text-fg-2">
                  Escrita pela aplicação em cada chamada (o pedido e o formato da resposta) e
                  enviada com os dados entre delimitadores. Instruções internas do provedor do
                  modelo não são controladas pelo produto e não aparecem aqui. Nenhuma credencial é
                  colocada no prompt.
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-fg-2">Sem versão ativa.</p>
            )}
          </Card>
          <Card>
            <CardTitle>Comparar versões</CardTitle>
            <form
              className="mt-2 flex flex-wrap items-end gap-2 text-sm"
              action={`/admin/audit/agentes/${agentId}`}
            >
              <label>
                De{" "}
                <select
                  name="a"
                  defaultValue={a}
                  className="ml-1 rounded border border-control bg-bg-2 px-2 py-1"
                >
                  {numbers.map((n) => (
                    <option key={n} value={n}>
                      v{n}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                para{" "}
                <select
                  name="b"
                  defaultValue={b}
                  className="ml-1 rounded border border-control bg-bg-2 px-2 py-1"
                >
                  {numbers.map((n) => (
                    <option key={n} value={n}>
                      v{n}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" className="rounded border border-control px-3 py-1">
                Comparar
              </button>
            </form>
            {diff ? (
              <div className="mt-3 space-y-1 text-[13px]" data-testid="prompt-diff">
                {diff.lines.map((l, i) => (
                  <p
                    key={i}
                    className={
                      l.kind === "incluida"
                        ? "border-l-2 border-success pl-2"
                        : l.kind === "removida"
                          ? "border-l-2 border-danger pl-2 line-through text-fg-2"
                          : "pl-2.5 text-fg-2"
                    }
                  >
                    {l.kind === "incluida" ? "+ " : l.kind === "removida" ? "− " : ""}
                    {l.text}
                  </p>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-fg-2">
                Só existe uma versão, ou escolha duas diferentes.
              </p>
            )}
          </Card>
          <Card>
            <CardTitle>Gestão de versões</CardTitle>
            <div className="mt-2">
              <PromptGovernance
                agentId={agent.id}
                versions={agent.versions}
                canManage={agent.can_manage}
                canApprove={agent.can_approve}
              />
            </div>
          </Card>
          <Card>
            <CardTitle>Execuções ({agent.runs.length})</CardTitle>
            {agent.runs.length === 0 ? (
              <p className="mt-2 text-sm text-fg-2">Nenhuma execução ainda.</p>
            ) : (
              <table className="mt-2 w-full text-[13px]">
                <thead className="text-left text-fg-2">
                  <tr>
                    <th className="py-1 pr-2">Quando</th>
                    <th className="py-1 pr-2">Condomínio · mês</th>
                    <th className="py-1 pr-2">Versão</th>
                    <th className="py-1 pr-2">IA</th>
                    <th className="py-1">Prompt montado (hash)</th>
                  </tr>
                </thead>
                <tbody>
                  {agent.runs.map((r) => (
                    <tr key={`${r.run_id}-${r.at}`} className="border-t border-line">
                      <td className="py-1 pr-2 whitespace-nowrap">{formatDateTime(r.at)}</td>
                      <td className="py-1 pr-2">
                        {r.condominium} · {formatMonthTitle(`${r.competencia}-01`)} · execução{" "}
                        {r.run_number}
                      </td>
                      <td className="py-1 pr-2">v{r.prompt_version ?? "—"}</td>
                      <td className="py-1 pr-2">
                        {r.llm_invoked ? (r.model ?? "sim") : "não chamada"}
                      </td>
                      <td className="py-1 font-mono">
                        {r.runtime_prompt_sha256?.slice(0, 16) ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
        <aside className="space-y-6">
          <Card>
            <CardTitle>Ficha do agente</CardTitle>
            <dl className="mt-2 space-y-2 text-sm">
              {[
                ["Etapa", agent.stage],
                ["Depende de", agent.depends_on.join(", ") || "—"],
                ["Ferramentas", agent.tools.join(", ")],
                ["Entradas", agent.inputs],
                ["Saídas", agent.outputs],
                ["Limites de autonomia", agent.limits],
                ["Responsável", agent.owner],
                ["Ativação", agent.active ? "Ativo" : `Inativo até o ciclo ${agent.cycle}`],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-fg-2">{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card>
            <CardTitle>Versões</CardTitle>
            <ul className="mt-2 space-y-2 text-sm">
              {agent.versions.map((v) => {
                const [tone, label] = STATUS[v.status] ?? ["neutral", v.status];
                return (
                  <li key={v.id}>
                    <span className="font-medium">v{v.version}</span>{" "}
                    <Badge tone={tone}>{label}</Badge>
                    <span className="block text-xs text-fg-2">
                      {v.author ?? "—"} · {formatDateTime(v.created_at)} ·{" "}
                      <span className="font-mono">{v.sha256.slice(0, 12)}</span>
                    </span>
                    <span className="block text-xs text-fg-2">{v.change_note}</span>
                  </li>
                );
              })}
            </ul>
          </Card>
          <Card>
            <CardTitle>Histórico</CardTitle>
            <ul className="mt-2 space-y-1 text-xs text-fg-2">
              {agent.events.map((e, i) => (
                <li key={i}>
                  {formatDateTime(e.at)} · v{e.version} · {e.kind} · {e.user ?? "sistema"}
                </li>
              ))}
            </ul>
            {agent.tests.length > 0 && (
              <>
                <p className="mt-3 text-sm font-medium">Testes no sandbox</p>
                <ul className="mt-1 space-y-1 text-xs text-fg-2">
                  {agent.tests.map((t, i) => (
                    <li key={i}>
                      {formatDateTime(t.at)} · v{t.version} · {t.passed ? "passou" : "falhou"}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        </aside>
      </div>
    </>
  );
}
