import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { auditCondos } from "@/lib/audit";
import { formatMonthTitle } from "@/lib/format";
import type { Me } from "@/lib/types";

type Issue = {
  id: string;
  control_id: string;
  control: string;
  title: string;
  status: string;
  first_competence: string;
  last_competence: string;
  months_open: number;
  sla: "em_dia" | "atencao" | "escalada" | "resolvida";
  sla_label: string;
  case: { id: string; title: string; status: string } | null;
  events: { kind: string; competencia: string; at: string }[];
};

/** Persistent audit issues (D123): one per gap, kept across months, reopened with the same
 * history; each one can become a case. */
export default async function AuditIssuesPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; status?: string }>;
}) {
  const sp = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = auditCondos(me);
  if (condos.length === 0)
    return <EmptyState title="Sem acesso à auditoria">Seu papel não vê as pendências.</EmptyState>;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : condos[0]!.id;
  const status = sp.status === "resolvida" ? "resolvida" : "aberta";
  const issues = await apiGet<Issue[]>(`/condominiums/${selected}/audit/issues?status=${status}`);
  return (
    <>
      <PageHeader
        title="Pendências da auditoria"
        subtitle="Cada pendência é uma só ao longo dos meses: quando volta, reabre com o mesmo histórico."
      />
      <nav className="mb-4 flex flex-wrap gap-2 text-sm" aria-label="Condomínio e situação">
        {condos.map((c) => (
          <Link
            key={c.id}
            href={`/admin/audit/pendencias?condominio=${c.id}&status=${status}`}
            aria-current={c.id === selected ? "page" : undefined}
            className={
              c.id === selected
                ? "rounded-full border border-accent px-3 py-1 font-medium"
                : "rounded-full border border-control px-3 py-1 text-fg-2"
            }
          >
            {c.name}
          </Link>
        ))}
        {(["aberta", "resolvida"] as const).map((s) => (
          <Link
            key={s}
            href={`/admin/audit/pendencias?condominio=${selected}&status=${s}`}
            aria-current={s === status ? "page" : undefined}
            className={
              s === status
                ? "rounded-full border border-accent px-3 py-1 font-medium"
                : "rounded-full border border-control px-3 py-1 text-fg-2"
            }
          >
            {s === "aberta" ? "Abertas" : "Resolvidas"}
          </Link>
        ))}
      </nav>
      {issues.length === 0 ? (
        <EmptyState
          title={status === "aberta" ? "Nenhuma pendência aberta" : "Nenhuma pendência resolvida"}
        >
          As pendências nascem do que cada controle diz que falta.
        </EmptyState>
      ) : (
        <ul className="space-y-3" data-testid="audit-issues">
          {issues.map((i) => (
            <li
              key={i.id}
              className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[13px] text-fg-2">{i.control_id}</span>
                <span className="text-sm text-fg-2">{i.control}</span>
                <Badge tone={i.status === "aberta" ? "warning" : "success"}>
                  {i.status === "aberta" ? "Aberta" : "Resolvida"}
                </Badge>
                {i.sla !== "resolvida" && (
                  <Badge
                    tone={
                      i.sla === "escalada" ? "danger" : i.sla === "atencao" ? "warning" : "neutral"
                    }
                  >
                    SLA: {i.sla_label}
                  </Badge>
                )}
                {i.months_open > 1 && <Badge tone="neutral">{i.months_open} meses</Badge>}
                {i.case && <Badge tone="info">Assunto: {i.case.status}</Badge>}
              </div>
              <p className="mt-1 text-sm">{i.title}</p>
              <p className="mt-1 text-xs text-fg-2">
                Desde {formatMonthTitle(`${i.first_competence}-01`)} · última vez em{" "}
                {formatMonthTitle(`${i.last_competence}-01`)} ·{" "}
                {i.events.map((e) => `${e.kind} (${e.competencia})`).join(", ")}
              </p>
              <div className="mt-2 flex gap-3 text-sm">
                <Link
                  className="text-fg-2 underline-offset-2 hover:underline"
                  href={`/admin/audit/controle/${selected}/${i.control_id}?competencia=${i.last_competence}`}
                >
                  Ver o controle
                </Link>
                <Link
                  className="text-fg-2 underline-offset-2 hover:underline"
                  href={`/admin/assuntos/novo?${new URLSearchParams({ condominio: selected, titulo: `Auditoria ${i.control_id}: ${i.title}`.slice(0, 190) })}`}
                >
                  Criar assunto
                </Link>
                <Link
                  className="text-fg-2 underline-offset-2 hover:underline"
                  href={`/admin/pedidos/novo?${new URLSearchParams({ condominio: selected, item: i.title.slice(0, 190) })}`}
                >
                  Pedir documento
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
