import type { ReactNode } from "react";

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
  const condo = await apiGet<Condominium>(`/condominiums/${id}`);
  return (
    <div className="mx-auto min-h-dvh max-w-md pb-36">
      <header className="flex items-center justify-between px-4 pt-5 pb-2" data-condo={condo.slug}>
        <Logo />
        <LogoutButton className="text-[13px] text-fg-2 hover:text-fg" />
      </header>
      <main className="space-y-5 px-4 pt-3">{children}</main>
      <AskButton />
      <BottomTabs condominiumId={id} />
    </div>
  );
}
