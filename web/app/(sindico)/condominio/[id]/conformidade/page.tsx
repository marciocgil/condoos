import { ComplianceList } from "@/components/condoos/ComplianceList";
import { apiGet } from "@/lib/api";
import type { ComplianceList as ComplianceListData } from "@/lib/types";

/** Compliance and expiry dates on the síndico's phone (D108), a section of the Rotina tab (D111). */
export default async function ConformidadePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiGet<ComplianceListData>(`/condominiums/${id}/compliance`);
  return (
    <>
      <h1 className="text-xl font-semibold">Conformidade e vencimentos</h1>
      <ComplianceList
        condominiumId={id}
        data={data}
        detailBase={`/condominio/${id}/conformidade`}
      />
    </>
  );
}
