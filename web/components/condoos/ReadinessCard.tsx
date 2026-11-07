import { AlertTriangle, CheckCircle2, Circle, XCircle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import type { LaunchReadiness, ReadinessState } from "@/lib/types";

function StateBadge({ state, label }: { state: ReadinessState; label: string }) {
  if (state === "supervisionada")
    return (
      <Badge tone="success" icon={<CheckCircle2 size={12} />}>
        {label}
      </Badge>
    );
  if (state === "analise_parcial")
    return (
      <Badge tone="warning" icon={<AlertTriangle size={12} />}>
        {label}
      </Badge>
    );
  return (
    <Badge tone="neutral" icon={<Circle size={12} />}>
      {label}
    </Badge>
  );
}

/** Readiness per capability (LB-011, D92): what each capability can do with the data the
 * condominium has now and what is missing. Requirements are yes or no; nothing here is a
 * score. ``resolve`` maps a requirement to the screen that fixes it, when a person can. */
export function ReadinessCard({
  readiness,
  resolve,
}: {
  readiness: LaunchReadiness[];
  resolve: Partial<Record<string, { href: string; label: string }>>;
}) {
  return (
    <Card aria-labelledby="readiness-title" data-testid="readiness">
      <CardTitle>
        <span id="readiness-title">O que o CondoOS já consegue fazer</span>
      </CardTitle>
      <ul className="divide-y divide-line">
        {readiness.map((cap) => {
          const missing = cap.requirements.filter((r) => !r.met);
          return (
            <li key={cap.capability} className="py-3" data-capability={cap.capability}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{cap.name}</span>
                <StateBadge state={cap.state} label={cap.state_label} />
              </div>
              {missing.length > 0 && (
                <ul className="mt-2 space-y-1.5 text-[13px]">
                  {missing.map((r) => {
                    const fix = resolve[r.key];
                    return (
                      <li key={r.key} className="flex items-start gap-2">
                        <XCircle size={14} aria-hidden className="mt-0.5 shrink-0 text-muted" />
                        <span>
                          <span className="text-fg-2">Falta: {r.label}</span>
                          {r.detail && <span className="block text-muted">{r.detail}</span>}
                          {fix && (
                            <Link href={fix.href} className="mt-0.5 inline-block text-fg underline">
                              {fix.label}
                            </Link>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
