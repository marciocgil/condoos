import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { ComplianceList } from "@/components/condoos/ComplianceList";
import { apiGet } from "@/lib/api";
import type { ComplianceList as ComplianceListData } from "@/lib/types";

/** Compliance and expiry dates on the síndico's phone (D108), opened from Ajustes. */
export default async function ConformidadePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiGet<ComplianceListData>(`/condominiums/${id}/compliance`);
  return (
    <>
      <Link
        href={`/condominio/${id}/ajustes`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Ajustes
      </Link>
      <h1 className="text-xl font-semibold">Conformidade e vencimentos</h1>
      <ComplianceList
        condominiumId={id}
        data={data}
        detailBase={`/condominio/${id}/conformidade`}
      />
    </>
  );
}
