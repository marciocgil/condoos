import { Card, CardTitle } from "@/components/ui/Card";
import type { CalcLine } from "@/lib/types";

const LABEL: Record<string, string> = {
  unidade: "Unidade",
  saldo_inicial: "Saldo inicial",
  emitidos: "Emitidos",
  pagos: "Pagos",
  cancelados: "Cancelados",
  saldo_final: "Saldo final",
  fechamento_anterior: "Fechamento anterior",
  servico: "Serviço",
  consumo: "Consumo",
  cobrado: "Cobrado",
  calculado: "Calculado",
  diferenca: "Diferença",
  nota: "Nota",
  retencoes: "Retenções",
  parcelamento: "Parcelamento",
  competencia: "Competência",
  parcela: "Parcela",
  valor: "Valor",
  paga: "Paga",
};

const ORDER = Object.keys(LABEL);

/** Columns in a fixed order (the database does not keep the order of JSON keys). */
function columns(row: Record<string, unknown>): string[] {
  const keys = Object.keys(row);
  return [...ORDER.filter((k) => keys.includes(k)), ...keys.filter((k) => !ORDER.includes(k))];
}

function cell(v: string | boolean | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "sim" : "não";
  return v;
}

/** Calculation memory of a control (D123): every number with its formula, and the rows per
 * item. Unit rows carry the unit code only, never a resident's name. */
export function CalculationMemory({ lines }: { lines: CalcLine[] }) {
  if (!lines.length) return null;
  return (
    <Card data-testid="calculation">
      <CardTitle>Memória de cálculo</CardTitle>
      <div className="mt-2 space-y-3 text-sm">
        {lines.map((l, i) => (
          <div key={`${l.label}-${i}`}>
            <p>
              <span className="font-medium">{l.label}</span>
              {l.value ? `: ${l.value}` : ""}
              {l.formula && <span className="block text-[13px] text-fg-2">{l.formula}</span>}
            </p>
            {l.rows && l.rows.length > 0 && (
              <div className="mt-1 max-h-[360px] overflow-auto">
                <table className="w-full text-[13px]">
                  <thead className="text-left text-fg-2">
                    <tr>
                      {columns(l.rows[0]!).map((k) => (
                        <th key={k} className="py-1 pr-3">
                          {LABEL[k] ?? k}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {l.rows.map((r, j) => (
                      <tr key={j} className="border-t border-line">
                        {columns(l.rows![0]!).map((k) => (
                          <td key={k} className="tabular py-1 pr-3">
                            {cell(r[k])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
