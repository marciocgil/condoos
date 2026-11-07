"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { controlClass } from "@/components/ui/Field";
import { CASE_CATEGORY_LABEL, CASE_SEVERITY_LABEL } from "@/lib/labels";

const DEADLINE: Record<string, string> = {
  atrasados: "Atrasados",
  "7dias": "Próximos 7 dias",
  sem_prazo: "Sem prazo",
};

/** Queue filters (FR-025, CB-023): person, category, severity and deadline, kept in the URL so
 * the list stays server-rendered and shareable. */
export function CaseFilters({ owners }: { owners: { id: string; name: string }[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  // The URL updates after the navigation; two quick changes must not lose the first one.
  const latest = useRef<string | null>(null);
  useEffect(() => {
    latest.current = null; // the URL caught up (or another view link was followed)
  }, [params]);

  function set(key: string, value: string) {
    const next = new URLSearchParams(latest.current ?? params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    latest.current = next.toString();
    router.push(`${pathname}?${next.toString()}`);
  }

  const select = (id: string, label: string, key: string, options: Record<string, string>) => (
    <label htmlFor={id} className="min-w-0 flex-1 basis-36">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      <select
        id={id}
        className={controlClass}
        value={params.get(key) ?? ""}
        onChange={(e) => set(key, e.target.value)}
      >
        <option value="">Todos</option>
        {Object.entries(options).map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filtros da fila">
      {owners.length > 0 &&
        select(
          "f-owner",
          "Responsável",
          "responsavel",
          Object.fromEntries(owners.map((o) => [o.id, o.name])),
        )}
      {select("f-category", "Categoria", "categoria", CASE_CATEGORY_LABEL)}
      {select("f-severity", "Criticidade", "criticidade", CASE_SEVERITY_LABEL)}
      {select("f-deadline", "Prazo", "prazo", DEADLINE)}
    </div>
  );
}
