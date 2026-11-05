import { AdminUpload } from "@/components/AdminUpload";
import { PageHeader } from "@/components/layout/PageHeader";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

export default async function AdminEnviarPage() {
  const me = await apiGet<Me>("/me");
  const condos = me.condominiums.filter((c) => c.permissions.includes("upload_document"));
  return (
    <>
      <PageHeader
        title="Enviar documentos"
        subtitle="Escolha o condomínio e envie os arquivos do mês. Cada condomínio também recebe documentos por e-mail."
      />
      <div className="max-w-2xl">
        <AdminUpload condos={condos.map((c) => ({ id: c.id, name: c.name, slug: c.slug }))} />
      </div>
    </>
  );
}
