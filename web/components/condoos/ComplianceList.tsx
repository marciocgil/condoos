import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/ui/EmptyState";
import type {
  ComplianceList as ComplianceListData,
  ComplianceObligationSummary,
} from "@/lib/types";

import { BuildingProfileCard } from "./BuildingProfileCard";
import { ComplianceBadge } from "./ComplianceBadge";
import { ComplianceReminderCard } from "./ComplianceReminderCard";
import { ComplianceSetup } from "./ComplianceSetup";

function Row({ ob, href }: { ob: ComplianceObligationSummary; href: string }) {
  const s = ob.situation;
  return (
    <li>
      <Link
        href={href}
        className="transition-ui flex items-start gap-3 rounded-[var(--radius-card)] border border-line bg-bg-2 px-3 py-2.5 hover:border-control"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{ob.name}</span>
          <span className="block text-[13px] text-fg-2">
            {ob.category_label} · {s.text}
          </span>
          {s.to_confirm && <span className="block text-xs text-warning">{s.to_confirm}</span>}
          {ob.hint && <span className="block text-xs text-info">Sugestão: {ob.hint.text}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <ComplianceBadge situation={s} />
          <ChevronRight size={16} className="text-muted" aria-hidden />
        </span>
      </Link>
    </li>
  );
}

const SUMMARY: [keyof ComplianceListData["counts"], string, string][] = [
  ["vencido", "vencido", "vencidos"],
  ["vence_em_breve", "vence em breve", "vencem em breve"],
  ["sem_documento", "sem documento", "sem documento"],
  ["a_validar", "a validar", "a validar"],
];

/** Compliance obligations of one condominium (D108), most urgent first. Shows only what is
 * registered in the CondoOS: whether an obligation applies is a person's decision. */
export function ComplianceList({
  condominiumId,
  data,
  detailBase,
}: {
  condominiumId: string;
  data: ComplianceListData;
  /** Base path of an obligation's page; "/<id>" is appended. */
  detailBase: string;
}) {
  const summary = SUMMARY.filter(([k]) => (data.counts[k] ?? 0) > 0).map(([k, one, many]) => {
    const n = data.counts[k] ?? 0;
    return `${n} ${n === 1 ? one : many}`;
  });
  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-2">
        Mostra só o que está registrado no CondoOS. Se uma obrigação se aplica ao condomínio e de
        quanto em quanto tempo renova, quem confirma é o síndico, com o responsável técnico.
      </p>
      {summary.length > 0 && (
        <p className="text-sm font-medium" data-testid="compliance-summary">
          {summary.join(" · ")}
        </p>
      )}
      <BuildingProfileCard
        condominiumId={condominiumId}
        profile={data.profile}
        canManage={data.can_manage}
      />
      <ComplianceReminderCard condominiumId={condominiumId} reminders={data.reminders} />
      <ComplianceSetup
        condominiumId={condominiumId}
        canManage={data.can_manage}
        catalogMissing={data.catalog_missing}
        categories={data.categories}
        detailBase={detailBase}
      />
      {data.obligations.length === 0 ? (
        <EmptyState title="Nenhuma obrigação cadastrada">
          {data.can_manage
            ? "Comece pela lista de obrigações comuns em condomínios e confirme as que se aplicam."
            : "O síndico ou a administradora ainda não cadastrou obrigações."}
        </EmptyState>
      ) : (
        <ul className="space-y-2" aria-label="Obrigações">
          {data.obligations.map((ob) => (
            <Row key={ob.id} ob={ob} href={`${detailBase}/${ob.id}`} />
          ))}
        </ul>
      )}
      {data.archived.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-fg-2">
            Arquivadas ({data.archived.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {data.archived.map((ob) => (
              <Row key={ob.id} ob={ob} href={`${detailBase}/${ob.id}`} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
