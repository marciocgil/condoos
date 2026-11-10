import { Ban, Bot, CheckCircle2, Mail, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Catalog } from "@/lib/types";

const SECTIONS = [
  ["regras", "Regras de auditoria"],
  ["prompts", "Prompts da IA"],
  ["leitura", "Leitura e confiança"],
  ["verificacoes", "Verificações automáticas"],
  ["politica", "Política das ações"],
] as const;

const SEVERITY: Record<string, "danger" | "warning" | "neutral"> = {
  alta: "danger",
  media: "warning",
  baixa: "neutral",
};

const SEVERITY_LABEL: Record<string, string> = { alta: "alta", media: "média", baixa: "baixa" };

function params(p: Record<string, unknown>): string {
  const entries = Object.entries(p);
  if (!entries.length) return "sem parâmetros";
  return entries.map(([k, v]) => `${k} = ${JSON.stringify(v)}`).join(" · ");
}

function usd(v: string): string {
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "USD" });
}

/** "Regras e prompts" (D121): what runs in the CondoOS, read only. Changes go through the
 * code, with tests and review; this screen only shows them. */
export default async function RegrasPage() {
  const c = await apiGet<Catalog>("/catalog");
  return (
    <>
      <PageHeader
        title="Regras e prompts"
        subtitle="O que o CondoOS executa, em cada propósito. Só leitura: mudanças passam pelo código, com testes e revisão."
      />
      <nav aria-label="Seções" className="mb-6 flex flex-wrap gap-2 text-sm">
        {SECTIONS.map(([id, label]) => (
          <a
            key={id}
            href={`#${id}`}
            className="rounded-[var(--radius-control)] border border-line px-3 py-1 text-fg-2 hover:text-fg"
          >
            {label}
          </a>
        ))}
      </nav>

      <section id="regras" aria-labelledby="regras-t" className="mb-10 space-y-3">
        <h2 id="regras-t" className="text-lg font-semibold">
          Regras de auditoria ({c.rules.length})
        </h2>
        <p className="text-sm text-fg-2">
          Determinísticas: com os mesmos dados, os mesmos achados. A IA só entra onde está marcado.
        </p>
        {c.rules.map((r) => (
          <Card key={r.code} data-testid={`rule-${r.code}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[13px] text-fg-2">{r.code}</span>
              <h3 className="text-[15px] font-semibold">{r.name}</h3>
              <Badge tone={SEVERITY[r.severity] ?? "neutral"}>
                Gravidade {SEVERITY_LABEL[r.severity] ?? r.severity}
              </Badge>
              {r.ai_assisted && (
                <Badge tone="info" icon={<Sparkles size={12} />}>
                  Assistida por IA
                </Badge>
              )}
            </div>
            <p className="mt-1 text-sm">{r.description}</p>
            <p className="mt-2 text-[13px] text-fg-2">
              Padrão: {params(r.default_params)}
              {Object.entries(r.condo_params).map(([condo, p]) => (
                <span key={condo} className="block">
                  {condo}: {params(p)}
                </span>
              ))}
            </p>
            <p className="mt-1 text-[13px] text-muted">Achados no mês: {r.findings_this_month}</p>
          </Card>
        ))}
      </section>

      <section id="prompts" aria-labelledby="prompts-t" className="mb-10 space-y-3">
        <h2 id="prompts-t" className="text-lg font-semibold">
          Prompts da IA ({c.prompts.length} propósitos)
        </h2>
        <p className="text-sm text-fg-2">
          O texto exato enviado à IA em cada propósito. A versão é a impressão digital (SHA-256) do
          texto; cada chamada registra a versão usada.
        </p>
        {c.prompts.map((p) => (
          <Card key={p.code} data-testid={`prompt-${p.code}`}>
            <div className="flex flex-wrap items-center gap-2">
              <Bot size={16} aria-hidden className="text-fg-2" />
              <h3 className="text-[15px] font-semibold">{p.label}</h3>
              <span className="font-mono text-[12px] text-muted">{p.code}</span>
            </div>
            <p className="mt-1 text-[13px] text-fg-2">
              {p.where} · modelo {p.model} · arquivos {p.files.join(" + ")} · versão{" "}
              <span className="font-mono">{p.sha256.slice(0, 12)}</span>
            </p>
            <p className="mt-1 text-[13px] text-fg-2">
              No mês: {p.calls_this_month} chamadas · {usd(p.cost_usd_this_month)}
              {p.failures_this_month ? ` · ${p.failures_this_month} com falha` : ""}
            </p>
            {p.versions.length > 0 && (
              <ul className="mt-2 space-y-1 text-[13px]" aria-label="Versões usadas">
                {p.versions.map((v) => (
                  <li key={v.sha256} className="flex flex-wrap items-center gap-2">
                    <span className="font-mono">{v.sha256.slice(0, 12)}</span>
                    {v.current ? (
                      <Badge tone="success" icon={<CheckCircle2 size={12} />}>
                        Em vigor
                      </Badge>
                    ) : (
                      <Badge tone="neutral">Anterior</Badge>
                    )}
                    <span className="text-fg-2">
                      {v.calls} chamadas, de {formatDateTime(v.first_at)} a{" "}
                      {formatDateTime(v.last_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-fg-2 hover:text-fg">
                Ver o texto do prompt
              </summary>
              <pre className="mt-2 max-h-[480px] overflow-auto rounded-[var(--radius-control)] border border-line bg-bg-2 p-3 text-[12px] whitespace-pre-wrap">
                {p.text}
              </pre>
            </details>
          </Card>
        ))}
      </section>

      <section id="leitura" aria-labelledby="leitura-t" className="mb-10 space-y-3">
        <h2 id="leitura-t" className="text-lg font-semibold">
          Leitura e confiança
        </h2>
        <Card>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {c.reading.rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardTitle>Campos por tipo de documento</CardTitle>
          <dl className="mt-2 space-y-3 text-sm">
            {c.reading.types.map((t) => (
              <div key={t.code}>
                <dt className="font-medium">{t.label}</dt>
                <dd className="text-[13px] text-fg-2">
                  Obrigatórios: {t.required.join(", ")}
                  {t.optional.length ? ` · Opcionais: ${t.optional.join(", ")}` : ""}
                </dd>
              </div>
            ))}
            <div>
              <dt className="font-medium">Guardados só como texto (pesquisáveis no chat)</dt>
              <dd className="text-[13px] text-fg-2">{c.reading.text_only.join(", ")}</dd>
            </div>
            <div>
              <dt className="font-medium">Recusados</dt>
              <dd className="text-[13px] text-fg-2">{c.reading.refused.join(" ")}</dd>
            </div>
          </dl>
        </Card>
      </section>

      <section id="verificacoes" aria-labelledby="verificacoes-t" className="mb-10 space-y-3">
        <h2 id="verificacoes-t" className="text-lg font-semibold">
          Verificações automáticas
        </h2>
        {c.detectors.length === 0 ? (
          <EmptyState title="Nenhuma verificação">Nada cadastrado.</EmptyState>
        ) : (
          <Card>
            <ul className="space-y-2 text-sm">
              {c.detectors.map((d) => (
                <li key={d.code}>
                  <span className="font-mono text-[12px] text-fg-2">{d.code}</span> · {d.group}
                  <span className="block">{d.what}</span>
                  <span className="text-[13px] text-muted">Abertos agora: {d.open}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      <section id="politica" aria-labelledby="politica-t" className="mb-10 space-y-3">
        <h2 id="politica-t" className="text-lg font-semibold">
          Política das ações (versão {c.policy.version})
        </h2>
        <Card>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {c.policy.rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <ul className="mt-4 space-y-2 text-sm">
            {c.policy.actions.map((a) => (
              <li key={a.code} className="flex flex-wrap items-center gap-2">
                <span>{a.label}</span>
                <span className="font-mono text-[12px] text-muted">
                  {a.code} · {a.level}
                </span>
                {a.always_denied ? (
                  <Badge tone="danger" icon={<Ban size={12} />}>
                    Negada sempre
                  </Badge>
                ) : (
                  <Badge tone="neutral">Com aprovação do síndico</Badge>
                )}
                {a.zero_cost_only && <Badge tone="neutral">Só sem custo</Badge>}
                {a.sends_email && (
                  <Badge tone="info" icon={<Mail size={12} />}>
                    Envia e-mail
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </section>
    </>
  );
}
