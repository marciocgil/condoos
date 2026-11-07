import { Card, CardTitle } from "@/components/ui/Card";
import type { Contract } from "@/lib/types";

const NOT_AVAILABLE = "não disponível no texto do contrato";

/** Termination terms read from the contract text, each with its excerpt (CB-060). */
export function ContractClauses({ contract: c }: { contract: Contract }) {
  const ev = c.clause_evidence ?? {};
  const rows: { label: string; value: string; excerpt?: string }[] = [
    {
      label: "Aviso prévio",
      value: c.notice_days ? `${c.notice_days} dias` : NOT_AVAILABLE,
      excerpt: ev.notice_days?.excerpt,
    },
    {
      label: "Renovação automática",
      value:
        c.auto_renewal === null || c.auto_renewal === undefined
          ? NOT_AVAILABLE
          : c.auto_renewal
            ? "Sim"
            : "Não",
      excerpt: ev.auto_renewal?.excerpt,
    },
    {
      label: "Multa por rescisão",
      value: c.termination_penalty ?? NOT_AVAILABLE,
      excerpt: ev.termination_penalty?.excerpt,
    },
  ];
  return (
    <Card>
      <CardTitle>Rescisão e renovação</CardTitle>
      <dl className="space-y-3 text-sm">
        {rows.map((r) => (
          <div key={r.label}>
            <dt className="text-[13px] text-muted">{r.label}</dt>
            <dd>{r.value}</dd>
            {r.excerpt && (
              <dd className="mt-1 border-l-2 border-line pl-2 text-xs text-fg-2">
                <q>{r.excerpt}</q>
              </dd>
            )}
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-muted">
        Lido do texto do contrato por regra; a data-limite do aviso aparece na Agenda.
      </p>
    </Card>
  );
}
