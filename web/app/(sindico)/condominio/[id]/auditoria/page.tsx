import { Gauge } from "lucide-react";

import { ControlStatusBadge } from "@/components/audit/ControlStatusBadge";
import { AuditPublicationDecision } from "@/components/condoos/AuditPublicationDecision";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { PUBLICATION_LABEL, type Publication } from "@/lib/audit";
import { formatDateTime } from "@/lib/format";
import type { ControlStatusCode } from "@/lib/types";

const ORDER: ControlStatusCode[] = [
  "DIVERGENTE",
  "PENDENTE",
  "COM_RESSALVA",
  "VALIDADO",
  "NAO_APLICAVEL",
  "NAO_AVALIADO",
];

function monthLabel(ym: string): string {
  const [y, m] = ym.split("-");
  return `${m}/${y}`;
}

function Farol({ p }: { p: Publication }) {
  const controls = [...p.snapshot.controles].sort(
    (a, b) =>
      ORDER.indexOf(a.status as ControlStatusCode) - ORDER.indexOf(b.status as ControlStatusCode),
  );
  return (
    <ul className="mt-3 divide-y divide-line">
      {controls.map((c) => (
        <li key={c.id} className="py-2" data-testid={`published-${c.id}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium">{c.nome}</p>
            <ControlStatusBadge status={c.status as ControlStatusCode} />
          </div>
          <p className="text-[13px] text-fg-2">{c.motivo}</p>
          {c.pendencias.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-[12px] text-fg-2">
              {c.pendencias.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

/** The month's audit farol for the board (D124): the síndico approves what the CondoOS team
 * sent; the conselho and the subsíndico see what was approved. No unit data. */
export default async function AuditoriaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiGet<{ publications: Publication[]; can_approve: boolean }>(
    `/condominiums/${id}/audit/publications`,
  );
  const waiting = data.publications.filter((p) => p.status === "aguardando_sindico");
  const approved = data.publications.filter((p) => p.status === "aprovada");
  return (
    <>
      <h1 className="text-xl font-semibold">Auditoria do mês</h1>
      <p className="text-[13px] text-fg-2">
        Os 25 controles do mês, revisados pela equipe CondoOS. Aprovar libera a leitura pelo corpo
        diretivo; não é a aprovação das contas, que é do conselho ou da assembleia.
      </p>
      {waiting.map((p) => (
        <Card key={p.id} className="mt-4" data-testid="publication-waiting">
          <p className="text-sm font-semibold">
            {monthLabel(p.competencia)} · {PUBLICATION_LABEL[p.status]}
          </p>
          <p className="text-[13px] text-fg-2">
            Enviado em {formatDateTime(p.submitted_at)}
            {p.submitted_by ? ` por ${p.submitted_by}` : ""}.
          </p>
          {data.can_approve && (
            <div className="mt-3">
              <AuditPublicationDecision condominiumId={id} publicationId={p.id} sha256={p.sha256} />
            </div>
          )}
          <Farol p={p} />
        </Card>
      ))}
      {approved.length === 0 && waiting.length === 0 ? (
        <EmptyState icon={<Gauge size={24} />} title="Nenhum farol publicado ainda">
          Quando a equipe CondoOS enviar a auditoria do mês, ela aparece aqui
          {data.can_approve ? " para a sua aprovação." : "."}
        </EmptyState>
      ) : (
        approved.map((p) => (
          <Card key={p.id} className="mt-4">
            <p className="text-sm font-semibold">
              {monthLabel(p.competencia)} · {PUBLICATION_LABEL[p.status]}
            </p>
            <p className="text-[13px] text-fg-2">
              Aprovado em {p.decided_at ? formatDateTime(p.decided_at) : "—"}
              {p.decided_by ? ` por ${p.decided_by}` : ""}.
              {p.changed_since
                ? " Depois da aprovação, uma revalidação mudou algum resultado deste mês: a equipe CondoOS vai reenviar."
                : ""}
            </p>
            <a
              href={`/api/condominiums/${id}/audit/publications/${p.id}/export.pdf`}
              className="mt-2 inline-block text-sm text-fg-2 underline-offset-2 hover:underline"
            >
              Baixar em PDF
            </a>
            <Farol p={p} />
          </Card>
        ))
      )}
    </>
  );
}
