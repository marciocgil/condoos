"use client";

import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { send } from "@/lib/client";
import { SEVERITY_PLURAL } from "@/lib/labels";
import type { ReviewPolicy } from "@/lib/types";

const REQUIREMENT: Record<ReviewPolicy["rules"][number]["requirement"], string> = {
  none: "publicados direto ao corpo diretivo",
  qualified_review: "revisados por uma pessoa antes de publicar",
  internal_review: "revisados pela equipe CondoOS antes de apresentar",
  pending_evidence: "aguardam evidência",
};

function describe(rule: ReviewPolicy["rules"][number]): string {
  const what = rule.object === "opportunity" ? "Recomendações de economia" : "Achados";
  const sev = rule.match?.severity
    ?.map((s) => SEVERITY_PLURAL[s as keyof typeof SEVERITY_PLURAL] ?? s)
    .join(", ");
  const scope = sev ? ` ${sev}` : rule.object === "finding" ? " demais" : "";
  return `${what}${scope}: ${REQUIREMENT[rule.requirement]}.`;
}

/** Who reviews findings before the board sees them (D74). Read by everyone who configures;
 * the switch is for whoever holds ``configure_policy`` (síndico or CondoOS admin). */
export function ReviewPolicyCard({
  condominiumId,
  policy,
}: {
  condominiumId: string;
  policy: ReviewPolicy;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    const r = await send("PUT", `/condominiums/${condominiumId}/review-policy`, {
      management_company_reviews: !policy.management_company_reviews,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.refresh();
  }

  return (
    <Card>
      <CardTitle>Quem revisa os achados</CardTitle>
      <ul className="space-y-1 text-sm text-fg-2">
        {policy.rules.map((rule, i) => (
          <li key={i}>{describe(rule)}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">
        Política {policy.condominium_specific ? "própria do condomínio" : "padrão da plataforma"},
        versão {policy.version}. A revisão é feita pela equipe CondoOS
        {policy.has_management_company && policy.management_company_reviews
          ? " ou pelo gerente da administradora."
          : "."}
      </p>
      {policy.has_management_company && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
          <Badge
            tone={policy.management_company_reviews ? "success" : "neutral"}
            icon={<ShieldCheck size={12} />}
          >
            {policy.management_company_reviews
              ? "Administradora revisa achados"
              : "Administradora não revisa achados"}
          </Badge>
          {policy.can_configure ? (
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => void toggle()}>
              {policy.management_company_reviews
                ? "Retirar da administradora"
                : "Permitir à administradora"}
            </Button>
          ) : (
            <span className="text-xs text-muted">Decisão do síndico ou da equipe CondoOS.</span>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
