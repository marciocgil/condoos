import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { AgendaItem, agendaStatus, isLate, KIND_LABEL } from "@/components/condoos/AgendaItem";
import { CondoFilter } from "@/components/condoos/CondoFilter";
import { MonthCoverageCard } from "@/components/condoos/MonthCoverageCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonClass } from "@/components/ui/Button";
import { cx } from "@/components/ui/cx";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips } from "@/components/ui/FilterChips";
import { apiGet } from "@/lib/api";
import { formatDate, formatMonthTitle } from "@/lib/format";
import type { Agenda, AgendaEvent, AgendaKind, MonthCoverage, Portfolio } from "@/lib/types";

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const KINDS = Object.keys(KIND_LABEL) as AgendaKind[];

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function eventHref(e: AgendaEvent): string | null {
  if (e.obligation_id && e.condominium_id)
    return `/admin/conformidade/${e.condominium_id}/${e.obligation_id}`;
  return e.contract_id && e.condominium_id
    ? `/admin/contratos/${e.condominium_id}/${e.contract_id}`
    : null;
}

/** Agenda of the portfolio (D71): due dates, expected invoices, adjustments, contract ends. */
export default async function AgendaPage({
  searchParams,
}: {
  searchParams: Promise<{ mes?: string; condominio?: string; tipo?: string | string[] }>;
}) {
  const sp = await searchParams;
  const now = new Date();
  const [y, m] =
    sp.mes && /^\d{4}-\d{2}$/.test(sp.mes)
      ? sp.mes.split("-").map(Number)
      : [now.getFullYear(), now.getMonth() + 1];
  const first = new Date(Date.UTC(y!, m! - 1, 1));
  const last = new Date(Date.UTC(y!, m!, 0));
  const month = iso(first).slice(0, 7);
  const prev = iso(new Date(Date.UTC(y!, m! - 2, 1))).slice(0, 7);
  const next = iso(new Date(Date.UTC(y!, m!, 1))).slice(0, 7);
  const kinds = ([] as string[])
    .concat(sp.tipo ?? [])
    .filter((k): k is AgendaKind => KINDS.includes(k as AgendaKind));

  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const q = new URLSearchParams({ start: iso(first), end: iso(last) });
  if (selected) q.set("condominium_id", selected);
  kinds.forEach((k) => q.append("kind", k));
  const agenda = await apiGet<Agenda>(`/portfolio/agenda?${q.toString()}`);
  // LB-055: the month's expected invoices, per condominium (one chosen, or the only one).
  const coverageCondo = selected ?? (condos.length === 1 ? (condos[0]?.id ?? null) : null);
  const coverage = coverageCondo
    ? await apiGet<MonthCoverage>(`/condominiums/${coverageCondo}/coverage?month=${month}`)
    : null;

  const byDay = new Map<string, AgendaEvent[]>();
  for (const e of agenda.events) byDay.set(e.date, [...(byDay.get(e.date) ?? []), e]);
  const late = agenda.events.filter(isLate).length;
  const today = iso(new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())));

  const cells: (string | null)[] = Array.from({ length: first.getUTCDay() }, () => null);
  for (let d = 1; d <= last.getUTCDate(); d++) cells.push(iso(new Date(Date.UTC(y!, m! - 1, d))));
  while (cells.length % 7) cells.push(null);

  const keep = (extra: Record<string, string>) => {
    const p = new URLSearchParams(extra);
    if (selected) p.set("condominio", selected);
    kinds.forEach((k) => p.append("tipo", k));
    return `/admin/agenda?${p.toString()}`;
  };
  const params: Record<string, string[]> = { mes: [month] };
  if (selected) params.condominio = [selected];

  return (
    <>
      <PageHeader
        title="Agenda"
        subtitle={`Vencimentos, NF prevista dos contratos, reajustes e fim de contrato · ${agenda.events.length} item(ns)${late ? ` · ${late} em atraso` : ""}`}
        actions={
          <div className="flex items-center gap-1">
            <Link
              href={keep({ mes: prev })}
              className={buttonClass("ghost", "sm")}
              aria-label="Mês anterior"
            >
              <ChevronLeft size={16} aria-hidden />
            </Link>
            <span className="min-w-36 text-center text-sm font-medium">
              {formatMonthTitle(iso(first))}
            </span>
            <Link
              href={keep({ mes: next })}
              className={buttonClass("ghost", "sm")}
              aria-label="Próximo mês"
            >
              <ChevronRight size={16} aria-hidden />
            </Link>
          </div>
        }
      />
      <CondoFilter
        pathname="/admin/agenda"
        condos={condos}
        selected={selected}
        extra={{ mes: month }}
      />
      <div className="mb-6">
        <FilterChips
          name="tipo"
          label="Mostrar"
          options={KINDS.map((k) => ({ value: k, label: KIND_LABEL[k] }))}
          selected={kinds}
          pathname="/admin/agenda"
          params={params}
        />
      </div>

      <div
        className="mb-8 overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface"
        aria-hidden
      >
        <div className="grid min-w-[760px] grid-cols-7 border-b border-line text-center text-xs text-fg-2">
          {WEEKDAYS.map((d) => (
            <div key={d} className="py-2">
              {d}
            </div>
          ))}
        </div>
        <div className="grid min-w-[760px] grid-cols-7">
          {cells.map((day, i) => {
            const items = day ? (byDay.get(day) ?? []) : [];
            return (
              <div
                key={day ?? `empty-${i}`}
                className={cx(
                  "min-h-24 border-r border-b border-line p-1.5 text-xs",
                  !day && "bg-bg-2/50",
                  day === today && "bg-accent/5",
                )}
              >
                {day && (
                  <span
                    className={cx(
                      "mb-1 inline-block",
                      day === today ? "font-semibold text-accent" : "text-fg-2",
                    )}
                  >
                    {Number(day.slice(8))}
                  </span>
                )}
                {items.slice(0, 3).map((e, k) => {
                  const look = agendaStatus(e);
                  return (
                    <span
                      key={k}
                      className={cx(
                        "mb-0.5 flex items-center gap-1 truncate rounded px-1 py-0.5",
                        look.tone === "danger" && "bg-danger/15 text-danger",
                        look.tone === "warning" && "bg-warning/15 text-warning",
                        look.tone === "success" && "bg-success/10 text-success",
                        look.tone === "info" && "bg-info/10 text-info",
                        look.tone === "neutral" && "bg-elevated text-fg-2",
                      )}
                    >
                      {look.icon}
                      <span className="truncate">{e.title.split(" · ")[1] ?? e.title}</span>
                    </span>
                  );
                })}
                {items.length > 3 && <span className="text-muted">+{items.length - 3} mais</span>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mb-6">
        {coverage ? (
          <MonthCoverageCard coverage={coverage} />
        ) : (
          <p className="text-sm text-fg-2">
            Escolha um condomínio para ver quais notas dos contratos já chegaram neste mês.
          </p>
        )}
      </div>

      <section aria-labelledby="lista">
        <h2 id="lista" className="mb-3 text-base font-semibold">
          {formatMonthTitle(iso(first))} por dia
        </h2>
        {agenda.events.length === 0 ? (
          <EmptyState title="Nada na agenda deste mês">
            Mude o mês, o condomínio ou os tipos mostrados.
          </EmptyState>
        ) : (
          <ol className="space-y-5">
            {[...byDay.entries()].map(([day, items]) => (
              <li key={day}>
                <h3 className={cx("mb-2 text-sm font-medium", day === today && "text-accent")}>
                  {formatDate(day)}
                  {day === today && " · hoje"}
                </h3>
                <div className="grid gap-2 lg:grid-cols-2">
                  {items.map((e, k) => (
                    <AgendaItem key={k} event={e} href={eventHref(e)} showCondo={!selected} />
                  ))}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}
