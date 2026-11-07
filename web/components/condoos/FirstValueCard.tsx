"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  GitCompare,
  Loader2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { FirstValue, FirstValueField } from "@/lib/types";

const POLL_MS = 2000;
const MAX_POLLS = 45;

const FIELD: Record<
  FirstValueField["status"],
  { tone: BadgeTone; icon: React.ReactNode; label: string }
> = {
  lido: { tone: "success", icon: <CheckCircle2 size={12} />, label: "Lido no documento" },
  a_confirmar: { tone: "warning", icon: <AlertTriangle size={12} />, label: "A confirmar" },
  nao_encontrado: { tone: "neutral", icon: <CircleHelp size={12} />, label: "Não encontrado" },
  conflitante: { tone: "danger", icon: <GitCompare size={12} />, label: "Conflitante" },
};

/** First-value card (LB-006/007, F01): follows the reading of an uploaded document and
 * shows what was read, with source and excerpt; uncertain fields are "a confirmar", never
 * facts; the limits of the reading are always stated. */
export function FirstValueCard({
  condominiumId,
  documentId,
  duplicate = false,
}: {
  condominiumId: string;
  documentId: string;
  duplicate?: boolean;
}) {
  const [card, setCard] = useState<FirstValue | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    let polls = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stop = false;
    async function load() {
      try {
        const res = await fetch(
          `/api/condominiums/${condominiumId}/documents/${documentId}/first-value`,
        );
        if (res.ok) {
          const data = (await res.json()) as FirstValue;
          if (stop) return;
          setCard(data);
          if (data.state !== "lendo") return;
        }
      } catch {
        // keep polling: a transient failure is not a result
      }
      polls += 1;
      if (polls >= MAX_POLLS) setGaveUp(true);
      else timer = setTimeout(load, POLL_MS);
    }
    void load();
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
    };
  }, [condominiumId, documentId]);

  if (!card || card.state === "lendo") {
    return (
      <Card aria-live="polite" data-testid="first-value">
        <p className="flex items-center gap-2 text-sm">
          <Loader2 size={16} aria-hidden className={gaveUp ? "" : "animate-spin"} />
          {gaveUp
            ? "A leitura está demorando. Você pode sair: o resultado fica em Contratos e no Hoje."
            : `Lendo ${card?.filename ?? "o documento"}…`}
        </p>
      </Card>
    );
  }

  return (
    <Card aria-live="polite" data-testid="first-value">
      <p className="text-[13px] break-all text-fg-2">{card.filename}</p>
      {duplicate && (
        <p className="mt-1 text-[13px] text-fg-2">
          Este arquivo já tinha sido recebido. Esta é a leitura guardada, sem novo processamento.
        </p>
      )}
      <p className="mt-1 flex items-start gap-2 text-sm font-medium">
        {card.state === "falhou" ? (
          <XCircle size={16} aria-hidden className="mt-0.5 shrink-0 text-danger" />
        ) : card.state === "parcial" ? (
          <AlertTriangle size={16} aria-hidden className="mt-0.5 shrink-0 text-warning" />
        ) : (
          <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0 text-success" />
        )}
        {card.message}
      </p>

      {card.fields && (
        <dl className="mt-4 space-y-3">
          {card.fields.map((f) => (
            <div key={f.name} data-testid={`field-${f.name}`}>
              <dt className="flex flex-wrap items-center gap-2 text-[13px] text-fg-2">
                {f.label}
                <Badge tone={FIELD[f.status].tone} icon={FIELD[f.status].icon}>
                  {FIELD[f.status].label}
                </Badge>
              </dt>
              <dd className="tabular mt-0.5 text-sm">{f.value ?? "—"}</dd>
              {f.evidence && (
                <dd className="mt-0.5 border-l-2 border-line pl-2 text-[13px] break-words text-fg-2">
                  {f.evidence.page ? `p. ${f.evidence.page}: ` : ""}“{f.evidence.excerpt}”
                </dd>
              )}
            </div>
          ))}
        </dl>
      )}

      {card.conflicts && card.conflicts.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <h3 className="flex items-center gap-2 text-[13px] font-medium text-fg-2">
            <GitCompare size={14} aria-hidden /> Divergência com outro documento
          </h3>
          <ul className="mt-1 space-y-1 text-[13px] text-fg-2">
            {card.conflicts.map((c) => (
              <li key={c.id}>
                <span className="text-fg">{c.title}.</span> {c.detail} A equipe CondoOS vai conferir
                qual versão vale.
              </li>
            ))}
          </ul>
        </div>
      )}

      {card.clauses && card.clauses.length > 0 && (
        <dl className="mt-4 space-y-2 border-t border-line pt-3">
          {card.clauses.map((c) => (
            <div key={c.label}>
              <dt className="text-[13px] text-fg-2">{c.label}</dt>
              <dd className="text-sm">{c.value}</dd>
              {c.evidence?.excerpt && (
                <dd className="text-[13px] break-words text-fg-2">“{c.evidence.excerpt}”</dd>
              )}
            </div>
          ))}
        </dl>
      )}

      {card.limits && card.limits.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <h3 className="text-[13px] font-medium text-fg-2">O que esta leitura não cobre</h3>
          <ul className="mt-1 list-disc pl-5 text-[13px] text-fg-2">
            {card.limits.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}

      {card.next_step && (
        <div className="mt-4">
          <p className="text-sm">{card.next_step.why}</p>
          <Link
            href={`/condominio/${condominiumId}/resumo`}
            className={`${buttonClass("secondary", "sm")} mt-2`}
          >
            Ver próximos passos
          </Link>
        </div>
      )}
    </Card>
  );
}
