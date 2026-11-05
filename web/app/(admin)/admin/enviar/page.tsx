import { AdminUpload } from "@/components/AdminUpload";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

export default async function AdminEnviarPage() {
  const me = await apiGet<Me>("/me");
  const condos = me.condominiums.filter((c) => c.permissions.includes("upload_document"));
  return (
    <>
      <h1 className="text-2xl font-semibold">Enviar documentos</h1>
      <p className="mt-1 text-sm text-gray-500">
        Escolha o condomínio e envie os arquivos do mês. Cada condomínio também recebe documentos
        por e-mail em <code>&lt;condomínio&gt;@ingest.condoos.local</code>.
      </p>
      <div className="mt-6 max-w-2xl">
        <AdminUpload condos={condos.map((c) => ({ id: c.id, name: c.name, slug: c.slug }))} />
      </div>
    </>
  );
}
