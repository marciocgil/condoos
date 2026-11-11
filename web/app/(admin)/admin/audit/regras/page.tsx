import { AgentTabs } from "@/components/audit/AgentTabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

type Catalog = {
  controls: {
    id: string;
    pillar: string;
    name: string;
    agents: string[];
    sources: string[];
    criteria: string[];
    inputs: string[];
    cycle: number;
    rule_version: string;
    parameters: Record<string, string>;
  }[];
  classification: {
    version: string;
    debits: { kind: string; pattern: string }[];
    credits: { kind: string; pattern: string }[];
  };
};

/** "Regras, não prompts": the deterministic rules behind each control. Calculations are code,
 * never a model's decision. */
export default async function RulesNotPromptsPage() {
  const c = await apiGet<Catalog>("/audit/controls-catalog");
  return (
    <>
      <PageHeader
        title="Agentes & Prompts"
        subtitle="Regras, não prompts: o que é cálculo determinístico em cada controle, com versão, fontes e critérios."
      />
      <AgentTabs active="regras" />
      <div className="space-y-3">
        {c.controls.map((x) => (
          <Card key={x.id} data-testid={`rule-${x.id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[13px] text-fg-2">{x.id}</span>
              <span className="font-medium">{x.name}</span>
              <Badge tone={x.cycle === 1 ? "success" : "neutral"}>
                {x.cycle === 1 ? `Regra v${x.rule_version}` : `Ciclo ${x.cycle}`}
              </Badge>
              <span className="text-xs text-fg-2">
                {x.pillar} · agentes {x.agents.join(", ")}
              </span>
            </div>
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm">
              {x.criteria.map((k) => (
                <li key={k}>{k}</li>
              ))}
            </ul>
            <p className="mt-2 text-[13px] text-fg-2">
              Fontes: {x.sources.join("; ")} · depende de: {x.inputs.join(", ")}
              {Object.keys(x.parameters).length
                ? ` · ${Object.entries(x.parameters)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(", ")}`
                : ""}
            </p>
          </Card>
        ))}
      </div>
      <Card className="mt-6">
        <CardTitle>Classificação de lançamentos ({c.classification.version})</CardTitle>
        <div className="mt-2 grid grid-cols-1 gap-4 text-[13px] md:grid-cols-2">
          {(["debits", "credits"] as const).map((k) => (
            <div key={k}>
              <p className="font-medium">{k === "debits" ? "Débitos" : "Créditos"}</p>
              <ul className="mt-1 space-y-1">
                {c.classification[k].map((r) => (
                  <li key={r.kind}>
                    {r.kind}: <span className="font-mono text-fg-2">{r.pattern}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[13px] text-fg-2">
          A primeira regra que casa vale. Débito ligado a uma despesa é sempre “pagamento de
          despesa”. PIX ou depósito sem identificação fica só como indício.
        </p>
      </Card>
    </>
  );
}
