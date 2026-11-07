"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

/** Records that the briefing was opened (VS-04: read receipt) and offers a refresh, which
 * creates a new version with what changed since this one. */
export function BriefingActions({
  condominiumId,
  briefingId,
  read,
}: {
  condominiumId: string;
  briefingId: string;
  read: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!read) void send("POST", `/condominiums/${condominiumId}/briefing/${briefingId}/read`);
  }, [condominiumId, briefingId, read]);
  return (
    <Button
      variant="ghost"
      size="sm"
      icon={<RefreshCw size={14} aria-hidden />}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await send("POST", `/condominiums/${condominiumId}/briefing/refresh`);
        setBusy(false);
        router.refresh();
      }}
    >
      Atualizar
    </Button>
  );
}
