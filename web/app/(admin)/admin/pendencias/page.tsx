import { CheckCircle2, Clock, FileQuestion, FileSearch, FileWarning, Upload } from "lucide-react";
import Link from "next/link";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { OneOffApproval } from "@/components/condoos/OneOffApproval";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { KpiCard } from "@/components/ui/KpiCard";
import { apiGet } from "@/lib/api";
import { competenceParam, formatBRL, formatDate, formatMonth } from "@/lib/format";
import type { PendingCockpit, PendingContract, Portfolio } from "@/lib/types";

const BILLING: Record<
  PendingContract["status"],
  { label: string; tone: BadgeTone; icon: React.ReactNode }
> = {
  faturado: { label: "Faturado", tone: "success", icon: <CheckCircle2 size={12} /> },
  sem_nf: { label: "Cobrado sem NF", tone: "warning", icon: <FileWarning size={12} /> },
  sem_faturamento: { label: "Sem faturamento", tone: "danger", icon: <FileQuestion size={12} /> },
  aguardando: { label: "Aguardando NF", tone: "neutral", icon: <Clock size={12} /> },
  em_conferencia: {
    label: "Chegou, em conferência",
    tone: "info",
    icon: <FileSearch size={12} />,
  },
};

/** Cockpit of pending items (D70): contracts in force without the month's invoice and
 * one-off services without an approval document. */
