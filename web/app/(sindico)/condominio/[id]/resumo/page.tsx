import { MonthSelect } from "@/components/MonthSelect";
import { apiGet } from "@/lib/api";
import { competenceParam, formatBRL } from "@/lib/format";
import type { Competence, Expense, Finding } from "@/lib/types";

const SEVERITY = [
  { key: "alta", label: "Graves", dot: "bg-sev-alta" },
  { key: "media", label: "Médios", dot: "bg-sev-media" },
  { key: "baixa", label: "Baixos", dot: "bg-sev-baixa" },
] as const;

export default async function ResumoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ mes?: string }>;
}) {
  const { id } = await params;
  const { mes } = await searchParams;
  const competences = await apiGet<Competence[]>(`/condominiums/${id}/competences`);
  // Default: the most recent closed month.
  const selected =
    competences.find((c) => mes && c.month.startsWith(mes)) ??
    competences.find((c) => c.status === "fechada") ??
    competences[0];

  if (!selected) {
    return <p className="text-gray-600">Ainda não há meses processados para este condomínio.</p>;
  }

  const month = competenceParam(selected.month);
  const [findings, expenses] = await Promise.all([
    apiGet<Finding[]>(`/condominiums/${id}/findings?competence=${month}`),
    apiGet<Expense[]>(`/condominiums/${id}/expenses?competence=${month}`),
  ]);
  const atRisk = findings.reduce((sum, f) => sum + Number(f.amount_at_risk), 0);
  const spent = expenses.reduce((sum, e) => sum + Number(e.amount), 0);
  const count = (sev: string) => findings.filter((f) => f.severity === sev).length;
  const top = [...findings]
    .sort((a, b) => Number(b.amount_at_risk) - Number(a.amount_at_risk))
    .slice(0, 3);

  return (
    <>
      <MonthSelect competences={competences} value={selected.month} />

      <section className="rounded-xl bg-white p-5 shadow-sm" aria-label="Destaque do mês">
        <p className="text-sm text-gray-500">Valor em risco</p>
        <p className="mt-1 text-3xl font-semibold" data-testid="amount-at-risk">
          {formatBRL(atRisk)}
        </p>
        <p className="mt-2 text-sm text-gray-600">
          {findings.length} {findings.length === 1 ? "achado" : "achados"} · {count("alta")}{" "}
          {count("alta") === 1 ? "grave" : "graves"}
        </p>
        <p className="mt-3 border-t border-gray-100 pt-3 text-sm text-gray-500">
          {expenses.length} despesas analisadas · {formatBRL(spent)}
        </p>
      </section>

      <ul className="flex gap-2" aria-label="Achados por severidade">
        {SEVERITY.map((s) => (
          <li key={s.key}>
            <a
              href={`/condominio/${id}/achados?severidade=${s.key}`}
              className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-sm"
            >
              <span className={`h-2 w-2 rounded-full ${s.dot}`} aria-hidden />
              {count(s.key)} {s.label.toLowerCase()}
            </a>
          </li>
        ))}
      </ul>

      <section className="rounded-xl bg-white p-5 shadow-sm">
        <h2 className="font-semibold">Principais achados</h2>
        {top.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">Nenhum ponto de atenção neste mês.</p>
        ) : (
          <ul className="mt-3 divide-y divide-gray-100">
            {top.map((f) => (
              <li key={f.id} className="flex items-start gap-3 py-3">
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                    SEVERITY.find((s) => s.key === f.severity)?.dot ?? "bg-gray-400"
                  }`}
                  aria-hidden
                />
                <span className="flex-1 text-sm">{f.title}</span>
                <span className="text-sm font-medium">{formatBRL(f.amount_at_risk)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <a
        href={`/condominio/${id}/enviar`}
        className="block w-full rounded-lg border border-brand-600 bg-white px-4 py-3 text-center text-sm font-medium text-brand-700"
      >
        Enviar documentos
      </a>

      <button
        type="button"
        disabled
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-500"
        title="O relatório em PDF chega no Marco 5"
      >
        Baixar relatório em PDF
      </button>
    </>
  );
}
