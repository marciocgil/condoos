import { Logo } from "@/components/layout/Logo";
import { PublicUpload } from "@/components/condoos/PublicUpload";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { PublicDelegation } from "@/lib/types";

/** Public send-only page of a delegation link (LF4, D97). No account; any invalid, expired
 * or revoked link is "not found". Shows what was asked, never data of the condominium. */
export default async function EnviarDocumentosPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const req = await apiGet<PublicDelegation>(`/submit/${encodeURIComponent(token)}`);
  return (
    <main className="mx-auto max-w-md space-y-4 px-4 py-6">
      <Logo />
      <h1 className="text-xl font-semibold">Envio de documentos</h1>
      <Card>
        <p className="text-sm">
          <strong>{req.condominium}</strong> pede a <strong>{req.recipient_name}</strong>:
        </p>
        <p className="mt-1 text-sm text-fg-2">{req.scope}</p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          {req.items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
        <p className="mt-3 text-[13px] text-muted">
          {req.due_date ? `Prazo: ${formatDate(req.due_date)} · ` : ""}Este link vale até{" "}
          {formatDate(req.expires_at)} e só recebe arquivos (PDF, foto ou XML de nota fiscal).
        </p>
      </Card>
      <PublicUpload token={token} />
    </main>
  );
}
