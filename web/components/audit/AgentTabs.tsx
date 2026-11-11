import Link from "next/link";

import { cx } from "@/components/ui/cx";

/** Tabs of "Agentes & Prompts": the agents' prompts, and the deterministic rules apart. */
export function AgentTabs({ active }: { active: "agentes" | "regras" }) {
  const tab = (on: boolean) =>
    cx(
      "rounded-full border px-3 py-1 text-sm",
      on ? "border-accent bg-accent/10 font-medium" : "border-control text-fg-2 hover:text-fg",
    );
  return (
    <nav aria-label="Seções" className="mb-6 flex gap-2">
      <Link
        href="/admin/audit/agentes"
        className={tab(active === "agentes")}
        aria-current={active === "agentes" ? "page" : undefined}
      >
        Agentes e prompts
      </Link>
      <Link
        href="/admin/audit/regras"
        className={tab(active === "regras")}
        aria-current={active === "regras" ? "page" : undefined}
      >
        Regras, não prompts
      </Link>
    </nav>
  );
}
