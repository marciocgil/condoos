import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// D95 (LF4): the síndica asks for a document, the CondoOS makes the link and the text
// (nothing is sent by the system), the sender uploads without a login, triage refuses an
// active PDF, and the request concludes; the link then stops working.
const RECEIPT = path.resolve(__dirname, "../../../api/tests/fixtures/corpus/17_recibo.pdf");

test("síndica pede um documento, quem tem envia pelo link e o pedido conclui", async ({
  page,
  browser,
}, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(120_000);
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  const stamp = Date.now();

  await page.goto(`/condominio/${id}/enviar`);
  await page.getByRole("link", { name: /Peça a quem tem os documentos/ }).click();
  await page.getByLabel("Para quem").fill(`Atlântida Gestão ${stamp}`);
  for (const box of await page.getByRole("checkbox").all()) await box.uncheck();
  await page.getByLabel("Outro documento").fill("Recibo da limpeza da caixa de gordura");
  await page.getByRole("button", { name: "Incluir" }).click();
  await page.getByRole("button", { name: "Preparar pedido" }).click();
  await expect(page).toHaveURL(/\/pedidos\/[0-9a-f-]+$/);
  await expect(page.getByText("Autorizado", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Gerar link e texto" }).click();
  const text = await page.getByTestId("delegation-link").locator("pre").innerText();
  const url = new URL(text.match(/https?:\/\/\S+\/enviar\/[\w-]+/)?.[0] ?? "");
  expect(text).toContain("Recibo da limpeza da caixa de gordura");
  await page.getByRole("button", { name: "Já enviei" }).click();

  // Hoje (LB-044): the request is now with the recipient, not with the síndica.
  await page.goto(`/condominio/${id}/resumo`);
  const board = page.getByRole("region", { name: "Com outros", exact: true });
  await expect(board).toContainText(`Atlântida Gestão ${stamp}`);
  await page.goBack();

  // The sender: another browser, no session.
  const sender = await (await browser.newContext()).newPage();
  await sender.goto(url.pathname);
  await expect(sender.getByRole("heading", { name: "Envio de documentos" })).toBeVisible();
  await expect(sender.getByText("Recibo da limpeza da caixa de gordura")).toBeVisible();
  const pdf = Buffer.concat([readFileSync(RECEIPT), Buffer.from(`\n% pedido ${stamp}\n`)]);
  const active = Buffer.from(
    readFileSync(RECEIPT)
      .toString("latin1")
      .replace("%%EOF", "9 0 obj << /S /JavaScript /JS (x) >> endobj\n%%EOF"),
    "latin1",
  );
  await sender.getByLabel("Escolher arquivos para enviar").setInputFiles([
    { name: `recibo-${stamp}.pdf`, mimeType: "application/pdf", buffer: pdf },
    { name: `ativo-${stamp}.pdf`, mimeType: "application/pdf", buffer: active },
  ]);
  const results = sender.getByRole("list", { name: "Resultado do envio" });
  await expect(results).toContainText("Recebido");
  await expect(results).toContainText("conteúdo ativo");

  // Files arrived: checking them is now with the síndica.
  await page.goto(`/condominio/${id}/resumo`);
  const mine = page.getByRole("region", { name: "Com você", exact: true });
  await expect(mine).toContainText("Conferir os arquivos recebidos");
  await mine.getByRole("link", { name: new RegExp(`Atlântida Gestão ${stamp}`) }).click();
  await expect(page.getByRole("list", { name: "Arquivos recebidos" })).toContainText(
    `recibo-${stamp}.pdf`,
  );
  await page.getByRole("button", { name: "Recebido", exact: true }).click();
  await expect(page.getByText("Concluído", { exact: true })).toBeVisible();

  await sender.reload();
  await expect(
    sender.getByRole("heading", { name: "Link inválido ou fora do prazo" }),
  ).toBeVisible();
});

test("equipe CondoOS prepara um pedido no desktop e ele fica como rascunho", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "admin-desktop", "tela do desktop");
  await loginAs(page, "fabio.admin@condoos.example.com");
  const stamp = Date.now();
  await page.goto("/admin/pedidos");
  await expect(page.getByRole("heading", { name: "Pedidos de documentos" })).toBeVisible();
  await page
    .getByRole("navigation", { name: "Filtrar por condomínio" })
    .getByRole("link", { name: /Acácias/ })
    .click();
  await page.getByRole("link", { name: "Preparar pedido" }).click();
  await page.getByLabel("Para quem").fill(`Contador ${stamp}`);
  for (const box of await page.getByRole("checkbox").all()) await box.uncheck();
  await page.getByLabel("Outro documento").fill("Balancete de outubro");
  await page.getByRole("button", { name: "Incluir" }).click();
  await page.getByRole("button", { name: "Preparar pedido" }).click();
  await expect(page).toHaveURL(/\/admin\/pedidos\/[0-9a-f-]+\/[0-9a-f-]+$/);
  await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();
  // Only the síndico authorises: the team sees no link button.
  await expect(page.getByRole("button", { name: "Gerar link e texto" })).toHaveCount(0);
  await page.getByRole("link", { name: "Pedidos" }).first().click();
  await expect(page.getByRole("table", { name: "Pedidos de documentos" })).toContainText(
    `Contador ${stamp}`,
  );
});
