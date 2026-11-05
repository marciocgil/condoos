import { AlertTriangle, CheckCircle2, Inbox, Send, Wallet } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { QueueList } from "@/components/QueueList";
import { Badge } from "@/components/ui/Badge";
import { CardTitle } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { KpiCard } from "@/components/ui/KpiCard";
import { apiGet } from "@/lib/api";
import { formatBRLShort, formatMonth } from "@/lib/format";
import type { Portfolio, PortfolioRow, QueueItem } from "@/lib/types";

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
  const [p, queue] = await Promise.all([
    apiGet<Portfolio>("/portfolio"),
    apiGet<QueueItem[]>("/queue"),
  ]);
  const n = p.condominiums.length;
  return (
    <>
      <PageHeader
        title="Carteira"
        subtitle={`${n} ${n === 1 ? "condomínio" : "condomínios"}${p.latest_competence ? ` · ${formatMonth(p.latest_competence)}` : ""}`}
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
          context={`${p.serious} ${p.serious === 1 ? "grave" : "graves"}`}
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
          ]}
        />
      </div>

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
