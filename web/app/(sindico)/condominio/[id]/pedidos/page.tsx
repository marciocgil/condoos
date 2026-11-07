import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { DelegationsPanel } from "@/components/condoos/DelegationsPanel";
import { apiGet } from "@/lib/api";
import type { Delegation, Me } from "@/lib/types";

/** Requests for documents to third parties (LF4, D97). */
export default async function PedidosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [requests, me] = await Promise.all([
    apiGet<Delegation[]>(`/condominiums/${id}/delegations`),
    apiGet<Me>("/me"),
  ]);
  const perms = me.condominiums.find((c) => c.id === id)?.permissions ?? [];
  return (
    <>
      <Link
        href={`/condominio/${id}/ajustes`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Ajustes
      </Link>
      <h1 className="text-xl font-semibold">Pedidos de documentos</h1>
      <p className="text-sm text-fg-2">
        Peça documentos à administradora, a um fornecedor ou ao zelador. Você autoriza, o CondoOS
        cria um link que só recebe arquivos, e você envia o texto pelo seu canal. Tudo o que chega
        passa por uma pessoa antes de ser usado.
      </p>
      <DelegationsPanel
        condominiumId={id}
        requests={requests}
        canManage={perms.includes("manage_cases")}
        canAuthorize={perms.includes("approve_in_condo")}
      />
    </>
  );
}
