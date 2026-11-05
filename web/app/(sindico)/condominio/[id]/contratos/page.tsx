import { apiGet } from "@/lib/api";
import { formatBRL, formatDate } from "@/lib/format";
import type { Contract } from "@/lib/types";

const INDEX_LABEL: Record<string, string> = {
  IPCA: "IPCA",
  IGPM: "IGP-M",
  INPC: "INPC",
  FIXO: "Valor fixo",
  NENHUM: "Sem reajuste",
};

function nextAdjustment(baseMonth: number | null, today: Date): string | null {
  if (!baseMonth) return null;
  const year = baseMonth > today.getMonth() + 1 ? today.getFullYear() : today.getFullYear() + 1;
  return `${String(baseMonth).padStart(2, "0")}/${year}`;
}

function daysUntil(iso: string, today: Date): number {
  const end = new Date(`${iso}T00:00:00`);
  return Math.ceil((end.getTime() - today.getTime()) / 86_400_000);
}

export default async function ContratosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const contracts = await apiGet<Contract[]>(`/condominiums/${id}/contracts`);
  const today = new Date();

  return (
    <section aria-label="Contratos">
      <h2 className="mb-3 font-semibold">Contratos</h2>
      <ul className="space-y-3">
        {contracts.map((c) => {
          const days = c.end_date ? daysUntil(c.end_date, today) : null;
          const expiring = days !== null && days >= 0 && days <= 60;
          const expired = days !== null && days < 0;
          return (
            <li
              key={c.id}
              className={`rounded-xl bg-white p-4 shadow-sm ${
                expiring || expired ? "ring-2 ring-sev-media" : ""
              }`}
            >
              <p className="font-medium">{c.supplier_name}</p>
              <p className="text-sm text-gray-600">{c.object}</p>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <dt className="text-gray-500">Valor mensal</dt>
                  <dd>{formatBRL(c.monthly_value)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Índice</dt>
                  <dd>{INDEX_LABEL[c.adjustment_index] ?? c.adjustment_index}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Próximo reajuste</dt>
                  <dd>{nextAdjustment(c.adjustment_base_month, today) ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Fim da vigência</dt>
                  <dd>{c.end_date ? formatDate(c.end_date) : "Indeterminado"}</dd>
                </div>
              </dl>
              {expiring && (
                <p className="mt-2 text-sm font-medium text-sev-media">
                  Vence em {days} {days === 1 ? "dia" : "dias"}
                </p>
              )}
              {expired && (
                <p className="mt-2 text-sm font-medium text-sev-alta">Contrato vencido</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
