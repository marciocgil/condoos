"use client";

import { Clock, Sprout } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { send } from "@/lib/client";
import type { EvolutionSuggestion } from "@/lib/types";

/** Centro de Evolução (LB-063, D110): at most three suggestions, each only when the data
 * already shows the demand. ``base`` is where relative links lead (the síndico's screens);
 * absolute links (starting with "/") are used as they are. */
export function EvolutionCard({
  condominiumId,
  items,
  canManage,
  base,
}: {
  condominiumId: string;
  items: EvolutionSuggestion[];
  canManage: boolean;
  base: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  if (items.length === 0) return null;

  async function later(key: string) {
    setBusy(true);
    await send("POST", `/condominiums/${condominiumId}/launch/postpone`, { step: `evo:${key}` });
    setBusy(false);
    router.refresh();
  }

  return (
    <Card aria-labelledby="evolution-title" data-testid="evolution-card">
      <CardTitle>
        <span id="evolution-title" className="inline-flex items-center gap-2">
          <Sprout size={16} aria-hidden className="text-info" /> Para evoluir
        </span>
      </CardTitle>
      <ul className="space-y-4">
        {items.map((s) => (
          <li key={s.key} data-testid={`evolution-${s.key}`}>
            <p className="text-sm">{s.observed}</p>
            <p className="text-[13px] text-fg-2">{s.gain}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {s.action && (
                <Link
                  href={s.action.href.startsWith("/") ? s.action.href : `${base}/${s.action.href}`}
                  className={buttonClass("secondary", "sm")}
                >
                  {s.action.label}
                </Link>
              )}
              {canManage && (
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Clock size={14} aria-hidden />}
                  disabled={busy}
                  onClick={() => void later(s.key)}
                >
                  Agora não
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[12px] text-muted">
        Sugestões a partir do que já chegou ao CondoOS. Nada muda sem a sua decisão.
      </p>
    </Card>
  );
}
