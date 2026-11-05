import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { UploadForm } from "@/components/UploadForm";

export default async function EnviarPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <Link
        href={`/condominio/${id}/resumo`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Resumo
      </Link>
      <h1 className="text-xl font-semibold">Enviar documentos</h1>
      <p className="text-sm text-fg-2">
        Você também pode encaminhar notas e boletos por e-mail para o endereço do condomínio.
      </p>
      <UploadForm condominiumId={id} />
    </>
  );
}
