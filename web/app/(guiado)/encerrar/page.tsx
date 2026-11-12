import { ChevronLeft, DoorOpen } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { GuidedChoice } from "@/components/condoos/GuidedChoice";
import { apiGet } from "@/lib/api";
import { sindicoCondos } from "@/lib/daytoday";
import type { Me } from "@/lib/types";

/** Which condominium to leave (D129), when there is more than one. */
export default async function EncerrarEscolhaPage() {
  const me = await apiGet<Me>("/me");
  const condos = sindicoCondos(me);
  if (condos.length === 0) redirect("/");
  if (condos.length === 1) redirect(`/encerrar/${condos[0]!.id}`);
  return (
    <>
      <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
        <ChevronLeft size={16} aria-hidden /> Início
      </Link>
      <h1 className="text-[22px] leading-tight font-semibold">De qual condomínio você vai sair?</h1>
      {condos.map((c) => (
        <GuidedChoice
          key={c.id}
          href={`/encerrar/${c.id}`}
          icon={DoorOpen}
          title={c.name}
          detail="Por quê, quando e o dossiê do seu período"
          quiet
        />
      ))}
    </>
  );
}
