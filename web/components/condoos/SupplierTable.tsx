"use client";

import Link from "next/link";

import { Store } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { SidePanel } from "@/components/ui/SidePanel";
import { formatBRL, formatBRLShort } from "@/lib/format";
import type { SupplierRow } from "@/lib/types";

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <Badge tone="neutral">Sem consulta</Badge>;
  return status === "ATIVA" ? (
    <Badge tone="success">Ativa</Badge>
  ) : (
    <Badge tone="danger">{status.toLowerCase()}</Badge>
  );
}

/** Consolidated suppliers; a row opens the side panel without leaving the list (DS §5.7). */
export function SupplierTable({
  rows,
  condominiumId = null,
}: {
  rows: SupplierRow[];
  // With one condominium chosen, each supplier links to its relations there (FR-014).
  condominiumId?: string | null;
}) {
  const [selected, setSelected] = useState<SupplierRow | null>(null);
  return (
    <>
      <div className="overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Fornecedores da carteira</caption>
          <thead className="border-b border-line text-[12px] text-fg-2">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Fornecedor
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Situação
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Condomínios
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Pago em 12 meses
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Achados abertos
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.id} className="transition-ui hover:bg-elevated/60">
                <td className="px-4 py-3">
                  <button
                    type="button"
                    className="text-left font-medium hover:text-accent"
                    onClick={() => setSelected(r)}
                  >
                    {r.name}
                  </button>
                  <p className="tabular text-xs text-muted">{r.cnpj}</p>
                  {condominiumId && (
                    <Link
                      href={`/admin/relacoes/${condominiumId}/supplier/${r.id}`}
                      className="text-xs text-fg-2 underline-offset-2 hover:underline"
                    >
                      Relações neste condomínio
                    </Link>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={r.registration_status} />
                </td>
                <td className="px-4 py-3">{r.condominiums.length}</td>
                <td className="tabular px-4 py-3 text-right">{formatBRLShort(r.total_paid_12m)}</td>
                <td className="tabular px-4 py-3 text-right">
                  {r.open_findings > 0 ? (
                    <span className="text-warning">{r.open_findings}</span>
                  ) : (
                    0
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SidePanel
        open={selected !== null}
        title={selected?.name ?? "Fornecedor"}
        onClose={() => setSelected(null)}
      >
        {selected && (
          <dl className="space-y-4 text-sm">
            <div>
              <dt className="text-muted">CNPJ</dt>
              <dd className="tabular">{selected.cnpj}</dd>
            </div>
            <div>
              <dt className="text-muted">Situação na Receita Federal</dt>
              <dd>
                <StatusBadge status={selected.registration_status} />
              </dd>
            </div>
            <div>
              <dt className="text-muted">Condomínios atendidos</dt>
              <dd>
                <ul className="mt-1 space-y-1">
                  {selected.condominiums.map((c) => (
                    <li key={c} className="inline-flex items-center gap-2">
                      <Store size={14} aria-hidden className="text-fg-2" />
                      {c}
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
            <div>
              <dt className="text-muted">Pago nos últimos 12 meses</dt>
              <dd className="tabular">{formatBRL(selected.total_paid_12m)}</dd>
            </div>
            <div>
              <dt className="text-muted">Achados abertos</dt>
              <dd className="tabular">
                {selected.open_findings} · {formatBRL(selected.amount_at_risk)} em risco
              </dd>
            </div>
          </dl>
        )}
      </SidePanel>
    </>
  );
}
