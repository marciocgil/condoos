import type { ReactNode } from "react";

import { AskButton } from "@/components/AskButton";
import { BottomTabs } from "@/components/BottomTabs";
import { LogoutButton } from "@/components/LogoutButton";
import { apiGet } from "@/lib/api";
import type { Condominium } from "@/lib/types";

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
    <div className="mx-auto min-h-dvh max-w-md pb-32">
      <header className="bg-brand-700 px-4 pt-6 pb-4 text-white">
        <div className="flex items-center justify-between">
          <p className="text-xs tracking-wide text-brand-100 uppercase">CondoOS</p>
          <LogoutButton className="text-xs text-brand-100 underline" />
        </div>
        <h1 className="mt-1 text-lg leading-tight font-semibold">{condo.name}</h1>
      </header>
      <main className="space-y-4 p-4">{children}</main>
      <AskButton />
      <BottomTabs condominiumId={id} />
    </div>
  );
}
