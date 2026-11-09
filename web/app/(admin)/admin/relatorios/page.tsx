import { Download, FileSpreadsheet, FileText } from "lucide-react";

import { ComplianceBadge } from "@/components/condoos/ComplianceBadge";
import { CondoFilter } from "@/components/condoos/CondoFilter";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { competenceParam, formatMonthTitle } from "@/lib/format";
import type { ComplianceList, MonthlyReport, Portfolio } from "@/lib/types";

/** Reports in one place (D111): monthly reports, the decision trail and the compliance
 * dossiers of one condominium, for the board and the assembly. */
export default async function RelatoriosAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const sp = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const target = selected ?? (condos.length === 1 ? (condos[0]?.id ?? null) : null);
  const [reports, compliance] = target
    ? await Promise.all([
        apiGet<MonthlyReport[]>(`/condominiums/${target}/reports`),
        apiGet<ComplianceList>(`/condominiums/${target}/compliance`),
      ])
    : [[], null];
  const dossiers = (compliance?.obligations ?? []).filter((o) => o.applicability === "aplicavel");
  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader
        title="Relatórios"
        subtitle="Relatório do mês, trilha de decisões e dossiês de conformidade"
      />
      <CondoFilter pathname="/admin/relatorios" condos={condos} selected={selected} />
      {!target ? (
        <EmptyState title="Escolha um condomínio">Os relatórios são por condomínio.</EmptyState>
      ) : (
        <>
          <Card aria-label="Relatórios mensais">
            <CardTitle>Relatórios mensais</CardTitle>
            {reports.length === 0 ? (
              <p className="text-[13px] text-fg-2">Nenhuma competência ainda.</p>
            ) : (
              <ul className="divide-y divide-line">
                {reports.map((r) => {
                  const base = `/api/condominiums/${target}/reports/${competenceParam(r.competence)}`;
                  const closed = r.status === "fechada";
                  return (
                    <li
                      key={r.competence}
                      className="flex items-center justify-between gap-3 py-2 text-sm"
                    >
                      <span className="inline-flex min-w-0 items-center gap-2">
                        <FileText size={16} aria-hidden className="shrink-0 text-fg-2" />
                        <span className="truncate">{formatMonthTitle(r.competence)}</span>
                        <span className="text-xs text-fg-2">
                          · {closed ? "fechado" : "em aberto (prévia)"} · {r.findings}{" "}
                          {r.findings === 1 ? "achado" : "achados"}
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
            )}
          </Card>
          <Card aria-label="Trilha de decisões">
            <CardTitle
              action={
                <a
                  href={`/api/condominiums/${target}/decisions.pdf`}
                  className={buttonClass("ghost", "sm")}
                >
                  <Download size={14} aria-hidden /> PDF
                </a>
              }
            >
              Trilha de decisões
            </CardTitle>
            <p className="text-[13px] text-fg-2">
              Quem decidiu o quê sobre cada achado, para levar à assembleia.
            </p>
          </Card>
          <Card aria-label="Dossiês de conformidade">
            <CardTitle>Dossiês de conformidade</CardTitle>
            {dossiers.length === 0 ? (
              <p className="text-[13px] text-fg-2">
                Nenhuma obrigação confirmada ainda. Confirme as que se aplicam em Conformidade.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {dossiers.map((o) => (
                  <li key={o.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <span className="min-w-0">
                      <span className="block truncate">{o.name}</span>
                      <ComplianceBadge situation={o.situation} />
                    </span>
                    <a
                      href={`/api/condominiums/${target}/compliance/${o.id}/dossier.pdf`}
                      className={buttonClass("ghost", "sm")}
                    >
                      <Download size={14} aria-hidden /> Dossiê
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
