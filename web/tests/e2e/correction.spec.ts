import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// A fictitious receipt from the corpus. Without the model, receipts always go to the
// exception queue, so the manager has something to correct.
const RECEIPT = path.resolve(__dirname, "../../../api/tests/fixtures/corpus/18_recibo.pdf");

test("gerente envia um recibo, corrige a extração e o item sai da fila", async ({ page }, info) => {
  test.skip(info.project.name !== "admin-desktop");
  test.setTimeout(120_000);
  // Unique bytes per run so the upload is never a duplicate of an earlier run.
  const unique = Buffer.concat([readFileSync(RECEIPT), Buffer.from(`\n% e2e ${Date.now()}\n`)]);
  const filename = `recibo-e2e-${Date.now()}.pdf`;

  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.goto("/admin/enviar");
  await page
    .getByLabel("Condomínio")
    .selectOption({ label: "Condomínio Residencial Jardim das Acácias" });
  await page.getByLabel("Escolher arquivos").setInputFiles({
    name: filename,
    mimeType: "application/pdf",
    buffer: unique,
  });
  await expect(page.getByRole("list", { name: "Resultado do envio" })).toContainText("Recebido");

  // The worker classifies and extracts in the background. With the full reader (Docling in
  // the docker worker) or a model key, the receipt may be read completely and never need a
  // correction: then there is nothing to correct and the flow does not apply.
  const portfolio = await (await page.request.get("/api/portfolio")).json();
  const acacias = portfolio.condominiums.find((c: { name: string }) =>
    c.name.includes("Jardim das Acácias"),
  );
  let read: { extraction_status: string; needs_review: boolean } | undefined;
  await expect(async () => {
    const docs = (await (
      await page.request.get(`/api/condominiums/${acacias.id}/documents`)
    ).json()) as { original_filename: string; extraction_status: string; needs_review: boolean }[];
    read = docs.find((d) => d.original_filename === filename);
    expect(read && !["pending", "processing"].includes(read.extraction_status)).toBeTruthy();
  }).toPass({ timeout: 90_000 });
  test.skip(
    read?.extraction_status === "done" && !read.needs_review,
    "O recibo foi lido por completo, sem precisar de correção (leitor completo ou IA ativa).",
  );

  const item = page.getByRole("listitem").filter({ hasText: filename });
  await expect(async () => {
    await page.goto("/admin/fila");
    await expect(item).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 90_000 });

  await item.getByRole("link", { name: "Corrigir" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(filename);
  await expect(page.getByLabel("Tipo do documento")).toHaveValue("recibo");
  await expect(page.getByTestId("low-nome_recebedor")).toBeVisible();

  await page.getByLabel(/^Data/).fill("2026-10-18");
  await page.getByLabel(/^Valor/).fill("180,00");
  await page.getByLabel(/^Quem recebeu/).fill("Joana Lúcia Ferreira");
  await page.getByLabel(/^CPF\/CNPJ de quem recebeu/).fill("");
  await page.getByLabel(/^Referente a/).fill("limpeza da caixa de gordura");
  await page.getByRole("button", { name: "Salvar correção" }).click();

  await expect(page).toHaveURL(/\/admin\/fila$/);
  await expect(page.getByRole("listitem").filter({ hasText: filename })).toHaveCount(0);
});
