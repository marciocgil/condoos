import Link from "next/link";

import { apiGet } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { CondoMembership, Finding, Me } from "@/lib/types";

interface Row {
  condo: CondoMembership;
  atRisk: number;
  open: number;
  serious: number;
  pending: number;
}

const OPEN = new Set(["aguardando_validacao", "publicado"]);

export default async function CarteiraPage() {
  const me = await apiGet<Me>("/me");
  const rows: Row[] = await Promise.all(
    me.condominiums.map(async (condo) => {
      const findings = await apiGet<Finding[]>(`/condominiums/${condo.id}/findings`);
      const open = findings.filter((f) => OPEN.has(f.status));
      return {
        condo,
        atRisk: open.reduce((s, f) => s + Number(f.amount_at_risk), 0),
        open: open.length,
        serious: open.filter((f) => f.severity === "alta").length,
        pending: findings.filter((f) => f.status === "aguardando_validacao").length,
      };
    }),
  );
  rows.sort((a, b) => b.atRisk - a.atRisk);
  const total = rows.reduce((s, r) => s + r.atRisk, 0);
  const open = rows.reduce((s, r) => s + r.open, 0);
  const serious = rows.reduce((s, r) => s + r.serious, 0);

  return (
    <>
      <h1 className="text-2xl font-semibold">Carteira</h1>
      <section className="mt-6 grid grid-cols-3 gap-4" aria-label="Indicadores">
        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Valor em risco</p>
          <p className="mt-1 text-2xl font-semibold">{formatBRL(total)}</p>
        </div>
        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Achados abertos</p>
          <p className="mt-1 text-2xl font-semibold">
            {open} <span className="text-base font-normal text-sev-alta">· {serious} graves</span>
          </p>
        </div>
        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Itens na fila</p>
          <p className="mt-1 text-2xl font-semibold">0</p>
        </div>
      </section>

      <table className="mt-8 w-full overflow-hidden rounded-xl bg-white text-left text-sm shadow-sm">
        <thead className="bg-gray-50 text-gray-500">
          <tr>
            <th className="px-4 py-3 font-medium">Condomínio</th>
            <th className="px-4 py-3 font-medium">Em risco</th>
            <th className="px-4 py-3 font-medium">Achados</th>
            <th className="px-4 py-3 font-medium">Graves</th>
            <th className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((r) => (
            <tr key={r.condo.id}>
              <td className="px-4 py-3">
                <Link
                  href={`/condominio/${r.condo.id}/resumo`}
                  className="font-medium hover:underline"
                >
                  {r.condo.name}
                </Link>
              </td>
              <td className="px-4 py-3">{formatBRL(r.atRisk)}</td>
              <td className="px-4 py-3">{r.open}</td>
              <td className="px-4 py-3">{r.serious}</td>
              <td className="px-4 py-3">
                {r.pending > 0 ? (
                  <span className="rounded-full bg-orange-100 px-2 py-0.5 text-sev-alta">
                    Revisar
                  </span>
                ) : (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">Em dia</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
