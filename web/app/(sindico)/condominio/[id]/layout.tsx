import { Settings } from "lucide-react";
import Link from "next/link";
import { type ReactNode, Suspense } from "react";

import { AskButton } from "@/components/AskButton";
import { BottomTabs } from "@/components/BottomTabs";
import { Logo } from "@/components/layout/Logo";
import { LogoutButton } from "@/components/LogoutButton";
import { apiGet } from "@/lib/api";
import type { Condominium } from "@/lib/types";

/** Mobile shell of the síndico (reference width 390 px), bottom tabs kept from the spec §8. */
export default async function SindicoLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [condo, chat] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    apiGet<{ available: boolean }>(`/condominiums/${id}/chat/status`),
  ]);
  return (
    <div className="mx-auto min-h-dvh max-w-md pb-36">
      <header className="flex items-center justify-between px-4 pt-5 pb-2" data-condo={condo.slug}>
        <Logo />
        <span className="flex items-center gap-4">
          <Link
            href={`/condominio/${id}/ajustes`}
            className="inline-flex items-center gap-1 text-[13px] text-fg-2 hover:text-fg"
          >
            <Settings size={14} aria-hidden /> Ajustes
          </Link>
          <LogoutButton className="text-[13px] text-fg-2 hover:text-fg" />
        </span>
      </header>
      <main className="space-y-5 px-4 pt-3">{children}</main>
      {/* Only when the chat can answer (LB-085, D108). */}
      {chat.available && (
        <Suspense fallback={null}>
          <AskButton condominiumId={id} />
        </Suspense>
      )}
      <BottomTabs condominiumId={id} />
    </div>
  );
}
