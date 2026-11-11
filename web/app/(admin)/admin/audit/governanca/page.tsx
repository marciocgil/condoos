import { AuditToolbar } from "@/components/audit/AuditToolbar";
import {
  AccountKindSelect,
  AccountsApprovalForm,
  BudgetImport,
  BudgetNoteForm,
  FundAccounts,
  FundBalancesImport,
  NewFundForm,
  type Governance,
} from "@/components/audit/GovernanceForms";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { auditCondos, lastMonth } from "@/lib/audit";
import { formatBRL, formatDate } from "@/lib/format";
import type { Me } from "@/lib/types";

const BODY: Record<string, string> = {
  conselho_fiscal: "Conselho fiscal",
  conselho_consultivo: "Conselho consultivo",
  assembleia: "Assembleia",
};

function money(v: string | null | undefined): string {
  return v === null || v === undefined ? "—" : formatBRL(v);
}

/** Funds, investments, budget and the formal approval of the accounts (D124): the inputs of
 * BAN-08, BAN-09, GOV-01 and DOC-03. */
export default async function GovernancePage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; competencia?: string }>;
}) {
  const sp = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = auditCondos(me);
  if (condos.length === 0)
    return <EmptyState title="Sem acesso à auditoria">Seu papel não vê estes dados.</EmptyState>;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : condos[0]!.id;
  const competencia = /^\d{4}-\d{2}$/.test(sp.competencia ?? "") ? sp.competencia! : lastMonth();
  const g = await apiGet<Governance>(
    `/condominiums/${selected}/audit/governance?competencia=${competencia}`,
  );
  const year = Number(competencia.slice(0, 4));
  return (
    <>
      <PageHeader
        title="Fundos, orçamento e aprovação das contas"
        subtitle="Entradas dos controles BAN-08, BAN-09, GOV-01 e DOC-03. Saldo positivo de fundo não é lastro segregado; desvio de orçamento não é erro, só a falta de explicação é ressalva."
      />
      <AuditToolbar
        pathname="/admin/audit/governanca"
        condos={condos}
        selected={selected}
        competencia={competencia}
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardTitle>Contas bancárias</CardTitle>
          {g.accounts.length === 0 ? (
            <p className="mt-2 text-sm text-fg-2">
              Nenhuma conta: elas aparecem com o primeiro extrato OFX.
            </p>
          ) : (
            <table className="mt-2 w-full text-[13px]" data-testid="accounts-table">
              <tbody>
                {g.accounts.map((a) => (
                  <tr key={a.id} className="border-t border-line align-top">
                    <td className="py-2 pr-2">{a.label}</td>
                    <td className="py-2 pr-2 text-right tabular">
                      {a.closing_balance ? money(a.closing_balance) : "sem extrato no mês"}
                    </td>
                    <td className="py-2">
                      {g.can_edit ? (
                        <AccountKindSelect condominiumId={selected} account={a} />
                      ) : (
                        a.kind
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-2 text-xs text-fg-2">
            Marque como “Aplicação” a conta que tem extrato próprio de investimento (BAN-09).
          </p>
        </Card>
        <Card>
          <CardTitle>Fundos ({g.funds.length})</CardTitle>
          {g.funds.length === 0 && (
            <p className="mt-2 text-sm text-fg-2">Nenhum fundo cadastrado.</p>
          )}
          <ul className="mt-2 space-y-4">
            {g.funds.map((f) => (
              <li key={f.id} className="border-t border-line pt-2" data-testid={`fund-${f.name}`}>
                <p className="font-medium">
                  {f.name}{" "}
                  {f.account_ids.length === 0 ? (
                    <Badge tone="warning">sem conta de lastro</Badge>
                  ) : (
                    <Badge tone="neutral">{f.account_ids.length} conta(s) de lastro</Badge>
                  )}
                </p>
                <p className="text-[13px] text-fg-2">
                  {f.balance
                    ? `Mês: inicial ${money(f.balance.opening)} + entradas ${money(f.balance.inflows)} − saídas ${money(f.balance.outflows)} + rendimentos ${money(f.balance.yield)} = final ${money(f.balance.closing)}`
                    : "Sem saldo do mês no demonstrativo."}
                </p>
                {g.can_edit && (
                  <FundAccounts condominiumId={selected} fund={f} accounts={g.accounts} />
                )}
              </li>
            ))}
          </ul>
          {g.can_edit && (
            <div className="mt-4 space-y-3 border-t border-line pt-3">
              <NewFundForm condominiumId={selected} />
              <FundBalancesImport condominiumId={selected} />
            </div>
          )}
        </Card>
        <Card>
          <CardTitle>Orçamento de {year}</CardTitle>
          {g.budget ? (
            <>
              <p className="mt-1 text-[13px] text-fg-2">
                Versão {g.budget.version}
                {g.budget.approved_on
                  ? `, aprovada em ${formatDate(g.budget.approved_on)}`
                  : ", sem data de aprovação"}
                {g.budget.document ? ` · ${g.budget.document}` : " · sem a ata ligada"}
              </p>
              <table className="mt-2 w-full text-[13px]" data-testid="budget-table">
                <thead className="text-left text-fg-2">
                  <tr>
                    <th className="py-1 pr-2">Categoria</th>
                    <th className="py-1 pr-2 text-right">Orçado</th>
                    <th className="py-1 text-right">Realizado</th>
                  </tr>
                </thead>
                <tbody>
                  {g.budget.lines.map((l) => (
                    <tr key={l.category} className="border-t border-line">
                      <td className="py-1 pr-2">{l.label}</td>
                      <td className="py-1 pr-2 text-right tabular">{money(l.budgeted)}</td>
                      <td className="py-1 text-right tabular">{money(l.realized)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className="mt-2 text-sm text-fg-2">Orçamento aprovado do ano não importado.</p>
          )}
          {g.notes.length > 0 && (
            <ul className="mt-3 space-y-1 text-[13px]">
              {g.notes.map((n) => (
                <li key={n.id}>
                  <span className="font-medium">{n.label}:</span> {n.text}
                </li>
              ))}
            </ul>
          )}
          {g.can_edit && (
            <div className="mt-4 space-y-4 border-t border-line pt-3">
              <BudgetNoteForm
                condominiumId={selected}
                competencia={competencia}
                categories={g.categories}
              />
              <BudgetImport condominiumId={selected} year={year} documents={g.documents} />
            </div>
          )}
        </Card>
        <Card>
          <CardTitle>Aprovação das contas (DOC-03)</CardTitle>
          {g.approvals.length === 0 ? (
            <p className="mt-2 text-sm text-fg-2">
              Nenhuma aprovação registrada que cubra {competencia.slice(5)}/{year}. Ela costuma vir
              depois do mês; a revalidação atualiza o controle quando chegar.
            </p>
          ) : (
            <ul className="mt-2 space-y-2 text-[13px]">
              {g.approvals.map((a) => (
                <li key={a.id}>
                  <span className="font-medium">{BODY[a.body] ?? a.body}</span> · {a.period} ·
                  aprovada em {formatDate(a.approved_on)}
                  {a.with_reservations ? " · com ressalvas" : ""} · {a.document ?? "documento"}
                  <span className="block text-fg-2">
                    {a.signatories
                      .map((s) => `${s.nome ?? ""} (${s.cargo ?? s.papel ?? ""})`)
                      .join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {g.can_edit && (
            <div className="mt-4 border-t border-line pt-3">
              <AccountsApprovalForm
                condominiumId={selected}
                competencia={competencia}
                board={g.board}
                documents={g.documents}
              />
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