export default async function PendenciasPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; mes?: string }>;
}) {
  const sp = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const params = new URLSearchParams();
  if (sp.mes && /^\d{4}-\d{2}$/.test(sp.mes)) params.set("month", sp.mes);
  if (selected) params.set("condominium_id", selected);
  const data = await apiGet<PendingCockpit>(`/portfolio/pending?${params.toString()}`);
  const month = competenceParam(data.month);
  const all = data.condominiums;
  const noInvoice = all
    .flatMap((c) => c.contracts)
    .filter((c) => c.status === "sem_nf" || c.status === "sem_faturamento");
  const unbacked = all.flatMap((c) => c.one_off).filter((o) => o.pending);
  const billed = all.flatMap((c) => c.contracts).filter((c) => c.status === "faturado").length;
  const expected = all.flatMap((c) => c.contracts).length;
  const monthHref = (m: string) => {
    const q = new URLSearchParams({ mes: competenceParam(m) });
    if (selected) q.set("condominio", selected);
    return `/admin/pendencias?${q.toString()}`;
  };

  return (
    <>
      <PageHeader
        title="Pendências"
        subtitle={`Faturamento dos contratos e aprovação dos serviços avulsos · ${formatMonth(data.month)}`}
      />
      <CondoFilter
        pathname="/admin/pendencias"
        condos={condos}
        selected={selected}
        extra={{ mes: month }}
      />
      <nav aria-label="Mês" className="mb-6 flex flex-wrap gap-2">
        {data.months.map((m) => {
          const active = m.month === data.month;
          return (
            <Link
              key={m.month}
              href={monthHref(m.month)}
              aria-current={active ? "page" : undefined}
              className={cx(
                "transition-ui inline-flex h-8 items-center gap-2 rounded-full border px-3 text-[13px]",
                active
                  ? "border-accent bg-accent/10 font-medium text-fg"
                  : "border-control text-fg-2 hover:text-fg",
              )}
            >
              {formatMonth(m.month)}
              <span
                className={cx(
                  "rounded-full px-1.5 text-xs",
                  m.open ? "bg-warning/20 text-warning" : "text-muted",
                )}
              >
                {m.open}
              </span>
            </Link>
          );
        })}
      </nav>

      <section className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3" aria-label="Indicadores">
        <KpiCard
          label="Contratos faturados no mês"
          value={`${billed} de ${expected}`}
          context="contratos vigentes com NF esperada neste mês"
          icon={<CheckCircle2 size={18} />}
        />
        <KpiCard
          label="Faturamento pendente"
          value={noInvoice.length}
          context="contratos sem NF ou sem cobrança no mês"
          tone={noInvoice.length ? "attention" : "normal"}
          icon={<FileQuestion size={18} />}
        />
        <KpiCard
          label="Avulsos sem aprovação"
          value={unbacked.length}
          context={`${formatBRL(unbacked.reduce((s, o) => s + Number(o.amount), 0))} sem documento de aprovação`}
          tone={unbacked.length ? "attention" : "normal"}
          icon={<FileWarning size={18} />}
        />
      </section>

      {all.length === 0 && (
        <EmptyState title="Nenhum condomínio na carteira">
          Cadastre um condomínio na Carteira.
        </EmptyState>
      )}

      <div className="space-y-8">
        {all.map((c) => (
          <Card key={c.id}>
            <CardTitle
              action={
                <Link
                  href={`/admin/enviar?condominio=${c.id}`}
                  className={buttonClass("ghost", "sm")}
                >
                  <Upload size={14} aria-hidden /> Enviar NF ou aprovação
                </Link>
              }
            >
              {c.name}
              <span className="ml-2 text-[13px] font-normal text-fg-2">
                {c.open_count ? `${c.open_count} pendência(s)` : "sem pendências"}
              </span>
            </CardTitle>

            <h3 className="mt-2 mb-2 text-sm font-semibold">Faturamento dos contratos</h3>
            {c.contracts.length === 0 ? (
              <p className="text-[13px] text-muted">
                Nenhum contrato com faturamento esperado neste mês.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Faturamento dos contratos de {c.name}</caption>
                  <thead className="border-b border-line text-[12px] text-fg-2">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Fornecedor</th>
                      <th className="py-2 pr-3 text-right font-medium">Valor do contrato</th>
                      <th className="py-2 pr-3 font-medium">Situação</th>
                      <th className="py-2 font-medium">NF / cobrança</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {c.contracts.map((k) => (
                      <tr key={k.contract_id}>
                        <td className="py-2 pr-3">
                          <span className="block">{k.supplier}</span>
                          <span className="text-xs text-muted">{k.object}</span>
                        </td>
                        <td className="tabular py-2 pr-3 text-right">
                          {formatBRL(k.expected_value)}
                        </td>
                        <td className="py-2 pr-3">
                          <Badge tone={BILLING[k.status].tone} icon={BILLING[k.status].icon}>
                            {BILLING[k.status].label}
                          </Badge>
                        </td>
                        <td className="py-2 text-[13px] text-fg-2">
                          {k.invoice_number
                            ? `NF ${k.invoice_number} · ${formatBRL(k.billed_value ?? "0")}`
                            : k.billed_value
                              ? `Cobrança de ${formatBRL(k.billed_value)} sem NF`
                              : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h3 className="mt-6 mb-2 text-sm font-semibold">Serviços avulsos (sem contrato)</h3>
            {c.one_off.length === 0 ? (
              <p className="text-[13px] text-muted">Nenhum serviço avulso neste mês.</p>
            ) : (
              <ul className="divide-y divide-line">
                {c.one_off.map((o) => (
                  <li
                    key={o.expense_id}
                    className="flex flex-wrap items-start justify-between gap-3 py-3 text-sm"
                  >
                    <span className="min-w-0">
                      <span className="block">{o.description}</span>
                      <span className="text-xs text-muted">
                        {o.supplier ?? "Fornecedor não identificado"} · {formatDate(o.issue_date)}
                        {o.invoice_number && ` · NF ${o.invoice_number}`} · {formatBRL(o.amount)}
                      </span>
                      {o.approvals.map((a) => (
                        <span
                          key={a.id}
                          className="mt-1 flex items-center gap-1.5 text-xs text-success"
                        >
                          <CheckCircle2 size={12} aria-hidden />
                          Aprovado por {a.approved_by} em {formatDate(a.approved_at)}
                          {a.document && ` · ${a.document}`}
                        </span>
                      ))}
                    </span>
                    {o.pending ? (
                      <span className="flex flex-col items-end gap-2">
                        <Badge tone="warning" icon={<FileWarning size={12} />}>
                          Sem documento de aprovação
                        </Badge>
                        <OneOffApproval condominiumId={c.id} expenseId={o.expense_id} />
                      </span>
                    ) : (
                      <Badge tone="success" icon={<CheckCircle2 size={12} />}>
                        Aprovado
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </>
  );
}
