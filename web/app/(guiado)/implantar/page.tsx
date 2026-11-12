import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ImplantConversation } from "@/components/condoos/ImplantConversation";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

/** Implantar um condomínio (D128). */
export default async function ImplantarPage() {
  const [me, can] = await Promise.all([
    apiGet<Me>("/me"),
    apiGet<{ can_implant: boolean }>("/implantation/eligibility"),
  ]);
  if (!can.can_implant) redirect("/");
  return (
    <>
      <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
        <ChevronLeft size={16} aria-hidden /> Início
      </Link>
      <ImplantConversation userName={me.name} />
    </>
  );
}
