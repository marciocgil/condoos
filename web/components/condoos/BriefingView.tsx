import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  CircleDot,
  Database,
  Gavel,
  Hammer,
  Info,
  PiggyBank,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { formatDate, formatDateTime } from "@/lib/format";
import type { Briefing, BriefingItem } from "@/lib/types";

import { BriefingActions } from "./BriefingActions";

const ICON: Record<string, React.ReactNode> = {
  riscos: <AlertTriangle size={16} aria-hidden />,
  decisoes: <Gavel size={16} aria-hidden />,
  andamento: <Hammer size={16} aria-hidden />,
  concluido: <CheckCircle2 size={16} aria-hidden />,
  agenda: <CalendarDays size={16} aria-hidden />,
  oportunidades: <PiggyBank size={16} aria-hidden />,
  dados: <Database size={16} aria-hidden />,
};
const TONE_LABEL: Record<BriefingItem["tone"], string> = {
  danger: "Atenção",
  warning: "Verificar",
  info: "Decidir",
  success: "Feito",
  neutral: "",
};

function when(item: BriefingItem): string {
  if (!item.when) return "";
  return item.when.length === 10 ? formatDate(item.when) : formatDateTime(item.when);
}

/** Hoje (spec §7.3, VS-04): the day's briefing, every item linked to its source.
 * ``paths`` maps a source type to a path template with "{id}" (strings, not functions). */
export function BriefingView({
  briefing: b,
  paths,
  compact = false,
  withName = false,
}: {
  briefing: Briefing;
  paths: Record<string, string>;
  /** Only sections with something to show. */
  compact?: boolean;
  /** Condominium name in the title (desktop, several condominiums). */
  withName?: boolean;
}) {
  const sections = compact
    ? b.sections.filter((s) => s.count > 0 && s.key !== "dados")
    : b.sections;
  // A source that never received anything is "starting", not "late" (LB-083, D108).
  const starting = b.partial_sources.filter((p) => p.not_started);
  const late = b.partial_sources.filter((p) => !p.not_started);
  return (
    <section aria-labelledby={`briefing-${b.id}`} className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id={`briefing-${b.id}`} className="text-lg font-semibold">
            Hoje{withName ? ` · ${b.condominium_name}` : ""}
          </h2>
          <p className="text-sm">{b.headline}</p>
          <p className="text-xs text-muted">
            Desde {formatDateTime(b.period_start)} · versão {b.version} de{" "}
            {formatDate(b.local_date)} · gerado em {formatDateTime(b.generated_at)}
          </p>
        </div>
        <BriefingActions
          condominiumId={b.condominium_id}
          briefingId={b.id}
          read={b.read_at !== null}
        />
      </div>
      {late.length > 0 && (
        <div
          role="note"
          className="rounded-[var(--radius-card)] border border-warning/60 bg-bg-2 p-3 text-[13px]"
        >
          <p className="flex items-center gap-1.5 font-medium">
            <AlertTriangle size={14} aria-hidden className="text-warning" /> Dados parciais
          </p>
          <ul className="mt-1 list-disc pl-5">
            {late.map((p) => (
              <li key={p.source}>
                {p.label}: {p.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      {starting.length > 0 && (
        <div
          role="note"
          data-testid="briefing-starting"
          className="rounded-[var(--radius-card)] border border-line bg-bg-2 p-3 text-[13px]"
        >
          <p className="flex items-center gap-1.5 font-medium">
            <Info size={14} aria-hidden className="text-info" /> Começando
          </p>
          <ul className="mt-1 list-disc pl-5 text-fg-2">
            {starting.map((p) => (
              <li key={p.source}>{p.reason}</li>
            ))}
          </ul>
        </div>
      )}
      {sections.map((s) => (
        <div key={s.key} className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold">
            {ICON[s.key] ?? <CircleDot size={16} aria-hidden />}
            {s.title}
            <span className="text-[13px] font-normal text-muted">({s.count})</span>
          </h3>
          {s.items.length === 0 ? (
            <p className="mt-2 text-[13px] text-fg-2">Nada aqui.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line">
              {s.items.map((item, i) => {
                const template = item.ref ? paths[item.ref.type] : paths[item.kind];
                const href = template ? template.replace("{id}", item.ref?.id ?? "") : null;
                const label = (
                  <>
                    <span className="block text-sm font-medium">{item.title}</span>
                    <span className="block text-[13px] text-fg-2">
                      {item.detail}
                      {when(item) && ` · ${when(item)}`}
                    </span>
                  </>
                );
                return (
                  <li key={`${s.key}-${i}`} className="flex items-start justify-between gap-2 py-2">
                    {href ? (
                      <Link href={href} className="min-w-0 hover:underline">
                        {label}
                      </Link>
                    ) : (
                      <span className="min-w-0">{label}</span>
                    )}
                    {TONE_LABEL[item.tone] && (
                      <Badge
                        tone={item.tone === "info" ? "accent" : item.tone}
                        icon={
                          item.tone === "success" ? (
                            <CheckCircle2 size={12} />
                          ) : (
                            <AlertTriangle size={12} />
                          )
                        }
                      >
                        {TONE_LABEL[item.tone]}
                      </Badge>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {s.count > s.items.length && (
            <p className="mt-1 text-xs text-muted">e mais {s.count - s.items.length}.</p>
          )}
        </div>
      ))}
    </section>
  );
}
