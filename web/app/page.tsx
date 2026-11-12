import { redirect } from "next/navigation";

import { apiGet } from "@/lib/api";
import { type DayToDay, sindicoCondos } from "@/lib/daytoday";
import type { Me } from "@/lib/types";

/** Entry point: send each user to the right home for their role. */
export default async function Home() {
  const me = await apiGet<Me>("/me");
  // The management company and CondoOS staff (D77) work from the desktop screens.
  if (me.management_companies.length > 0 || me.platform_roles.length > 0) {
    redirect("/admin/carteira");
  }
  // The síndico starts guided (D127): several condominiums → "O que vamos fazer hoje?"; one
  // "apto a operar" → its day to day; one still being implemented → its implantation (D128).
  const mine = sindicoCondos(me);
  if (mine.length > 1) redirect("/inicio");
  if (mine.length === 1) {
    const day = await apiGet<DayToDay>(`/condominiums/${mine[0]!.id}/day`);
    redirect(day.implemented ? `/dia-a-dia/${mine[0]!.id}` : `/implantacao/${mine[0]!.id}`);
  }
  const first = me.condominiums[0];
  if (first) redirect(`/condominio/${first.id}/resumo`);
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-xl font-semibold">Olá, {me.name}</h1>
      <p className="mt-2 text-fg-2">
        Seu acesso ainda não está ligado a nenhum condomínio. Fale com quem cadastrou você.
      </p>
    </main>
  );
}
