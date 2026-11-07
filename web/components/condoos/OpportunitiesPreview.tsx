import Link from "next/link";

import { CardTitle } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import type { OpportunityRow } from "@/lib/types";

import { OpportunityCards } from "./OpportunityCards";

/** Resumo card (D81): opportunities the CondoOS review approved, waiting for the síndico. */
export async function OpportunitiesPreview({ condominiumId }: { condominiumId: string }) {
  const rows = await apiGet<OpportunityRow[]>(`/condominiums/${condominiumId}/opportunities`);
  const waiting = rows.filter((r) => r.status === "aprovada_para_cliente");
  if (rows.length === 0) return null;
  const href = `/condominio/${condominiumId}/oportunidades`;
  return (
    <section aria-labelledby="opp-preview-title">
      <CardTitle
        action={
          <Link href={href} className="text-[13px] text-fg-2 hover:text-fg">
            Ver todas
          </Link>
        }
      >
        <span id="opp-preview-title">
          Oportunidades de economia
          {waiting.length > 0 && ` · ${waiting.length} aguardando sua decisão`}
        </span>
      </CardTitle>
      <OpportunityCards
        rows={(waiting.length > 0 ? waiting : rows).slice(0, 2)}
        hrefFor={(r) => `${href}/${r.id}`}
      />
    </section>
  );
}
