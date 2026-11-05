import { redirect } from "next/navigation";

import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

/** Entry point: send each user to the right home for their role. */
export default async function Home() {
  const me = await apiGet<Me>("/me");
  if (me.management_companies.length > 0) redirect("/admin/carteira");
  const first = me.condominiums[0];
  if (first) redirect(`/condominio/${first.id}/resumo`);
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-xl font-semibold">Olá, {me.name}</h1>
      <p className="mt-2 text-fg-2">
        Seu acesso ainda não está ligado a nenhum condomínio. Fale com a administradora.
      </p>
    </main>
  );
}
