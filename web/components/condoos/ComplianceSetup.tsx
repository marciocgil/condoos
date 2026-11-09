"use client";

import { ListChecks, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";

/** Turning on the catalogue of common obligations and adding one by hand (D108). Both start
 * "a validar": nothing raises an alert before a person confirms it applies. */
export function ComplianceSetup({
  condominiumId,
  canManage,
  catalogMissing,
  categories,
  detailBase,
}: {
  condominiumId: string;
  canManage: boolean;
  catalogMissing: number;
  categories: { value: string; label: string }[];
  detailBase: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("outros");
  const [lead, setLead] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!canManage) return null;
  const base = `/condominiums/${condominiumId}/compliance`;

  async function catalog() {
    setBusy(true);
    setError(null);
    const r = await send("POST", `${base}/catalog`);
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.refresh();
  }

  async function create() {
    setBusy(true);
    setError(null);
    const r = await send<{ id: string }>("POST", base, { name, category, lead_days: lead });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.push(`${detailBase}/${r.data.id}`);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {catalogMissing > 0 && (
          <Button
            variant="primary"
            size="sm"
            disabled={busy}
            onClick={catalog}
            icon={<ListChecks size={14} aria-hidden />}
          >
            Usar a lista de obrigações comuns ({catalogMissing})
          </Button>
        )}
        <Button
          size="sm"
          onClick={() => setOpen(!open)}
          icon={<Plus size={14} aria-hidden />}
          aria-expanded={open}
        >
          Nova obrigação
        </Button>
      </div>
      {open && (
        <Card aria-label="Nova obrigação">
          <div className="space-y-3">
            <Field
              id="c-name"
              label="Nome"
              required
              hint="Ex.: Laudo da fachada, seguro do gerador."
            >
              <input
                id="c-name"
                className={controlClass}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Field id="c-category" label="Área">
              <select
                id="c-category"
                className={controlClass}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {categories.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field id="c-lead" label="Avisar quantos dias antes do vencimento">
              <input
                id="c-lead"
                type="number"
                min={1}
                max={365}
                className={controlClass}
                value={lead}
                onChange={(e) => setLead(Number(e.target.value))}
              />
            </Field>
            <Button variant="primary" disabled={busy || name.trim().length < 3} onClick={create}>
              Cadastrar
            </Button>
          </div>
        </Card>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
