import { Download } from "lucide-react";
import Link from "next/link";

import { AuditToolbar } from "@/components/audit/AuditToolbar";
import { ControlStatusBadge } from "@/components/audit/ControlStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { auditCondos, lastMonth } from "@/lib/audit";
import { formatDateTime } from "@/lib/format";
import type { ControlStatusCode, Me } from "@/lib/types";

type History = {
  months: {
    competencia: string;
    auditado: boolean;
    aprovado_pelo_sindico: boolean;
    contagem: Record<string, number>;
  }[];
  controls: {
    id: string;
    name: string;
    pillar: string;
    statuses: (ControlStatusCode | null)[];
    streak: number;
  }[];
  trend: {
    validados?: number;
    divergentes?: number;
    pendentes?: number;
    de?: string;
    para?: string;
  };
};
type Operations = {
  runs: {
    id: string;
    competencia: string | null;
    number: number;
    trigger: string;
    started_at: string;
    novos: number | null;
    mudancas: string[];
  }[];
  sla: Record<string, number>;
  waiting: { id: string; competencia: string; submitted_at: string; overdue: boolean }[];
  reprocess_paused: boolean;
};
type Links = {
  operate_total: number;
  operate: {
    issue_id: string;
    control_id: string;
    title: string;
    sla_label: string;
    case: { id: string; title: string; status: string } | null;
  }[];
  optimize: {
    opportunities: { id: string; number: string; title: string; status: string }[];
    candidates: { contract_id: string; object: string }[];
  };
};

const TRIGGER: Record<string, string> = {
  manual: "pessoa",
  evento: "evento (documento, extrato, contrato)",
  revalidacao: "revalidação",
};
const SHORT: Record<ControlStatusCode, string> = {
  VALIDADO: "V",
  COM_RESSALVA: "R",
  PENDENTE: "P",
  DIVERGENTE: "D",
  NAO_AVALIADO: "—",
  NAO_APLICAVEL: "NA",
};
const CELL: Record<ControlStatusCode, string> = {
  VALIDADO: "text-success",
  COM_RESSALVA: "text-warning",
  PENDENTE: "text-info",
  DIVERGENTE: "text-danger",
  NAO_AVALIADO: "text-muted",
  NAO_APLICAVEL: "text-muted",
};

function signed(n: number | undefined): string {
  if (n === undefined) return "—";
  return n > 0 ? `+${n}` : String(n);
}

/** Continuous operation (D125): the farol over 12 months, how runs were triggered, the SLA of
 * the pending items, the links with Operate and Optimize, and the export of the month. */
