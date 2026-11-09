import { Download, FileSpreadsheet, FileText, History } from "lucide-react";
import Link from "next/link";

import { buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Timeline } from "@/components/ui/Timeline";
import { apiGet } from "@/lib/api";
import { competenceParam, formatDateTime, formatMonthTitle } from "@/lib/format";
import { ACTION_LABEL } from "@/lib/labels";
import type { MonthlyReport, TrailItem } from "@/lib/types";

export default async function HistoricoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [trail, reports] = await Promise.all([
    apiGet<TrailItem[]>(`/condominiums/${id}/decisions`),
    apiGet<MonthlyReport[]>(`/condominiums/${id}/reports`),
  ]);
  const closed = reports.filter((r) => r.status === "fechada");
  return (
    <>
      <h1 className="text-xl font-semibold">Relatórios</h1>
      <Card>
        <CardTitle
          action={
            trail.length > 0 ? (
              <a
                href={`/api/condominiums/${id}/decisions.pdf`}
                className={buttonClass("ghost", "sm")}
              >
                <Download size={14} aria-hidden /> Exportar PDF
              </a>
            ) : undefined
          }
        >
          Trilha de decisões
        </CardTitle>
        <p className="mb-4 text-[13px] text-fg-2">
          Quem decidiu o quê sobre cada achado. Exporte em PDF para levar à assembleia.
        </p>
        {trail.length === 0 ? (
          <EmptyState icon={<History size={28} />} title="Nenhuma decisão registrada ainda">
            As decisões sobre os achados aparecem aqui.
          </EmptyState>
        ) : (
          <Timeline
            label="Trilha de decisões"
            items={trail.map((t, i) => ({
              id: `${t.finding_id}-${i}`,
              when: formatDateTime(t.decided_at),
              who: t.user_name,
              what: (
                <>
                  {ACTION_LABEL[t.action]?.verb ?? t.action}{" "}
                  <Link
                    href={`/condominio/${id}/achados/${t.finding_id}`}
                    className="underline underline-offset-2 hover:text-accent"
                  >
                    {t.finding_title}
                  </Link>
                </>
              ),
              detail: t.comment ? <q>{t.comment}</q> : undefined,
            }))}
          />
        )}
      </Card>
      <Card>
        <CardTitle>Relatórios mensais</CardTitle>
        <ul className="divide-y divide-line">
          {closed.map((r) => {
            const base = `/api/condominiums/${id}/reports/${competenceParam(r.competence)}`;
            return (
              <li
                key={r.competence}
                className="flex items-center justify-between gap-3 py-2 text-sm"
              >
                <span className="inline-flex min-w-0 items-center gap-2">
                  <FileText size={16} aria-hidden className="shrink-0 text-fg-2" />
                  <span className="truncate">{formatMonthTitle(r.competence)}</span>
                  <span className="text-xs text-fg-2">
                    · {r.findings} {r.findings === 1 ? "achado" : "achados"}
                  </span>
                </span>
                <span className="flex shrink-0 gap-1">
                  <a href={`${base}.pdf`} className={buttonClass("ghost", "sm")}>
                    <Download size={14} aria-hidden /> PDF
                  </a>
                  <a href={`${base}.xlsx`} className={buttonClass("ghost", "sm")}>
                    <FileSpreadsheet size={14} aria-hidden /> XLSX
                  </a>
                </span>
              </li>
            );
          })}
        </ul>
      </Card>
    </>
  );
}
