import { CalendarDays } from "lucide-react";
import Link from "next/link";

import { CardTitle } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

import { AgendaItem, isLate } from "./AgendaItem";
import type { Agenda } from "@/lib/types";

/** Resumo card: what is late and the next items of the agenda (D71). */
export async function AgendaPreview({ condominiumId }: { condominiumId: string }) {
  const now = new Date();
  const day = (offset: number) =>
    new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate() + offset))
      .toISOString()
      .slice(0, 10);
  const today = day(0);
  const agenda = await apiGet<Agenda>(
    `/condominiums/${condominiumId}/agenda?start=${day(-60)}&end=${day(30)}`,
  );
  const late = agenda.events.filter(isLate);
  const next = agenda.events.filter((e) => e.date >= today && !isLate(e));
  const shown = [...late, ...next].slice(0, 3);
  const href = `/condominio/${condominiumId}/agenda`;
  return (
    <section aria-labelledby="agenda-title">
      <CardTitle
        action={
          <Link href={href} className="text-[13px] text-fg-2 hover:text-fg">
            Ver agenda
          </Link>
        }
      >
        <span id="agenda-title" className="inline-flex items-center gap-2">
          <CalendarDays size={16} aria-hidden className="text-info" /> Agenda
          {late.length > 0 && (
            <span className="text-[13px] font-normal text-danger">· {late.length} em atraso</span>
          )}
        </span>
      </CardTitle>
      {shown.length === 0 ? (
        <p className="text-[13px] text-muted">Nada previsto nos próximos 30 dias.</p>
      ) : (
        <div className="space-y-2">
          {shown.map((e, k) => (
            <AgendaItem key={k} event={e} href={href} />
          ))}
        </div>
      )}
    </section>
  );
}