export default async function AuditHistoryPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; competencia?: string }>;
}) {
  const sp = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = auditCondos(me);
  if (condos.length === 0)
    return <EmptyState title="Sem acesso à auditoria">Seu papel não vê o histórico.</EmptyState>;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : condos[0]!.id;
  const competencia = /^\d{4}-\d{2}$/.test(sp.competencia ?? "") ? sp.competencia! : lastMonth();
  const base = `/condominiums/${selected}/audit`;
  const [history, ops, links] = await Promise.all([
    apiGet<History>(`${base}/history?ate=${competencia}&meses=12`),
    apiGet<Operations>(`${base}/operations`),
    apiGet<Links>(`${base}/links?competencia=${competencia}`),
  ]);
  const canExport =
    me.condominiums.find((c) => c.id === selected)?.permissions.includes("export") ?? false;
  return (
    <>
      <PageHeader
        title="Histórico e operação"
        subtitle="O farol mês a mês, como cada execução começou, o prazo das pendências e as ligações com Assuntos e Oportunidades."
        actions={
          canExport ? (
            <div className="flex gap-2">
              <a
                href={`/api${base}/export.pdf?competencia=${competencia}`}
                className={buttonClass("secondary", "sm")}
              >
                <Download size={14} aria-hidden /> PDF do mês
              </a>
              <a
                href={`/api${base}/export.xlsx?competencia=${competencia}`}
                className={buttonClass("secondary", "sm")}
              >
                <Download size={14} aria-hidden /> Planilha do mês
              </a>
            </div>
          ) : undefined
        }
      />
      <AuditToolbar
        pathname="/admin/audit/historico"
        condos={condos}
        selected={selected}
        competencia={competencia}
      />
      <Card className="mb-6">
        <CardTitle>Tendência</CardTitle>
        {history.trend.de ? (
          <p className="mt-1 text-sm" data-testid="trend">
            De {history.trend.de} para {history.trend.para}: validados{" "}
            {signed(history.trend.validados)}, divergentes {signed(history.trend.divergentes)},
            pendentes {signed(history.trend.pendentes)}.
          </p>
        ) : (
          <p className="mt-1 text-sm text-fg-2">É preciso ao menos dois meses auditados.</p>
        )}
        <div className="mt-3 overflow-x-auto">
          <table className="text-[12px]" data-testid="history-matrix">
            <thead>
              <tr className="text-fg-2">
                <th className="py-1 pr-3 text-left">Controle</th>
                {history.months.map((m) => (
                  <th key={m.competencia} className="px-1 py-1 text-center font-normal">
                    {m.competencia.slice(5)}/{m.competencia.slice(2, 4)}
                    {m.aprovado_pelo_sindico && <span className="block text-success">aprov.</span>}
                  </th>
                ))}
                <th className="px-2 py-1 text-left font-normal">Meses sem verde</th>
              </tr>
            </thead>
            <tbody>
              {history.controls.map((c) => (
                <tr key={c.id} className="border-t border-line">
                  <td className="py-1 pr-3 whitespace-nowrap">
                    <span className="font-mono text-fg-2">{c.id}</span> {c.name}
                  </td>
                  {c.statuses.map((st, i) => (
                    <td
                      key={i}
                      className={`px-1 py-1 text-center font-medium ${st ? CELL[st] : "text-muted"}`}
                      title={st ?? "não auditado"}
                    >
                      {st ? SHORT[st] : "·"}
                    </td>
                  ))}
                  <td className="px-2 py-1">{c.streak > 1 ? `${c.streak}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 flex flex-wrap gap-2 text-xs text-fg-2">
          Legenda:
          {(Object.keys(SHORT) as ControlStatusCode[]).map((s) => (
            <span key={s} className="inline-flex items-center gap-1">
              {SHORT[s]} = <ControlStatusBadge status={s} />
            </span>
          ))}
          · = mês não auditado
        </p>
      </Card>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardTitle>Execuções recentes</CardTitle>
          <p className="mt-1 text-xs text-fg-2">
            Depois que uma pessoa roda um mês, documentos, extratos, contratos e aprovações novos
            rodam aquele mês de novo sozinhos (só o que mudou é substituído).
            {ops.reprocess_paused && (
              <strong className="text-warning">
                {" "}
                O reprocessamento automático está pausado neste condomínio.
              </strong>
            )}
          </p>
          <ul className="mt-2 space-y-1 text-[13px]">
            {ops.runs.map((r) => (
              <li key={r.id}>
                {r.competencia} · execução {r.number} · {TRIGGER[r.trigger] ?? r.trigger} ·{" "}
                {formatDateTime(r.started_at)} · {r.novos ?? 0} resultado(s) novo(s)
                {r.mudancas.length > 0 && (
                  <span className="block text-fg-2">Mudou: {r.mudancas.join("; ")}</span>
                )}
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardTitle>Prazos (SLA)</CardTitle>
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            <Badge tone="neutral">Em dia: {ops.sla.em_dia ?? 0}</Badge>
            <Badge tone="warning">Atenção: {ops.sla.atencao ?? 0}</Badge>
            <Badge tone="danger">Escaladas: {ops.sla.escalada ?? 0}</Badge>
          </div>
          <p className="mt-2 text-xs text-fg-2">
            Pendência aberta no 2º mês fica em atenção; a partir do 3º, escalada. Farol enviado ao
            síndico há mais de 7 dias fica atrasado.
          </p>
          {ops.waiting.map((w) => (
            <p key={w.id} className="mt-2 text-sm">
              Farol de {w.competencia} aguardando o síndico desde {formatDateTime(w.submitted_at)}
              {w.overdue && (
                <>
                  {" "}
                  <Badge tone="danger">atrasado</Badge>
                </>
              )}
            </p>
          ))}
          <Link
            href={`/admin/audit/pendencias?condominio=${selected}`}
            className="mt-2 inline-block text-sm text-fg-2 underline-offset-2 hover:underline"
          >
            Abrir as pendências
          </Link>
        </Card>
        <Card>
          <CardTitle>Assuntos (Operate)</CardTitle>
          {links.operate_total > links.operate.length && (
            <p className="mt-1 text-xs text-fg-2">
              Mostrando {links.operate.length} de {links.operate_total}. Todas em{" "}
              <Link href={`/admin/audit/pendencias?condominio=${selected}`} className="underline">
                Pendências da auditoria
              </Link>
              .
            </p>
          )}
          {links.operate.length === 0 ? (
            <p className="mt-2 text-sm text-fg-2">
              Nenhuma pendência escalada ou com assunto aberto.
            </p>
          ) : (
            <ul className="mt-2 space-y-2 text-[13px]">
              {links.operate.map((o) => (
                <li key={o.issue_id}>
                  <span className="font-mono text-fg-2">{o.control_id}</span> {o.title}
                  <span className="block text-fg-2">
                    {o.sla_label} ·{" "}
                    {o.case ? (
                      <Link href={`/admin/assuntos/${selected}/${o.case.id}`} className="underline">
                        assunto {o.case.status}
                      </Link>
                    ) : (
                      "sem assunto: crie pelas pendências"
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardTitle>Oportunidades (Optimize)</CardTitle>
          {links.optimize.opportunities.length === 0 && links.optimize.candidates.length === 0 ? (
            <p className="mt-2 text-sm text-fg-2">
              Nenhum contrato apontado pela auditoria neste mês.
            </p>
          ) : (
            <ul className="mt-2 space-y-2 text-[13px]">
              {links.optimize.opportunities.map((o) => (
                <li key={o.id}>
                  {o.number} · {o.title} · {o.status}
                </li>
              ))}
              {links.optimize.candidates.map((c) => (
                <li key={c.contract_id}>
                  Contrato apontado nos controles de contrato, sem oportunidade: {c.object}
                  <span className="block text-fg-2">
                    Indício para a equipe avaliar; economia só é calculada e revisada no Optimize.
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
