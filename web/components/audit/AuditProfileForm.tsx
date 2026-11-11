"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { send } from "@/lib/client";

type Value = boolean | null;

/** The audit profile (D123): what applies to this condominium. Versioned with author and
 * reason; "não sei" keeps the controls that depend on it pending. */
export function AuditProfileForm({
  condominiumId,
  profile,
  questions,
  canEdit,
}: {
  condominiumId: string;
  profile: Record<string, Value>;
  questions: Record<string, string>;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [values, setValues] = useState(profile);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const set = (k: string, v: string) =>
    setValues((p) => ({ ...p, [k]: v === "sim" ? true : v === "nao" ? false : null }));
  async function save() {
    const r = await send("PUT", `/condominiums/${condominiumId}/audit/profile`, { values, reason });
    setMessage(r.ok ? "Perfil salvo (nova versão, com motivo)." : r.error);
    if (r.ok) router.refresh();
  }
  return (
    <div className="space-y-3" data-testid="audit-profile">
      {Object.entries(questions).map(([k, q]) => (
        <label key={k} className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>{q}</span>
          <select
            className={controlClass}
            disabled={!canEdit}
            value={values[k] === true ? "sim" : values[k] === false ? "nao" : ""}
            onChange={(e) => set(k, e.target.value)}
          >
            <option value="">Não informado</option>
            <option value="sim">Sim</option>
            <option value="nao">Não</option>
          </select>
        </label>
      ))}
      {canEdit && (
        <div className="flex flex-wrap items-end gap-2">
          <input
            className={controlClass}
            placeholder="Motivo da mudança"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            variant="primary"
            disabled={reason.trim().length < 10}
            onClick={() => void save()}
          >
            Salvar perfil
          </Button>
        </div>
      )}
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
