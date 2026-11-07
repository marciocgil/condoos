"use client";

import { PiggyBank } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

/** CondoOS team: turn an R02/R03 finding into an opportunity (computed by code, D81). */
export function GenerateOpportunity({
  condominiumId,
  findingId,
  detailPath,
}: {
  condominiumId: string;
  findingId: string;
  detailPath: string; // "{id}" is replaced by the new opportunity
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="space-y-1">
      <Button
        size="sm"
        icon={<PiggyBank size={14} aria-hidden />}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          const r = await send<{ id: string }>(
            "POST",
            `/condominiums/${condominiumId}/opportunities`,
            {
              finding_id: findingId,
            },
          );
          setBusy(false);
          if (!r.ok) return setError(r.error);
          router.push(detailPath.replace("{id}", r.data.id));
        }}
      >
        Gerar oportunidade
      </Button>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
