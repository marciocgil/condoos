import { FileText, History } from "lucide-react";
import Link from "next/link";

import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Timeline } from "@/components/ui/Timeline";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatMonthTitle } from "@/lib/format";
import { ACTION_LABEL } from "@/lib/labels";
import type { Competence, TrailItem } from "@/lib/types";

export default async function HistoricoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [trail, competences] = await Promise.all([
    apiGet<TrailItem[]>(`/condominiums/${id}/decisions`),
    apiGet<Competence[]>(`/condominiums/${id}/competences`),
  ]);
  const closed = competences.filter((c) => c.status === "fechada");
  return (
    <>
      <h1 className="text-xl font-semibold">Histórico</h1>
      <Card>
        <CardTitle>Trilha de decisões</CardTitle>
        <p className="mb-4 text-[13px] text-fg-2">
          Quem decidiu o quê sobre cada achado. A exportação em PDF para a assembleia chega com os
          relatórios mensais.
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
          {closed.map((c) => (
            <li key={c.id} className="flex items-center justify-between py-2 text-sm">
              <span className="inline-flex items-center gap-2">
                <FileText size={16} aria-hidden className="text-fg-2" /> {formatMonthTitle(c.month)}
              </span>
              <span className="text-xs text-muted">PDF em breve</span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
