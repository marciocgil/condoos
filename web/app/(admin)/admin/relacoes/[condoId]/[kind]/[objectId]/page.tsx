import { notFound } from "next/navigation";

import { RelationsList, type Relations } from "@/components/condoos/RelationsList";
import { PageHeader } from "@/components/layout/PageHeader";
import { apiGet } from "@/lib/api";

const KIND_LABEL: Record<string, string> = {
  document: "Documento",
  contract: "Contrato",
  supplier: "Fornecedor",
};

/** Relations of a document, a contract or a supplier (FR-014, D126). */
export default async function RelationsPage({
  params,
}: {
  params: Promise<{ condoId: string; kind: string; objectId: string }>;
}) {
  const { condoId, kind, objectId } = await params;
  if (!(kind in KIND_LABEL)) notFound();
  const data = await apiGet<Relations>(`/condominiums/${condoId}/relations/${kind}/${objectId}`);
  return (
    <>
      <PageHeader
        title={data.object.label}
        subtitle={`${KIND_LABEL[kind]}: tudo o que está ligado a ele no CondoOS.`}
      />
      <div className="max-w-3xl">
        <RelationsList data={data} />
      </div>
    </>
  );
}
