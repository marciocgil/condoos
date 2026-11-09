import { ChevronLeft, Send, Target } from "lucide-react";
import Link from "next/link";

import { UploadForm } from "@/components/UploadForm";
import { apiGet } from "@/lib/api";
import type { Launch } from "@/lib/types";

export default async function EnviarPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ passo?: string }>;
}) {
  const { id } = await params;
  const { passo } = await searchParams;
  // The guide's step that led here (LB-080, D108): the screen says what was asked. Any file
  // is still accepted; a step already done simply shows no reminder.
  const step = passo
    ? (await apiGet<Launch>(`/condominiums/${id}/launch`)).next_steps.find((s) => s.key === passo)
    : undefined;
  return (
    <>
      <Link
        href={`/condominio/${id}/resumo`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Hoje
      </Link>
      <h1 className="text-xl font-semibold">Enviar documentos</h1>
      {step && (
        <div
          className="rounded-[var(--radius-card)] border border-line bg-surface p-3"
          data-testid="upload-step"
        >
          <p className="flex items-center gap-2 text-sm font-medium">
            <Target size={14} aria-hidden className="text-info" /> {step.label}
          </p>
          <p className="mt-1 text-[13px] text-fg-2">{step.why}</p>
        </div>
      )}
      <p className="text-sm text-fg-2">
        Você também pode encaminhar notas e boletos por e-mail para o endereço do condomínio.
      </p>
      <UploadForm condominiumId={id} />
      <Link
        href={`/condominio/${id}/pedidos/novo`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <Send size={14} aria-hidden /> Não está com você? Peça a quem tem os documentos
      </Link>
    </>
  );
}
