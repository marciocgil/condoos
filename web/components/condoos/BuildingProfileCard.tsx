"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { ComplianceList } from "@/lib/types";

type Values = Record<string, boolean | number>;

/** What the building has (D113). It only suggests which obligations probably apply; each one
 * is still validated by a person. Blank means "não informado". */
export function BuildingProfileCard({
  condominiumId,
  profile,
  canManage,
}: {
  condominiumId: string;
  profile: ComplianceList["profile"];
  canManage: boolean;
}) {
  const router = useRouter();
  const [values, setValues] = useState<Values>(profile.values);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const filled = Object.keys(profile.values).length;

  function set(key: string, value: boolean | number | null) {
    const next = { ...values };
    if (value === null) delete next[key];
    else next[key] = value;
    setValues(next);
    setSaved(false);
  }

  async function save() {
    setBusy(true);
    setError(null);
    const r = await send("PUT", `/condominiums/${condominiumId}/compliance/profile`, { values });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    setSaved(true);
    router.refresh();
  }

  return (
    <Card aria-label="Perfil do prédio">
      <details>
        <summary className="cursor-pointer">
          <CardTitle>Perfil do prédio</CardTitle>
          <span className="text-[13px] text-fg-2">
            {filled === 0
              ? "Não preenchido. Ajuda a sugerir quais obrigações se aplicam."
              : `${filled} de ${profile.fields.length} itens informados. Só sugere: cada obrigação continua sendo confirmada por você.`}
          </span>
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {profile.fields.map((f) =>
            f.kind === "int" ? (
              <Field key={f.key} id={`p-${f.key}`} label={f.label}>
                <input
                  id={`p-${f.key}`}
                  type="number"
                  min={0}
                  max={500}
                  disabled={!canManage}
                  className={controlClass}
                  value={typeof values[f.key] === "number" ? String(values[f.key]) : ""}
                  onChange={(e) =>
                    set(f.key, e.target.value === "" ? null : Number(e.target.value))
                  }
                />
              </Field>
            ) : (
              <Field key={f.key} id={`p-${f.key}`} label={f.label}>
                <select
                  id={`p-${f.key}`}
                  disabled={!canManage}
                  className={controlClass}
                  value={values[f.key] === true ? "sim" : values[f.key] === false ? "nao" : ""}
                  onChange={(e) =>
                    set(f.key, e.target.value === "" ? null : e.target.value === "sim")
                  }
                >
                  <option value="">Não informado</option>
                  <option value="sim">Sim</option>
                  <option value="nao">Não</option>
                </select>
              </Field>
            ),
          )}
        </div>
        {canManage && (
          <div className="mt-3 flex items-center gap-3">
            <Button variant="primary" size="sm" disabled={busy} onClick={save}>
              Salvar perfil
            </Button>
            {saved && <span className="text-[13px] text-fg-2">Perfil salvo.</span>}
          </div>
        )}
        {error && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {error}
          </p>
        )}
      </details>
    </Card>
  );
}
