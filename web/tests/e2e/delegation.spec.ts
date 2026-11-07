import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// LF4 (F02, D97): the síndica asks the management company for documents. She authorizes a
// send-only link and sends the ready text herself; the company sends files without an
// account; the síndica sees them and revokes the link, which stops working at once.

const PDF = path.resolve(__dirname, "../../../api/tests/fixtures/corpus/01_nfse.pdf");

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

test("síndica pede documentos por link, a administradora envia e o link é revogado", async ({
  page,
  browser,
}) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(120_000);
  const tag = Date.now().toString(36);
  const email = `sindica.${tag}@pedido.example.com`;
  await loginAs(page, "fabio.admin@condoos.example.com");
  const created = await page.request.post("/api/portfolio/condominiums", {
    data: {
      condominium: {
        name: `Residencial Pedido ${tag} (fictício)`,
        slug: `pedido-${tag}`,
        cnpj: cnpj(),
        units: 20,
        address: "Rua Fictícia, 60 — Cidade Modelo/SP",
        approval_limits: null,
      },
      board: [{ name: "Síndica Pedido", position: "sindico", term_start: "2026-01-01", email }],
    },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };

  await loginAs(page, email);
  await page.goto(`/condominio/${id}/ajustes`);
  await page.getByRole("link", { name: /Pedidos de documentos/ }).click();
  await page.getByLabel("Para quem (nome)").fill("Administradora Fictícia");
  await page.getByLabel("Assunto").fill("Contratos vigentes e notas de outubro");
  await page.getByLabel("Documentos esperados (um por linha)").fill("Contrato da portaria\nNotas");
  await page.getByRole("button", { name: "Salvar rascunho" }).click();
  const card = page.getByTestId("delegation").first();
  await expect(card.getByText("Rascunho")).toBeVisible();

  await card.getByRole("button", { name: "Autorizar e gerar o link" }).click();
  const text = card.locator("pre");
  await expect(text).toContainText("/enviar-documentos/");
  await expect(card.getByText(/o CondoOS não envia nada/)).toBeVisible();
  const link = (await text.textContent())!.match(/\/enviar-documentos\/[\w-]+/)![0];
  await card.getByRole("button", { name: "Já enviei o link" }).click();
  await expect(card.getByText("Enviado por você")).toBeVisible();

  // The management company, without an account.
  const outsider = await browser.newContext();
  const ext = await outsider.newPage();
  await ext.goto(link);
  await expect(ext.getByRole("heading", { name: "Envio de documentos" })).toBeVisible();
  await expect(ext.getByText("Contrato da portaria")).toBeVisible();
  await ext.getByLabel("Escolher arquivos para enviar").setInputFiles([
    {
      name: "nota-outubro.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.concat([readFileSync(PDF), Buffer.from(`\n% e2e ${tag}\n`)]),
    },
    { name: "extrato.ofx", mimeType: "text/plain", buffer: Buffer.from("OFXHEADER:100\n") },
  ]);
  const sent = ext.getByRole("list", { name: "Arquivos enviados" });
  await expect(sent).toContainText("Recebido");
  await expect(sent).toContainText("Tipo não aceito por este link");

  await page.reload();
  await expect(card.getByText("Arquivos recebidos")).toBeVisible();
  await expect(card.getByText(/1 arquivo pelo link/)).toBeVisible();
  await card.getByRole("button", { name: "Revogar o link" }).click();
  await expect(card.getByText("Revogado")).toBeVisible();

  await ext.goto(link);
  await expect(ext.getByRole("heading", { name: "Página não encontrada" })).toBeVisible();
  await outsider.close();
});
