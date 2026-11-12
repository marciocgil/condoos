import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ExitConversation, ExitPending } from "@/components/condoos/ExitConversation";
import { apiGet } from "@/lib/api";
import type { ExitInfo } from "@/lib/exit";

/** Encerrar um condomínio (D129). */
export default async function EncerrarPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const info = await apiGet<ExitInfo>(`/condominiums/${id}/exit`);
  if (!info.can_exit) redirect("/");
  return (
    <>
      <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
        <ChevronLeft size={16} aria-hidden /> Início
      </Link>
      {info.pending ? <ExitPending info={info} /> : <ExitConversation info={info} />}
    </>
  );
}
