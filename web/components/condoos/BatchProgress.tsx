"use client";

import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";

type State = "lendo" | "lido" | "a_conferir" | "falhou";

interface BatchStatus {
  items: {
    id: string;
    filename: string;
    doc_type_label: string;
    state: State;
    reasons: string[];
  }[];
  totals: Record<State, number>;
  done: boolean;
}

const STATE: Record<State, { label: string; tone: BadgeTone; icon: React.ReactNode }> = {
  lendo: { label: "Lendo", tone: "neutral", icon: <Loader2 size={12} /> },
  lido: { label: "Lido", tone: "success", icon: <CheckCircle2 size={12} /> },
  a_conferir: {
    label: "A conferir pela equipe",
    tone: "warning",
    icon: <AlertTriangle size={12} />,
  },
  falhou: { label: "Não consegui ler", tone: "danger", icon: <XCircle size={12} /> },
};
const POLL_MS = 2500;
const MAX_POLLS = 60;

/** "Faça por mim" (LB-033, D94): the CondoOS reads a whole batch and shows, file by file,
 * what it read, what goes to the team to check and what failed. Nothing is typed. */
export function BatchProgress({
  condominiumId,
  documentIds,
}: {
  condominiumId: string;
  documentIds: string[];
}) {
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const key = documentIds.join(",");

  useEffect(() => {
    let polls = 0;
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const query = key
      .split(",")
      .map((id) => `ids=${encodeURIComponent(id)}`)
      .join("&");
    async function load() {
      try {
        const res = await fetch(`/api/condominiums/${condominiumId}/documents-status?${query}`);
        if (res.ok) {
          const data = (await res.json()) as BatchStatus;
          if (stop) return;
          setStatus(data);
          if (data.done) return;
        }
      } catch {
        // a transient failure is not a result: keep following
      }
      polls += 1;
      if (polls < MAX_POLLS) timer = setTimeout(load, POLL_MS);
    }
    void load();
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
    };
  }, [condominiumId, key]);

  const t = status?.totals;
  return (
    <Card aria-live="polite" data-testid="batch-progress">
      <CardTitle>
        <span>Leitura do lote</span>
      </CardTitle>
      {t ? (
        <p className="text-sm">
          {t.lido} lido(s) · {t.a_conferir} a conferir · {t.falhou} com falha
          {t.lendo ? ` · ${t.lendo} em leitura` : " · leitura concluída"}
        </p>
      ) : (
        <p className="text-sm text-fg-2">Acompanhando a leitura…</p>
      )}
      {status && (
        <ul className="mt-3 divide-y divide-line text-sm" aria-label="Arquivos do lote">
          {status.items.map((i) => (
            <li key={i.id} className="flex items-start justify-between gap-3 py-2">
              <span className="min-w-0">
                <span className="block break-all">{i.filename}</span>
                <span className="block text-[13px] text-fg-2">
                  {i.doc_type_label}
                  {i.reasons.length > 0 ? ` · ${i.reasons[0]}` : ""}
                </span>
              </span>
              <Badge tone={STATE[i.state].tone} icon={STATE[i.state].icon}>
                {STATE[i.state].label}
              </Badge>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[12px] text-muted">
        O que estiver “a conferir” vai para a equipe CondoOS; você não precisa digitar nada.
      </p>
    </Card>
  );
}
