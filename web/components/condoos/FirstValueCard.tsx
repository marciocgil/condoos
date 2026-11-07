import {
  AlertTriangle,
  CheckCircle2,
  FileQuestion,
  GitCompare,
  Info,
  Loader2,
  Sparkles,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { formatBRL, formatDate } from "@/lib/format";
import type { FirstValue, FirstValueField } from "@/lib/types";

const MONTH_NAMES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

const SOURCE_LABEL: Record<string, string> = {
  xml: "arquivo fiscal",
  texto: "texto do documento",
  ia: "leitura por IA",
  pessoa: "confirmado por pessoa",
  regra: "cláusula do texto",
};

function formatCnpj(digits: string): string {
  const d = digits.replace(/\D/g, "");
  if (d.length !== 14) return digits;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

function show(f: FirstValueField): string {
  const v = f.value;
  if (v === null) return "";
  if (Array.isArray(v)) return v.join("; ");
  if (f.kind === "money") return formatBRL(v);
  if (f.kind === "date") return formatDate(String(v));
  if (f.kind === "cnpj") return formatCnpj(String(v));
  if (f.name === "mes_base_reajuste") return MONTH_NAMES[Number(v) - 1] ?? String(v);
  return String(v);
}

function StateBadge({ state }: { state: FirstValueField["state"] }) {
  if (state === "lido")
    return (
      <Badge tone="success" icon={<CheckCircle2 size={12} />}>
        Lido no documento
      </Badge>
    );
  if (state === "conflitante")
    return (
      <Badge tone="danger" icon={<GitCompare size={12} />}>
        Conflita com o cadastro
      </Badge>
    );
  if (state === "inferido")
    return (
      <Badge tone="info" icon={<Sparkles size={12} />}>
        Inferido
      </Badge>
    );
  if (state === "a_confirmar")
    return (
      <Badge tone="warning" icon={<AlertTriangle size={12} />}>
        A confirmar
      </Badge>
    );
  return (
    <Badge tone="neutral" icon={<FileQuestion size={12} />}>
      Não encontrado
    </Badge>
  );
}

/** What the CondoOS read in a contract (LB-006, F01). Every value comes from the extraction
 * and carries its state; a doubtful value is labelled "a confirmar", never shown as a fact. */
export function FirstValueCard({ card }: { card: FirstValue }) {
  if (card.status === "lendo") {
    return (
      <Card aria-label="Leitura do documento" aria-busy="true">
        <p className="flex items-center gap-2 text-sm text-fg-2" role="status">
          <Loader2 size={16} aria-hidden className="animate-spin" />
          {card.message} <span className="text-muted">({card.filename})</span>
        </p>
      </Card>
    );
  }
  if (
    card.status === "falhou" ||
    card.status === "nao_contrato" ||
    card.status === "nao_identificado"
  ) {
    const failed = card.status === "falhou";
    return (
      <Card aria-label="Leitura do documento">
        <p
          className={`flex items-start gap-2 text-sm ${failed ? "text-danger" : "text-fg-2"}`}
          role="status"
        >
          {failed ? (
            <XCircle size={16} aria-hidden className="mt-0.5 shrink-0" />
          ) : (
            <Info size={16} aria-hidden className="mt-0.5 shrink-0" />
          )}
          {card.message}
        </p>
      </Card>
    );
  }
  return (
    <Card aria-label="Leitura do contrato" data-testid="first-value">
      <CardTitle>Leitura do contrato</CardTitle>
      <p className="text-sm text-fg-2" role="status">
        {card.message}
      </p>
      <dl className="mt-4 divide-y divide-line">
        {card.fields.map((f) => (
          <div key={f.name} className="py-3" data-field={f.name} data-state={f.state}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-[13px] text-fg-2">{f.label}</dt>
              <StateBadge state={f.state} />
            </div>
            {f.state === "nao_encontrado" ? (
              <dd className="mt-1 text-sm text-muted">Não encontrei isto neste documento.</dd>
            ) : (
              <dd className="mt-1">
                <span className="tabular font-medium">
                  {f.state === "a_confirmar"
                    ? `Li ${show(f)}, mas um revisor vai conferir`
                    : f.state === "conflitante"
                      ? `O documento diz ${show(f)}, mas o cadastro tem outro valor`
                      : f.state === "inferido"
                        ? `${show(f)} (o texto não mostra este valor; confira)`
                        : show(f)}
                </span>
                {(f.excerpt || f.source) && (
                  <span className="mt-1 block text-[13px] text-muted">
                    {f.source ? (SOURCE_LABEL[f.source] ?? f.source) : null}
                    {f.page ? ` · página ${f.page}` : null}
                    {f.excerpt ? (
                      <q className="mt-0.5 block text-fg-2 not-italic">{f.excerpt}</q>
                    ) : null}
                  </span>
                )}
              </dd>
            )}
          </div>
        ))}
      </dl>
      <div className="mt-4 rounded-[var(--radius-button)] border border-line bg-elevated p-3">
        <p className="text-[13px] font-medium">O que esta leitura não cobre</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px] text-fg-2">
          {card.limits.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>
      {card.next_step && (
        <p className="mt-3 text-sm">
          <span className="text-fg-2">Próximo passo: </span>
          {card.next_step.title}
        </p>
      )}
    </Card>
  );
}
