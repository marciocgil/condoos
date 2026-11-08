import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// Launch F01 (D89): the síndica chooses a goal, sends a contract and sees what was read,
// with the source of each field and the limits of the reading.
const CONTRACT = path.resolve(__dirname, "../../../api/tests/fixtures/corpus/20_contrato.pdf");

test("síndica escolhe o objetivo, envia um contrato e vê a primeira leitura", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(150_000);
  await loginAs(page, "ana.sindica@acacias.example.com");
  const resumo = page.url();
  const id = resumo.match(/condominio\/([^/]+)/)?.[1];
  // Start from no goal and a visible card, whatever earlier runs left.
  await page.request.put(`/api/condominiums/${id}/launch/dismissed`, {
    data: { dismissed: false },
  });
  await page.request.put(`/api/condominiums/${id}/launch/goal`, { data: { goal: null } });
  await page.reload();

  const card = page.getByTestId("journey-card");
  await expect(card.getByRole("heading", { name: "Implantação do seu assessor" })).toBeVisible();
  await card.getByRole("button", { name: "Economizar dinheiro" }).click();
  await expect(card.getByRole("list", { name: "Objetivo inicial" })).toBeHidden();
  await card.getByText("Marcos e o que cada função precisa").click();
  await expect(card.getByRole("list", { name: "Marcos" }).getByRole("listitem")).toHaveCount(5);
  await expect(card.getByRole("list", { name: "Prontidão por função" })).toContainText(
    "Leitura de contratos",
  );

  const unique = Buffer.concat([readFileSync(CONTRACT), Buffer.from(`\n% e2e ${Date.now()}\n`)]);
  await page.goto(`/condominio/${id}/enviar`);
  await page.getByLabel("Escolher arquivos").setInputFiles({
    name: `contrato-e2e-${Date.now()}.pdf`,
    mimeType: "application/pdf",
    buffer: unique,
  });
  const reading = page.getByTestId("first-value");
  await expect(reading).not.toContainText("Lendo", { timeout: 120_000 });
  await expect(reading).toContainText("O que esta leitura não cobre");
  await expect(reading).toContainText("não uma auditoria");
  // Every field says what it is: read, to confirm, or not found.
  await expect(reading.getByTestId("field-valor_mensal")).toContainText(
    /Lido no documento|A confirmar|Não encontrado/,
  );
});

// LF2-b (D90): the CondoOS team follows implementations across the portfolio.
test("admin CondoOS acompanha implantações, prontidão e tempo até o primeiro valor", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "fabio.admin@condoos.example.com");
  await page.goto("/admin/carteira");
  const table = page.getByRole("table", { name: "Implantações em andamento" });
  await expect(table).toContainText("Jardim das Acácias");
  await expect(table.getByRole("columnheader", { name: "Próximo marco" })).toBeVisible();

  await page.goto("/admin/configuracoes");
  await expect(page.getByRole("heading", { name: "O que já funciona" })).toBeVisible();
  await expect(page.getByTestId("readiness-C7")).toContainText("Ações com sua aprovação");

  await page.goto("/admin/metricas");
  await expect(page.getByRole("table", { name: "Implantação por condomínio" })).toContainText(
    "Jardim das Acácias",
  );
});

// LB-033 (D94): "Faça por mim" — a batch is read and followed file by file.
test("síndica envia um lote e acompanha a leitura de cada arquivo", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(150_000);
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  const corpus = path.resolve(__dirname, "../../../api/tests/fixtures/corpus");
  const stamp = Date.now();
  const file = (name: string) => ({
    name: `${stamp}-${name}`,
    mimeType: "application/pdf",
    buffer: Buffer.concat([
      readFileSync(path.join(corpus, name)),
      Buffer.from(`\n% e2e ${stamp}\n`),
    ]),
  });
  await page.goto(`/condominio/${id}/enviar`);
  await page
    .getByLabel("Escolher arquivos")
    .setInputFiles([file("01_nfse.pdf"), file("17_recibo.pdf")]);
  const batch = page.getByTestId("batch-progress");
  await expect(batch).toBeVisible();
  await expect(batch).toContainText("leitura concluída", { timeout: 120_000 });
  await expect(batch.getByRole("listitem")).toHaveCount(2);
});

// D101 (LF5): the síndica sees the inbound address and changes it; the old one stops.
test("síndica vê o e-mail de entrada e troca o endereço", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, "carla.sindica@mirante.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  await page.goto(`/condominio/${id}/ajustes`);
  const card = page.getByRole("region", { name: "E-mail de entrada" });
  const address = card.getByTestId("inbound-address");
  const before = await address.innerText();
  expect(before).toMatch(/^mirante-do-vale-[a-z2-9]{8}@/);
  await card.getByRole("button", { name: "Trocar o endereço" }).click();
  await card.getByRole("button", { name: "Trocar endereço", exact: true }).click();
  await expect(address).not.toHaveText(before);
  await expect(address).toHaveText(/^mirante-do-vale-[a-z2-9]{8}@/);
});
