import { Plus } from "lucide-react";
import Link from "next/link";

import { buttonClass } from "@/components/ui/Button";
import { CardTitle } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import type { ActionRow } from "@/lib/types";

import { ActionCards } from "./ActionCards";

/** Actions of a condominium or of one case (D83), with the link to ask for a new one. */
export async function ActionsPreview({
  condominiumId,
  caseId,
  detailPath,
  listHref,
  newHref,
  title = "Aprovações",
}: {
  condominiumId: string;
  caseId?: string;
  detailPath: string;
  listHref?: string;
  newHref?: string;
  title?: string;
}) {
  const query = caseId ? `?situacao=todas&case_id=${caseId}` : "";
  const rows = await apiGet<ActionRow[]>(`/condominiums/${condominiumId}/actions${query}`);
  if (rows.length === 0 && !newHref) return null;
  const waiting = rows.filter((r) => r.status === "aguardando_aprovacao").length;
  return (
    <section aria-labelledby="actions-preview-title" className="space-y-2">
      <CardTitle
        action={
          listHref ? (
            <Link href={listHref} className="text-[13px] text-fg-2 hover:text-fg">
              Ver todas
            </Link>
          ) : undefined
        }
      >
        <span id="actions-preview-title">
          {title}
          {waiting > 0 && ` · ${waiting} aguardando aprovação`}
        </span>
      </CardTitle>
      {rows.length > 0 && <ActionCards rows={rows.slice(0, 3)} detailPath={detailPath} />}
      {newHref && (
        <Link href={newHref} className={buttonClass("secondary", "sm")}>
          <Plus size={14} aria-hidden /> Pedir ação com aprovação
        </Link>
      )}
    </section>
  );
}
