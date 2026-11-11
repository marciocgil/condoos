import { Bot, Cpu, PauseCircle } from "lucide-react";
import Link from "next/link";

import { AgentTabs } from "@/components/audit/AgentTabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import type { AgentSummary } from "@/lib/types";

const MODE: Record<string, string> = {
  deterministico: "Determinístico (código)",
  ia_e_deterministico: "IA onde interpreta + código",
  inativo: "Ainda não ativado",
};

/** Agentes & Prompts (D122): A0–A9 with the version of the prompt in force. */
export default async function AgentsPage() {
  const data = await apiGet<{ agents: AgentSummary[]; can_manage: boolean; safety_rule: string }>(
    "/audit/agents",
  );
  return (
    <>
      <PageHeader
        title="Agentes & Prompts"
        subtitle="Os dez papéis do CondoOS Audit, com o texto integral e versionado de cada prompt e a versão usada em cada execução."
      />
      <AgentTabs active="agentes" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {data.agents.map((a) => (
          <Card key={a.id} data-testid={`agent-${a.id}`}>
            <div className="flex flex-wrap items-center gap-2">
              {a.mode === "inativo" ? (
                <PauseCircle size={16} aria-hidden />
              ) : a.mode === "deterministico" ? (
                <Cpu size={16} aria-hidden />
              ) : (
                <Bot size={16} aria-hidden />
              )}
              <Link
                href={`/admin/audit/agentes/${a.id}`}
                className="text-[15px] font-semibold hover:underline"
              >
                {a.id} — {a.name}
              </Link>
              <Badge tone={a.active ? "success" : "neutral"}>
                {a.active ? "Ativo" : `Inativo (ciclo ${a.cycle})`}
              </Badge>
            </div>
            <p className="mt-1 text-sm">{a.purpose}</p>
            <p className="mt-1 text-[13px] text-fg-2">
              {a.stage} · {MODE[a.mode] ?? a.mode} · prompt v{a.active_version ?? "—"}{" "}
              <span className="font-mono">{a.active_sha256?.slice(0, 12)}</span>
              {a.open_drafts ? ` · ${a.open_drafts} rascunho(s) em andamento` : ""}
            </p>
          </Card>
        ))}
      </div>
      <Card className="mt-6">
        <p className="text-sm font-medium">
          Regra de segurança da aplicação (fixa, não editável, enviada com todo prompt)
        </p>
        <p className="mt-1 text-sm text-fg-2">{data.safety_rule}</p>
      </Card>
    </>
  );
}
