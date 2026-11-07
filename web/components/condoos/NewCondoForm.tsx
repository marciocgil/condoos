"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field } from "@/components/ui/Field";
import { send } from "@/lib/client";

function slugify(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/^condom[ií]nio\s+/, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

/** New condominium in the manager's management company (replaces the CLI onboarding). */
export function NewCondoForm() {
  const router = useRouter();
  const [c, setC] = useState({
    name: "",
    slug: "",
    cnpj: "",
    units: "",
    address: "",
    limit: "",
    obras: "",
  });
  const [s, setS] = useState({ name: "", email: "", term_start: "" });
  const [slugTouched, setSlugTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    const r = await send<{ id: string }>("POST", "/portfolio/condominiums", {
      condominium: {
        name: c.name,
        slug: c.slug,
        cnpj: c.cnpj,
        units: Number(c.units),
        address: c.address,
        // Optional (D89): without a limit, actions with a cost wait until it is configured.
        approval_limits: c.limit
          ? { default: c.limit, by_category: c.obras ? { obras: c.obras } : {} }
          : null,
      },
      board: [
        { name: s.name, position: "sindico", term_start: s.term_start, email: s.email || null },
      ],
    });
    setBusy(false);
    if (!r.ok) return setError(r.error);
    router.push(`/admin/configuracoes?condominio=${r.data.id}`);
    router.refresh();
  }

  const ready = c.name && c.slug && c.cnpj && c.units && c.address && s.name && s.term_start;
  return (
    <div className="grid max-w-3xl gap-6">
      <Card>
        <CardTitle>Condomínio</CardTitle>
        <div className="space-y-4">
          <Field id="n-name" label="Nome" required>
            <input
              id="n-name"
              className={controlClass}
              value={c.name}
              onChange={(e) =>
                setC({
                  ...c,
                  name: e.target.value,
                  slug: slugTouched ? c.slug : slugify(e.target.value),
                })
              }
            />
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              id="n-cnpj"
              label="CNPJ"
              required
              hint="O mesmo das notas e contratos (tomador/contratante)."
            >
              <input
                id="n-cnpj"
                className={controlClass}
                value={c.cnpj}
                onChange={(e) => setC({ ...c, cnpj: e.target.value })}
                placeholder="00.000.000/0000-00"
              />
            </Field>
            <Field
              id="n-slug"
              label="Endereço curto"
              required
              hint="Usado no e-mail de entrada: <endereço>@ingest..."
            >
              <input
                id="n-slug"
                className={controlClass}
                value={c.slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setC({ ...c, slug: slugify(e.target.value) });
                }}
              />
            </Field>
          </div>
          <Field id="n-address" label="Endereço" required>
            <input
              id="n-address"
              className={controlClass}
              value={c.address}
              onChange={(e) => setC({ ...c, address: e.target.value })}
            />
          </Field>
          <div className="grid gap-4 md:grid-cols-3">
            <Field id="n-units" label="Unidades" required>
              <input
                id="n-units"
                type="number"
                min={1}
                className={controlClass}
                value={c.units}
                onChange={(e) => setC({ ...c, units: e.target.value })}
              />
            </Field>
            <Field
              id="n-limit"
              label="Alçada do síndico (R$)"
              hint="Pode ficar para depois: sem alçada, nenhuma ação com custo é aprovada."
            >
              <input
                id="n-limit"
                inputMode="decimal"
                className={controlClass}
                value={c.limit}
                onChange={(e) => setC({ ...c, limit: e.target.value })}
                placeholder="5000,00"
              />
            </Field>
            <Field id="n-obras" label="Alçada de obras (R$)">
              <input
                id="n-obras"
                disabled={!c.limit}
                inputMode="decimal"
                className={controlClass}
                value={c.obras}
                onChange={(e) => setC({ ...c, obras: e.target.value })}
                placeholder="3000,00"
              />
            </Field>
          </div>
        </div>
      </Card>
      <Card>
        <CardTitle>Síndico(a)</CardTitle>
        <div className="space-y-4">
          <Field id="n-sname" label="Nome completo" required>
            <input
              id="n-sname"
              className={controlClass}
              value={s.name}
              onChange={(e) => setS({ ...s, name: e.target.value })}
            />
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              id="n-semail"
              label="E-mail"
              hint="Com e-mail, a pessoa já recebe acesso de síndico(a)."
            >
              <input
                id="n-semail"
                type="email"
                className={controlClass}
                value={s.email}
                onChange={(e) => setS({ ...s, email: e.target.value })}
              />
            </Field>
            <Field id="n-sstart" label="Início do mandato" required>
              <input
                id="n-sstart"
                type="date"
                className={controlClass}
                value={s.term_start}
                onChange={(e) => setS({ ...s, term_start: e.target.value })}
              />
            </Field>
          </div>
          <p className="text-xs text-muted">
            Conselheiros e demais acessos são cadastrados depois, em Configurações.
          </p>
        </div>
      </Card>
      {error && (
        <p role="alert" className="text-[13px] text-danger">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button variant="primary" onClick={() => void save()} disabled={busy || !ready}>
          {busy ? "Cadastrando…" : "Cadastrar condomínio"}
        </Button>
        <Button variant="ghost" onClick={() => router.push("/admin/carteira")}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
