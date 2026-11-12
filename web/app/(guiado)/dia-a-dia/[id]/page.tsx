import { CheckCircle2, ChevronLeft, ChevronRight, Circle, Clock, Flag } from "lucide-react";
import Link from "next/link";

import { UploadForm } from "@/components/UploadForm";
import { Badge } from "@/components/ui/Badge";
import { apiGet } from "@/lib/api";
import { type DayToDay, monthTitle, sindicoCondos } from "@/lib/daytoday";
import type { ExitInfo } from "@/lib/exit";
import { formatDate } from "@/lib/format";
import type { Me } from "@/lib/types";

/** Day to day of one condominium (D127): send the month, see what arrived, the farol and the
 * points of attention. Everything else stays one tap away ("Ver tudo deste condomínio"). */
export default async function DiaADiaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [me, day, exit] = await Promise.all([
    apiGet<Me>("/me"),
    apiGet<DayToDay>(`/condominiums/${id}/day`),
    apiGet<ExitInfo>(`/condominiums/${id}/exit`),
  ]);
  const many = sindicoCondos(me).length > 1;
  const f = day.farol;
  return (
    <>
      {many && (
        <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
          <ChevronLeft size={16} aria-hidden /> Início
        </Link>
      )}
      <div>
        <p className="text-[13px] text-fg-2">Dia a dia</p>
        <h1 className="text-[22px] leading-tight font-semibold">
          {day.condominium.name} · {day.month_label}
        </h1>
      </div>
      {exit.pending && (
        <Link
          href={`/encerrar/${id}`}
          className="rounded-[var(--radius-card)] border border-line p-3 text-[13px] text-fg-2"
          data-testid="day-exit-pending"
        >
          Sua saída está marcada para {formatDate(exit.pending.on)}. Ver ou desfazer ›
        </Link>
      )}

      {day.can_upload && (
        <section aria-labelledby="send" className="grid gap-2" data-testid="day-upload">
          <h2 id="send" className="text-[15px] font-semibold">
            Enviar as contas de {day.month_label}
          </h2>
          <p className="text-[13px] text-fg-2">
            Notas, boletos, propostas aprovadas, comprovantes e o extrato. Pode mandar tudo junto:
            eu separo cada um.
          </p>
          <UploadForm condominiumId={id} />
        </section>
      )}

      <section
        aria-labelledby="arrived"
        className="grid gap-1 rounded-[var(--radius-card)] bg-surface p-4"
        data-testid="day-checklist"
      >
        <h2 id="arrived" className="text-[15px] font-semibold">
          O que já chegou
        </h2>
        <ul>
          {day.checklist.map((i) => (
            <li
              key={i.key}
              className="grid grid-cols-[20px_1fr_auto] items-start gap-2 border-t border-line py-2 first:border-0"
            >
              {i.status === "ok" ? (
                <CheckCircle2 size={18} aria-hidden className="text-success" />
              ) : (
                <Circle size={18} aria-hidden className="text-muted" />
              )}
              <span className="min-w-0">
                <span className="block text-sm font-medium">{i.title}</span>
                <span className="block text-[12.5px] text-fg-2">{i.detail}</span>
              </span>
              {i.status === "falta" && <Badge tone="warning">falta</Badge>}
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="farol"
        className="grid gap-2 rounded-[var(--radius-card)] bg-surface p-4"
        data-testid="day-farol"
      >
        <div className="flex items-center justify-between gap-2">
          <h2 id="farol" className="text-[15px] font-semibold">
            {f.last_approved ? `Farol de ${monthTitle(f.last_approved.competencia)}` : "Farol"}
          </h2>
          {f.last_approved && (
            <Badge tone="success" icon={<CheckCircle2 size={12} aria-hidden />}>
              Aprovado por você
            </Badge>
          )}
        </div>
        {f.last_approved ? (
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              ["Validado", f.last_approved.validados],
              ["Com ressalva", f.last_approved.ressalvas],
              ["Pendente", f.last_approved.pendentes + f.last_approved.divergentes],
            ].map(([label, n]) => (
              <div key={label} className="rounded-[10px] bg-elevated p-2">
                <strong className="block text-xl">{n}</strong>
                <span className="text-[11px] text-fg-2">{label}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-fg-2">
            O primeiro farol aparece aqui depois que a equipe CondoOS revisar o mês e você aprovar.
          </p>
        )}
        {f.waiting_for_you ? (
          <Link
            href={`/condominio/${id}/auditoria`}
            className="inline-flex items-center gap-1 text-sm font-medium text-fg underline-offset-2 hover:underline"
          >
            Um farol aguarda a sua aprovação <ChevronRight size={14} aria-hidden />
          </Link>
        ) : (
          f.in_review && (
            <p className="inline-flex items-center gap-1 text-[13px] text-fg-2">
              <Clock size={14} aria-hidden />
              {day.month_label.charAt(0).toUpperCase() + day.month_label.slice(1)} está em
              conferência pela equipe CondoOS.
            </p>
          )
        )}
        {f.last_approved && (
          <Link
            href={`/condominio/${id}/auditoria`}
            className="text-[13px] text-fg-2 underline-offset-2 hover:underline"
          >
            Ver o farol completo
          </Link>
        )}
      </section>

      {day.attention.count > 0 && (
        <Link
          href={`/condominio/${id}/achados`}
          className="grid grid-cols-[36px_1fr_16px] items-center gap-3 rounded-[var(--radius-card)] border border-line p-4"
          data-testid="day-attention"
        >
          <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-elevated">
            <Flag size={18} aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-[15px] font-semibold">
              {day.attention.count} ponto(s) de atenção
            </span>
            <span className="block truncate text-[12.5px] text-fg-2">
              {day.attention.items.map((i) => i.title).join(" · ")}
            </span>
          </span>
          <ChevronRight size={16} aria-hidden className="text-muted" />
        </Link>
      )}

      <Link
        href={`/condominio/${id}/resumo`}
        className="justify-self-center text-[13px] text-fg-2 underline-offset-2 hover:underline"
      >
        Ver tudo deste condomínio
      </Link>
    </>
  );
}
