"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { Field, controlClass } from "@/components/ui/Field";
import type { Settings } from "@/lib/types";

const PARAM_LABEL: Record<string, string> = {
  tolerance_pct: "Tolerância (%)",
  window_days: "Janela (dias)",
  tolerance_pp: "Tolerância (p.p.)",
  min_confidence: "Confiança mínima da IA (0 a 1)",
  grace_days: "Carência (dias)",
  sigma: "Desvios-padrão",
  min_months: "Meses mínimos de histórico",
  exempt_categories: "Categorias isentas (separadas por vírgula)",
};

export function SettingsForm({
  condominiumId,
  settings,
}: {
  condominiumId: string;
  settings: Settings;
}) {
  const router = useRouter();
  const [limitDefault, setLimitDefault] = useState(settings.approval_limits.default ?? "");
  const [byCategory, setByCategory] = useState<Record<string, string>>(
    settings.approval_limits.by_category ?? {},
  );
  const [params, setParams] = useState<Record<string, Record<string, string>>>(() =>
    Object.fromEntries(
      settings.rules.map((r) => [
        r.code,
        Object.fromEntries(
          Object.entries(r.defaults).map(([k, v]) => {
            const value = r.overrides[k] ?? v;
            return [k, Array.isArray(value) ? value.join(", ") : String(value)];
          }),
        ),
      ]),
    ),
  );
  const [categories, setCategories] = useState(settings.expense_categories.join(", "));
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setMessage(null);
    // Only values different from the rule defaults are stored as overrides.
    const overrides: Record<string, Record<string, unknown>> = {};
    for (const rule of settings.rules) {
      for (const [key, def] of Object.entries(rule.defaults)) {
        const raw = params[rule.code]?.[key] ?? "";
        const value: unknown = Array.isArray(def)
          ? raw
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean)
          : Number(raw.replace(",", "."));
        if (JSON.stringify(value) !== JSON.stringify(def))
          (overrides[rule.code] ??= {})[key] = value;
      }
    }
    const res = await fetch(`/api/condominiums/${condominiumId}/settings`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        approval_limits: { default: limitDefault, by_category: byCategory },
        rule_params: overrides,
        expense_categories: categories
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean),
      }),
    });
    setSaving(false);
    if (res.ok) {
      setMessage({
        ok: true,
        text: "Configurações salvas. A alteração ficou registrada na auditoria.",
      });
      router.refresh();
    } else {
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      setMessage({
        ok: false,
        text: typeof body?.detail === "string" ? body.detail : "Não foi possível salvar.",
      });
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardTitle>Alçadas de aprovação</CardTitle>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="limit-default"
            label="Alçada padrão (R$)"
            hint="Despesas acima disso precisam de aprovação registrada."
          >
            <input
              id="limit-default"
              inputMode="decimal"
              className={controlClass}
              value={limitDefault}
              onChange={(e) => setLimitDefault(e.target.value)}
            />
          </Field>
          {Object.entries(byCategory).map(([cat, value]) => (
            <Field key={cat} id={`limit-${cat}`} label={`Alçada de ${cat} (R$)`}>
              <input
                id={`limit-${cat}`}
                inputMode="decimal"
                className={controlClass}
                value={value}
                onChange={(e) => setByCategory((b) => ({ ...b, [cat]: e.target.value }))}
              />
            </Field>
          ))}
        </div>
      </Card>
      <Card>
        <CardTitle>Parâmetros das regras</CardTitle>
        <div className="divide-y divide-line">
          {settings.rules
            .filter((r) => Object.keys(r.defaults).length > 0)
            .map((r) => (
              <fieldset key={r.code} className="grid gap-3 py-4 sm:grid-cols-[200px_1fr]">
                <legend className="sr-only">{`${r.code} ${r.name}`}</legend>
                <p className="text-sm">
                  <span className="text-muted">{r.code}</span> {r.name}
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.keys(r.defaults).map((key) => (
                    <Field key={key} id={`${r.code}-${key}`} label={PARAM_LABEL[key] ?? key}>
                      <input
                        id={`${r.code}-${key}`}
                        className={controlClass}
                        value={params[r.code]?.[key] ?? ""}
                        onChange={(e) =>
                          setParams((p) => ({
                            ...p,
                            [r.code]: { ...p[r.code], [key]: e.target.value },
                          }))
                        }
                      />
                    </Field>
                  ))}
                </div>
              </fieldset>
            ))}
        </div>
      </Card>
      <Card>
        <CardTitle>Categorias de despesa</CardTitle>
        <Field id="categories" label="Categorias (separadas por vírgula)">
          <input
            id="categories"
            className={controlClass}
            value={categories}
            onChange={(e) => setCategories(e.target.value)}
          />
        </Field>
      </Card>
      <div className="flex items-center gap-4">
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? "Salvando…" : "Salvar configurações"}
        </Button>
        {message && (
          <p
            role={message.ok ? "status" : "alert"}
            className={message.ok ? "text-sm text-success" : "text-sm text-danger"}
          >
            {message.text}
          </p>
        )}
      </div>
    </div>
  );
}
