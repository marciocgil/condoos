"use client";

import { usePathname, useRouter } from "next/navigation";

import { controlClass } from "@/components/ui/Field";
import { formatMonthTitle } from "@/lib/format";
import type { Competence } from "@/lib/types";

export function MonthSelect({ competences, value }: { competences: Competence[]; value: string }) {
  const router = useRouter();
  const pathname = usePathname();
  return (
    <label className="block">
      <span className="sr-only">Competência</span>
      <select
        value={value}
        onChange={(e) => router.push(`${pathname}?mes=${e.target.value.slice(0, 7)}`)}
        className={controlClass}
      >
        {competences.map((c) => (
          <option key={c.id} value={c.month}>
            {formatMonthTitle(c.month)}
            {c.status === "aberta" ? " (em aberto)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
