import { AuditImports } from "@/components/audit/AuditImports";
import { AuditProfileForm } from "@/components/audit/AuditProfileForm";
import { AuditToolbar } from "@/components/audit/AuditToolbar";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { auditCondos, lastMonth } from "@/lib/audit";
import { formatBRL, formatDate } from "@/lib/format";
import type { Me } from "@/lib/types";

type Units = {
  competencia: string;
  can_import: boolean;
  units: {
    id: string;
    code: string;
    block: string | null;
    fraction: string | null;
    open_balance: string;
    titles: {
      kind: string;
      amount: string;
      due_date: string;
      status: string;
      paid_at: string | null;
      paid_amount: string | null;
    }[];
    readings: { utility: string; consumption: string }[];
  }[];
};
type Profile = {
  profile: Record<string, boolean | null>;
  questions: Record<string, string>;
  can_edit: boolean;
};

/** Units and receivables (D123): internal view, unit code only, never a resident's name. */
export default async function UnitsPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; competencia?: string }>;
}) {
  const sp = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = auditCondos(me);
  if (condos.length === 0)
    return (
      <EmptyState title="Sem acesso à auditoria">Seu papel não vê os dados por unidade.</EmptyState>
    );
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : condos[0]!.id;
  const competencia = /^\d{4}-\d{2}$/.test(sp.competencia ?? "") ? sp.competencia! : lastMonth();
  const [data, profile] = await Promise.all([
    apiGet<Units>(`/condominiums/${selected}/audit/units?competencia=${competencia}`),
    apiGet<Profile>(`/condominiums/${selected}/audit/profile`),
  ]);
  const open = data.units.filter((u) => Number(u.open_balance) > 0);
  return (
    <>
      <PageHeader
        title="Unidades e receitas"
        subtitle="Dado interno da equipe: unidade, títulos, situação e consumo. Nenhum nome de morador é lido ou guardado."
      />
      <AuditToolbar
        pathname="/admin/audit/unidades"
        condos={condos}
        selected={selected}
        competencia={competencia}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardTitle>
            Unidades ({data.units.length}) · {open.length} com saldo em aberto
          </CardTitle>
          {data.units.length === 0 ? (
            <p className="mt-2 text-sm text-fg-2">Nenhuma unidade importada.</p>
          ) : (
            <table className="mt-2 w-full text-[13px]" data-testid="units-table">
              <thead className="text-left text-fg-2">
                <tr>
                  <th className="py-1 pr-2">Unidade</th>
                  <th className="py-1 pr-2">Títulos do mês</th>
                  <th className="py-1 pr-2">Consumo (mês anterior)</th>
                  <th className="py-1 text-right">Em aberto</th>
                </tr>
              </thead>
              <tbody>
                {data.units.map((u) => (
                  <tr key={u.id} className="border-t border-line align-top">
                    <td className="py-1 pr-2 font-medium">
                      {u.code}
                      {u.fraction && (
                        <span className="block text-xs text-fg-2">fração {u.fraction}</span>
                      )}
                    </td>
                    <td className="py-1 pr-2">
                      {u.titles.length === 0 ? (
                        <span className="text-warning">sem título</span>
                      ) : (
                        u.titles.map((t, i) => (
                          <span key={i} className="block">
                            {t.kind} {formatBRL(t.amount)} · vence {formatDate(t.due_date)} ·{" "}
                            <Badge
                              tone={
                                t.status === "pago"
                                  ? "success"
                                  : t.status === "aberto"
                                    ? "warning"
                                    : "neutral"
                              }
                            >
                              {t.status}
                            </Badge>
                          </span>
                        ))
                      )}
                    </td>
                    <td className="py-1 pr-2">
                      {u.readings.map((r) => `${r.utility} ${r.consumption}`).join(" · ") || "—"}
                    </td>
                    <td className="tabular py-1 text-right">{formatBRL(u.open_balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <aside className="space-y-6">
          {data.can_import && (
            <Card>
              <CardTitle>Importar planilhas (CSV)</CardTitle>
              <div className="mt-2">
                <AuditImports condominiumId={selected} />
              </div>
            </Card>
          )}
          <Card>
            <CardTitle>Perfil de auditoria</CardTitle>
            <p className="mt-1 text-[13px] text-fg-2">
              Define o que se aplica ao condomínio. Sem resposta, os controles que dependem dela
              ficam pendentes.
            </p>
            <div className="mt-2">
              <AuditProfileForm
                condominiumId={selected}
                profile={profile.profile}
                questions={profile.questions}
                canEdit={profile.can_edit}
              />
            </div>
          </Card>
        </aside>
      </div>
    </>
  );
}
