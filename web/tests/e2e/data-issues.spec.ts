import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { loginAs } from "./auth";

// LF3-b (D95): a contract whose registered value no longer matches its own document opens a
// data conflict; the CondoOS admin sees both versions side by side and picks one with a
// reason. The document's values become facts the real way: a person confirms them.

const CORPUS = path.resolve(__dirname, "../../../api/tests/fixtures/corpus");
const CONTRACT = path.join(CORPUS, "20_contrato.pdf");
const TRUTH = JSON.parse(readFileSync(path.join(CORPUS, "ground_truth.json"), "utf8")) as {
  documents: Record<string, { fields: Record<string, unknown> }>;
};

function cnpj(): string {
  const base = Array.from({ length: 12 }, () => Math.floor(Math.random() * 10));
  const digit = (nums: number[]) => {
    const w =
      nums.length === 12
        ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const rest = nums.reduce((acc, n, i) => acc + n * (w[i] ?? 0), 0) % 11;
    return rest < 2 ? 0 : 11 - rest;
  };
  const d1 = digit(base);
  return [...base, d1, digit([...base, d1])].join("");
}

async function until<T>(page: Page, url: string, ok: (body: T) => boolean): Promise<T> {
  for (let i = 0; i < 60; i += 1) {
    const r = await page.request.get(url);
    if (r.ok()) {
      const body = (await r.json()) as T;
      if (ok(body)) return body;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`timeout waiting for ${url}`);
}

test("admin escolhe a versão certa de um contrato em conflito", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  test.setTimeout(150_000);
  const tag = Date.now().toString(36);
  const condoCnpj = cnpj();
  await loginAs(page, "fabio.admin@condoos.example.com");
  const created = await page.request.post("/api/portfolio/condominiums", {
    data: {
      condominium: {
        name: `Residencial Conflito ${tag} (fictício)`,
        slug: `conflito-${tag}`,
        cnpj: condoCnpj,
        units: 30,
        address: "Rua Fictícia, 50 — Cidade Modelo/SP",
        approval_limits: { default: "5000.00", by_category: {} },
      },
      board: [
        {
          name: "Síndico Conflito",
          position: "sindico",
          term_start: "2026-01-01",
          email: `sindico.${tag}@conflito.example.com`,
        },
      ],
    },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };
  const api = `/api/condominiums/${id}`;

  const sent = await page.request.post(`${api}/documents`, {
    multipart: {
      files: { name: "contrato.pdf", mimeType: "application/pdf", buffer: readFileSync(CONTRACT) },
    },
  });
  const doc = ((await sent.json()) as { document_id: string }[])[0]!.document_id;
  await until<{ extraction_status: string }>(
    page,
    `${api}/documents/${doc}`,
    (d) => !["pending", "processing"].includes(d.extraction_status),
  );

  // A person confirms what the document says: its values become facts and the contract is
  // created from the document (D59).
  const values: Record<string, unknown> = {
    ...TRUTH.documents["20_contrato.pdf"]!.fields,
    cnpj_contratante: condoCnpj,
  };
  const reviewed = await page.request.put(`${api}/documents/${doc}/review`, {
    data: { doc_type: "contrato", values },
  });
  expect(reviewed.ok()).toBeTruthy();
  // monthly_value is the value in force (with adjustments); the registered one is "original".
  type Contract = { id: string; monthly_value: string; original_monthly_value: string | null };
  const [contract] = await until<Contract[]>(page, `${api}/contracts`, (c) => c.length === 1);

  // Later the registered value is changed, and no longer matches the signed document.
  const changed = await page.request.put(`${api}/contracts/${contract!.id}`, {
    data: {
      supplier_cnpj: values.cnpj_contratada,
      supplier_name: values.razao_social_contratada,
      object: values.objeto,
      scope_items: values.itens_escopo,
      monthly_value: "9800.00",
      adjustment_index: "IPCA",
      adjustment_base_month: 1,
      start_date: values.data_inicio,
      end_date: values.data_fim,
    },
  });
  expect(changed.ok()).toBeTruthy();

  await page.goto(`/admin/configuracoes?condominio=${id}`);
  const card = page.getByTestId("data-issues");
  await expect(card).toBeVisible();
  await expect(card.getByText(/valor mensal do cadastro difere do documento/)).toBeVisible();
  await expect(card.getByText("R$ 9.800,00")).toBeVisible();
  await expect(card.getByText("R$ 9.200,00")).toBeVisible();
  const readiness = page.getByTestId("readiness").locator('[data-capability="C2"]');
  await expect(readiness.getByText("Falta: Nenhum conflito de dados aberto")).toBeVisible();

  await card.getByLabel(/Documento do contrato/).check();
  await card.getByLabel("Motivo (obrigatório)").fill("O contrato assinado é o que vale.");
  await card.getByRole("button", { name: "Usar a versão escolhida" }).click();
  await expect(page.getByTestId("data-issues")).toHaveCount(0);
  await expect(readiness.getByText("Falta: Nenhum conflito de dados aberto")).toHaveCount(0);
  const [after] = (await (await page.request.get(`${api}/contracts`)).json()) as Contract[];
  expect(Number(after!.original_monthly_value ?? after!.monthly_value)).toBe(9200);
});
