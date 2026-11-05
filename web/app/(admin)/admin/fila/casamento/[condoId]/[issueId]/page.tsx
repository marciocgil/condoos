import Link from "next/link";

import { ResolveForm } from "@/components/ResolveForm";
import { apiGet } from "@/lib/api";
import type { MatchIssue } from "@/lib/types";

export default async function MatchIssuePage({
  params,
}: {
  params: Promise<{ condoId: string; issueId: string }>;
}) {
  const { condoId, issueId } = await params;
  const issue = await apiGet<MatchIssue>(`/condominiums/${condoId}/match-issues/${issueId}`);
  return (
    <>
      <Link href="/admin/fila" className="text-sm text-gray-600">
        ‹ Fila de exceções
      </Link>
      <h1 className="mt-1 text-xl font-semibold">{issue.description}</h1>
      <p className="mt-1 text-sm text-gray-500">
        O sistema nunca escolhe entre opções equivalentes. Indique a correta.
      </p>
      <div className="mt-6 max-w-2xl">
        <ResolveForm condominiumId={condoId} issue={issue} />
      </div>
    </>
  );
}
