import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

function inDays(n: number): string {
  return new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
}

test("síndica cadastra uma obrigação, confirma que se aplica e registra a validade", async ({
  page,
}) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  const name = `Laudo de teste ${Date.now()}`;
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  await page.goto(`/condominio/${id}/ajustes`);
  await page.getByRole("link", { name: /Conformidade e vencimentos/ }).click();
  await expect(page.getByRole("heading", { name: "Conformidade e vencimentos" })).toBeVisible();
  // The seed: the insurance expires soon, the catalogue is on.
  const list = page.getByRole("list", { name: "Obrigações" });
  await expect(list.getByText("Seguro obrigatório da edificação")).toBeVisible();
  await expect(page.getByTestId("compliance-summary")).toContainText(/vence(m)? em breve/);

  await page.getByRole("button", { name: "Nova obrigação" }).click();
  await page.getByLabel("Nome").fill(name);
  await page.getByRole("button", { name: "Cadastrar" }).click();
  await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
  await expect(page.getByText("Confirme se se aplica a este condomínio")).toBeVisible();

  await page.getByLabel("Motivo").fill("Orientação do engenheiro (teste)");
  await page.getByRole("button", { name: "Registrar decisão" }).click();
  await expect(page.getByText("Nenhum documento registrado no CondoOS").first()).toBeVisible();

  const docs = page.getByRole("region", { name: "Registrar documento" });
  await docs.getByLabel("Validade").fill(inDays(10));
  await docs.getByRole("button", { name: "Registrar" }).click();
  await expect(page.getByText(/Vence em 10 dias/)).toBeVisible();
  await expect(page.getByText("Vence em breve").first()).toBeVisible();

  // Renewing: the request form opens already filled in.
  await page.getByRole("link", { name: "Pedir documento" }).click();
  await expect(page.getByText(`${name}: documento atualizado (com validade)`)).toBeVisible();
  await page.goBack();

  // Archive to keep the demo list tidy.
  await page.getByRole("button", { name: "Arquivar" }).click();
  await expect(page.getByText("Obrigação arquivada")).toBeVisible();
});

test("gerente vê a conformidade de um condomínio no desktop", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.getByRole("link", { name: "Conformidade" }).click();
  await expect(page.getByText("Escolha um condomínio")).toBeVisible();
  await page
    .getByRole("navigation", { name: "Filtrar por condomínio" })
    .getByRole("link", { name: /Acácias/ })
    .click();
  await page.getByRole("link", { name: /Seguro obrigatório da edificação/ }).click();
  await expect(page.getByText(/Vence em \d+ dias/)).toBeVisible();
  await expect(page.getByText(/Decidido por Ana/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Registrar decisão" })).toBeVisible();
});
