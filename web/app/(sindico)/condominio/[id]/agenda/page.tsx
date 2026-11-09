import { CalendarDays } from "lucide-react";

import { AgendaItem, isLate } from "@/components/condoos/AgendaItem";
import { MonthCoverageCard } from "@/components/condoos/MonthCoverageCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Agenda, AgendaEvent, MonthCoverage } from "@/lib/types";

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function group(events: AgendaEvent[]): [string, AgendaEvent[]][] {
  const by = new Map<string, AgendaEvent[]>();
  for (const e of events) by.set(e.date, [...(by.get(e.date) ?? []), e]);
  return [...by.entries()];
}

/** Agenda of the board (D71, mobile): what is late, and the next 30 days. */
export default async function AgendaSindicoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const now = new Date();
  const today = iso(new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())));
  const from = iso(new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate() - 60)));
  const to = iso(new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate() + 30)));
  const [agenda, coverage] = await Promise.all([
    apiGet<Agenda>(`/condominiums/${id}/agenda?start=${from}&end=${to}`),
    apiGet<MonthCoverage>(`/condominiums/${id}/coverage`),
  ]);
  const late = agenda.events.filter(isLate);
  const upcoming = agenda.events.filter((e) => e.date >= today && !isLate(e));
  const contractHref = `/condominio/${id}/contratos`;
  const href = (e: AgendaEvent) =>
    e.obligation_id
      ? `/condominio/${id}/conformidade/${e.obligation_id}`
      : e.contract_id
        ? contractHref
        : `/condominio/${id}/historico`;

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold">Agenda</h1>
        <p className="mt-1 text-[13px] text-fg-2">
          Vencimentos, notas previstas dos contratos, reajustes e fim de contratos. Datas previstas
          são estimadas pelo histórico. O CondoOS não faz pagamentos: a agenda serve para
          acompanhar.
        </p>
      </div>

      <MonthCoverageCard coverage={coverage} />

      {late.length > 0 && (
        <section aria-labelledby="late" className="space-y-2">
          <h2 id="late" className="text-base font-semibold">
            Em atraso ({late.length})
          </h2>
          {late.map((e, k) => (
            <AgendaItem key={k} event={e} href={href(e)} />
          ))}
        </section>
      )}

      <section aria-labelledby="next" className="space-y-3">
        <h2 id="next" className="text-base font-semibold">
          Próximos 30 dias
        </h2>
        {upcoming.length === 0 ? (
          <EmptyState icon={<CalendarDays size={28} />} title="Nada previsto">
            Nenhum vencimento, nota ou reajuste nos próximos 30 dias.
          </EmptyState>
        ) : (
          <ol className="space-y-4">
            {group(upcoming).map(([day, items]) => (
              <li key={day}>
                <h3 className="mb-1.5 text-[13px] font-medium text-fg-2">
                  {formatDate(day)}
                  {day === today && " · hoje"}
                </h3>
                <div className="space-y-2">
                  {items.map((e, k) => (
                    <AgendaItem key={k} event={e} href={href(e)} />
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
