import Link from "next/link";

import { UploadForm } from "@/components/UploadForm";

export default async function EnviarPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <Link href={`/condominio/${id}/resumo`} className="text-sm text-gray-600">
        ‹ Resumo
      </Link>
      <h2 className="text-lg font-semibold">Enviar documentos</h2>
      <p className="text-sm text-gray-600">
        Você também pode encaminhar notas e boletos por e-mail para o endereço do condomínio.
      </p>
      <UploadForm condominiumId={id} />
    </>
  );
}
