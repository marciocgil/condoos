"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import type { MatchIssue } from "@/lib/types";

export function ResolveForm({
  condominiumId,
  issue,
}: {
  condominiumId: string;
  issue: MatchIssue;
}) {
  const router = useRouter();
  const [choice, setChoice] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const res = await fetch(`/api/condominiums/${condominiumId}/match-issues/${issue.id}/resolve`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ candidate_id: choice === "none" ? null : choice }),
    });
    if (res.ok) {
      router.push("/admin/fila");
      router.refresh();
    } else {
      setError("Não foi possível salvar. Atualize a página e tente de novo.");
    }
  }

  return (
    <fieldset className="space-y-2 rounded-[var(--radius-card)] bg-surface p-5 border border-line">
      <legend className="mb-2 text-sm font-medium">Opções compatíveis</legend>
      {[...issue.candidates, { type: "none", id: "none", label: "Nenhuma das opções" }].map((c) => (
        <label
          key={c.id}
          className="flex items-center gap-3 rounded-[var(--radius-control)] border border-control px-3 py-2"
        >
          <input
            type="radio"
            name="candidate"
            value={c.id}
            checked={choice === c.id}
            onChange={() => setChoice(c.id)}
          />
          <span className="text-sm">{c.label}</span>
        </label>
      ))}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="button"
        disabled={!choice}
        onClick={submit}
        className={`mt-2 ${buttonClass("primary")}`}
      >
        Confirmar
      </button>
    </fieldset>
  );
}
