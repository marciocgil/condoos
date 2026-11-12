import { CheckCircle2, ChevronLeft, Circle } from "lucide-react";
import Link from "next/link";

import { ImplantationAction } from "@/components/condoos/ImplantationActions";
import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { apiGet } from "@/lib/api";
import type { Implantation, ImplantationItem } from "@/lib/implantation";

function Act({ id, item }: { id: string; item: ImplantationItem }) {
  if (item.action === "enviar")
    return (
      <Link href={`/condominio/${id}/enviar`} className={buttonClass("primary")}>
        Enviar documentos
      </Link>
    );
  return <ImplantationAction condominiumId={id} action={item.action} />;
}

/** Continuing an implantation (D128): the percentage with its count, the next step first and
 * the eight items. 100% = "apto a operar". */
export default async function ImplantacaoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const imp = await apiGet<Implantation>(`/condominiums/${id}/implantation`);
  return (
    <>
      <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
        <ChevronLeft size={16} aria-hidden /> Início
      </Link>
      <div>
        <p className="text-[13px] text-fg-2">Implantação</p>
        <h1 className="text-[22px] leading-tight font-semibold">{imp.condominium.name}</h1>
      </div>
      <div className="grid gap-1.5" data-testid="implantation-progress">
        <div className="flex items-baseline justify-between">
          <strong className="text-lg">{imp.percent}%</strong>
          <span className="text-[13px] text-fg-2">
            {imp.done} de {imp.total} itens
          </span>
        </div>
        <span className="h-2 overflow-hidden rounded-full bg-elevated">
          <span
            className="block h-full rounded-full bg-success"
            style={{ width: `${imp.percent}%` }}
          />
        </span>
      </div>
      {imp.complete ? (
        <section className="grid gap-2 rounded-[var(--radius-card)] bg-surface p-4">
          <Badge tone="success" icon={<CheckCircle2 size={12} aria-hidden />}>
            Apto a operar
          </Badge>
          <p className="text-sm">Tudo pronto. Daqui em diante é o dia a dia.</p>
          <Link href={`/dia-a-dia/${id}`} className={buttonClass("primary")}>
            Ir para o dia a dia
          </Link>
        </section>
      ) : (
        imp.next && (
          <section
            className="grid gap-2 rounded-[var(--radius-card)] bg-surface p-4"
            data-testid="implantation-next"
          >
            <span className="text-[12px] text-fg-2">Próximo passo</span>
            <strong>{imp.next.title}</strong>
            <span className="text-[13px] text-fg-2">{imp.next.why}</span>
            {imp.can_manage && <Act id={id} item={imp.next} />}
          </section>
        )
      )}
      <ul className="grid">
        {imp.items.map((i) => (
          <li
            key={i.key}
            className="grid grid-cols-[20px_1fr_auto] items-start gap-2 border-t border-line py-2.5 first:border-0"
          >
            {i.done ? (
              <CheckCircle2 size={18} aria-hidden className="text-success" />
            ) : (
              <Circle size={18} aria-hidden className="text-muted" />
            )}
            <span className="min-w-0">
              <span className="block text-sm font-medium">{i.title}</span>
              <span className="block text-[12.5px] text-fg-2">{i.detail}</span>
            </span>
            {!i.done && <Badge tone="warning">falta</Badge>}
          </li>
        ))}
      </ul>
      <p className="text-[12.5px] text-muted">
        Recomendado:{" "}
        {imp.recommended.map((r) => `${r.title}${r.done ? " (feito)" : ""}`).join(" · ")}. Não trava
        nada; deixa o farol mais completo.
      </p>
    </>
  );
}
