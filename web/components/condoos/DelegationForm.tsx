"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import type { DelegationDetail, DelegationItem } from "@/lib/types";

const ROLES = [
  { value: "administradora", label: "Administradora" },
  { value: "fornecedor", label: "Fornecedor" },
  { value: "contador", label: "Contador(a)" },
  { value: "zelador", label: "Zelador(a)" },
  { value: "outro", label: "Outra pessoa" },
];

/** A request for documents (D95): who, what (suggested from what is missing) and until when.
 * No phone or e-mail is asked: the síndico sends the link through their own channel. */
export function DelegationForm({
  condominiumId,
  suggestions,
  defaultDue,
  detailBase,
}: {
  condominiumId: string;
  /** Where the new request opens (base path + "/<id>"); defaults to the síndico's screen. */
  detailBase?: string;
  suggestions: DelegationItem[];
  defaultDue: string; // YYYY-MM-DD, computed on the server (same value when hydrating)
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState("administradora");
  const [chosen, setChosen] = useState<Set<string>>(
    new Set(suggestions.filter((s) => s.kind === "nota_fiscal").map((s) => s.key)),
  );
  const [custom, setCustom] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [due, setDue] = useState(defaultDue);
  const [scope, setScope] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = (key: string) => {
    const next = new Set(chosen);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setChosen(next);
  };
  const items = [
    ...suggestions.filter((s) => chosen.has(s.key)),
    ...custom.map((label) => ({ label })),
  ];

  async function save() {
    setBusy(true);
    setError(null);
    const r = await send<DelegationDetail>("POST", `/condominiums/${condominiumId}/delegations`, {
      recipient_name: name,
      recipient_role: role,
      items,
      scope,
      due_date: due,
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.push(`${detailBase ?? `/condominio/${condominiumId}/pedidos`}/${r.data.id}`);
  }

  return (
    <Card>
      <div className="space-y-4">
        <Field id="d-name" label="Para quem" required hint="Nome da pessoa ou da empresa.">
          <input
            id="d-name"
            className={controlClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field id="d-role" label="Quem é">
          <select
            id="d-role"
            className={controlClass}
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </Field>
        <fieldset>
          <legend className="text-sm font-medium">O que pedir</legend>
          <ul className="mt-2 space-y-2">
            {suggestions.map((s) => (
              <li key={s.key}>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={chosen.has(s.key)}
                    onChange={() => toggle(s.key)}
                  />
                  <span>
                    {s.label}
                    {s.kind === "nota_fiscal" && (
                      <span className="block text-[12px] text-fg-2">
                        Ainda não recebida: pode ter sido emitida e não enviada.
                      </span>
                    )}
                  </span>
                </label>
              </li>
            ))}
            {custom.map((label, i) => (
              <li key={`${label}-${i}`} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked readOnly className="mt-0.5" aria-label={label} />
                {label}
              </li>
            ))}
          </ul>
          <div className="mt-3 flex gap-2">
            <input
              aria-label="Outro documento"
              placeholder="Outro documento"
              className={controlClass}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <Button
              size="md"
              icon={<Plus size={14} aria-hidden />}
              disabled={draft.trim().length < 3}
              onClick={() => {
                setCustom([...custom, draft.trim()]);
                setDraft("");
              }}
            >
              Incluir
            </Button>
          </div>
        </fieldset>
        <Field id="d-due" label="Prazo" required>
          <input
            id="d-due"
            type="date"
            className={controlClass}
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
        </Field>
        <Field id="d-scope" label="Observação (opcional)">
          <textarea
            id="d-scope"
            className={textareaClass}
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          />
        </Field>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Button
          variant="primary"
          disabled={busy || name.trim().length < 3 || items.length === 0 || !due}
          onClick={() => void save()}
        >
          Preparar pedido
        </Button>
        <p className="text-[12px] text-muted">
          Não guardamos telefone nem e-mail: você envia o link pelo seu canal ou, na próxima tela,
          pede ao CondoOS para enviar por e-mail com a sua aprovação.
        </p>
      </div>
    </Card>
  );
}
