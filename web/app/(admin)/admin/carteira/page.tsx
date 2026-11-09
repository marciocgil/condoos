import { AlertTriangle, CheckCircle2, Clock, Inbox, Plus, Send, Wallet } from "lucide-react";
import Link from "next/link";

import { ReportActions } from "@/components/condoos/ReportActions";
import { PageHeader } from "@/components/layout/PageHeader";
import { QueueList } from "@/components/QueueList";
import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { CardTitle } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { KpiCard } from "@/components/ui/KpiCard";
import { apiGet } from "@/lib/api";
import { competenceParam, formatBRLShort, formatMonth } from "@/lib/format";
import type { Me, Portfolio, PortfolioLaunchRow, PortfolioRow, QueueItem } from "@/lib/types";

// A journey with no new document or step for this many days is shown as stalled.
const STALLED_DAYS = 7;

function IdleCell({ row }: { row: PortfolioLaunchRow }) {
  if (row.days_idle === null)
    return (
      <Badge tone="neutral" icon={<Clock size={12} />}>
        Sem atividade
      </Badge>
    );
  if (row.days_idle >= STALLED_DAYS)
    return (
      <Badge tone="warning" icon={<AlertTriangle size={12} />}>
        Parada há {row.days_idle} dias
      </Badge>
    );
  return (
    <Badge tone="success" icon={<CheckCircle2 size={12} />}>
      {row.days_idle === 0 ? "Ativa hoje" : `Ativa há ${row.days_idle} dia(s)`}
    </Badge>
  );
}

function StatusCell({ row }: { row: PortfolioRow }) {
  if (row.status === "revisar")
    return (
      <Badge tone="warning" icon={<AlertTriangle size={12} />}>
        Revisar
      </Badge>
    );
  if (row.status === "enviado")
    return (
      <Badge tone="success" icon={<Send size={12} />}>
        Enviado
      </Badge>
    );
  return (
    <Badge tone="neutral" icon={<CheckCircle2 size={12} />}>
      Em dia
    </Badge>
  );
}

export default async function CarteiraPage() {
  const [p, queue, me, launch] = await Promise.all([
    apiGet<Portfolio>("/portfolio"),
    apiGet<QueueItem[]>("/queue"),
    apiGet<Me>("/me"),
    apiGet<PortfolioLaunchRow[]>("/portfolio/launch"),
  ]);
  const implementing = launch.filter((r) => r.milestones_done < r.milestones_total);
  // The manager registers in its company; a CondoOS admin registers a condominium that
  // contracts directly, without a management company (D73).
  const isManager =
    me.management_companies.some((c) => c.roles.includes("gerente")) ||
    me.platform_roles.includes("condoos_admin");
  const n = p.condominiums.length;
  return (
    <>
      <PageHeader
        title="Carteira"
        subtitle={`${n} ${n === 1 ? "condomínio" : "condomínios"}${p.latest_competence ? ` · ${formatMonth(p.latest_competence)}` : ""}`}
        actions={
          isManager ? (
            <Link href="/admin/condominios/novo" className={buttonClass("secondary", "sm")}>
              <Plus size={14} aria-hidden /> Novo condomínio
            </Link>
          ) : undefined
        }
      />
      <section className="grid grid-cols-1 gap-4 md:grid-cols-3" aria-label="Indicadores">
        <KpiCard
          label="Em risco na carteira"
          value={formatBRLShort(p.amount_at_risk)}
          context="achados abertos, ainda não decididos"
          icon={<Wallet size={18} />}
        />
        <KpiCard
          label="Achados abertos"
          value={p.open_findings}
          context={
            <>
              {`${p.serious} ${p.serious === 1 ? "grave" : "graves"} · `}
              <Link href="/admin/achados" className="underline hover:text-fg">
                ver achados
              </Link>
            </>
          }
          tone={p.serious > 0 ? "attention" : "normal"}
          icon={<AlertTriangle size={18} />}
        />
        <KpiCard
          label="Itens na fila de exceções"
          value={queue.length}
          context="correções, casamentos e validações"
          icon={<Inbox size={18} />}
        />
      </section>

      <div className="mt-8">
        <DataTable<PortfolioRow>
          caption="Condomínios da carteira"
          rows={p.condominiums}
          rowKey={(r) => r.id}
          rowHref={(r) => `/condominio/${r.id}/resumo`}
          columns={[
            { key: "name", header: "Condomínio", cell: (r) => r.name },
            {
              key: "risk",
              header: "Em risco",
              cell: (r) => formatBRLShort(r.amount_at_risk),
              align: "right",
            },
            { key: "open", header: "Achados", cell: (r) => r.open_findings, align: "right" },
            { key: "serious", header: "Graves", cell: (r) => r.serious, align: "right" },
            { key: "status", header: "Status", cell: (r) => <StatusCell row={r} /> },
            {
              key: "report",
              header: "Relatório do mês",
              cell: (r) =>
                p.latest_competence && r.has_competence ? (
                  <ReportActions
                    condominiumId={r.id}
                    month={competenceParam(p.latest_competence)}
                    sent={r.status === "enviado"}
                    canClose={r.can_close}
                  />
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </div>

      {implementing.length > 0 && (
        <section className="mt-8" aria-labelledby="implantacao-titulo">
          <CardTitle>
            <span id="implantacao-titulo">Implantações em andamento</span>
          </CardTitle>
          <DataTable<PortfolioLaunchRow>
            caption="Implantações em andamento"
            rows={implementing}
            rowKey={(r) => r.id}
            rowHref={(r) => `/admin/configuracoes?condominio=${r.id}`}
            columns={[
              { key: "name", header: "Condomínio", cell: (r) => r.name },
              {
                key: "milestones",
                header: "Marcos",
                cell: (r) => `${r.milestones_done} de ${r.milestones_total}`,
                align: "right",
              },
              { key: "next", header: "Próximo marco", cell: (r) => r.next_milestone ?? "—" },
              {
                key: "capabilities",
                header: "Funções ativas",
                cell: (r) => `${r.capabilities_working} de ${r.capabilities_total}`,
                align: "right",
              },
              { key: "idle", header: "Atividade", cell: (r) => <IdleCell row={r} /> },
              {
                key: "alerts",
                header: "Alertas",
                // Health alerts of the daily monitors (D110), with words, not only a number.
                cell: (r) =>
                  r.alerts_open === 0
                    ? "Nenhum"
                    : `${r.alerts_open} ${r.alerts_open === 1 ? "aberto" : "abertos"}`,
                align: "right",
              },
            ]}
          />
        </section>
      )}

      <section className="mt-8" aria-labelledby="fila-titulo">
        <CardTitle
          action={
            queue.length > 5 ? (
              <Link href="/admin/fila" className="text-[13px] text-fg-2 hover:text-fg">
                Ver todos os {queue.length} itens
              </Link>
            ) : undefined
          }
        >
          <span id="fila-titulo">Fila de exceções</span>
        </CardTitle>
        <QueueList items={queue.slice(0, 5)} />
      </section>
    </>
  );
}
