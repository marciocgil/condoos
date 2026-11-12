import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// The guided síndico (D127): the day to day of one condominium, one screen.
test("síndica abre o dia a dia: envio único, o que chegou e o farol", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "tela do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().split("/")[4];
  await page.goto(`/dia-a-dia/${id}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Jardim das Acácias");
  await expect(page.getByTestId("day-upload")).toBeVisible();
  await expect(page.getByTestId("day-checklist")).toContainText("Notas e boletos");
  await expect(page.getByTestId("day-farol")).toBeVisible();
  await page.getByRole("link", { name: "Ver tudo deste condomínio" }).click();
  await expect(page).toHaveURL(/\/resumo$/);
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scroll).toBeLessThanOrEqual(390);
});

test("o início pergunta o que fazer hoje e leva ao dia a dia", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "tela do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("O que vamos fazer hoje?");
  const choices = page.locator('[data-testid^="choice-"]');
  expect(await choices.count()).toBeLessThanOrEqual(4);
  await choices.first().click();
  await expect(page).toHaveURL(/\/(dia-a-dia|condominio)\//);
});

test("síndica com condomínio em implantação vê o percentual e o próximo passo", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "sindico-mobile", "tela do celular");
  await loginAs(page, "carla.sindica@mirante.example.com");
  const id = page.url().split("/")[4];
  await page.goto(`/implantacao/${id}`);
  await expect(page.getByTestId("implantation-progress")).toContainText(/de 8 itens/);
  await expect(page.getByTestId("implantation-next")).toBeVisible();
  // D130: every pending item opens its own action, not only the next step.
  await page.getByTestId("implantation-item-contas").locator("summary").click();
  await expect(page.getByTestId("implant-upload-extrato")).toContainText("OFX");
  // Implanting starts with the CNPJ (no lookup here: a random valid CNPJ may be a real one).
  await page.goto("/implantar");
  await expect(page.getByTestId("implant-conversation")).toContainText("Qual é o CNPJ");
});

// D129: leaving is a short conversation; a later date shows on the day to day and is undone.
test("síndica marca a saída para outra data, vê o aviso e desfaz", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "tela do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().split("/")[4];
  await page.goto("/inicio");
  await expect(page.getByTestId("choice-encerrar")).toBeVisible();
  await page.goto(`/encerrar/${id}`);
  const talk = page.getByTestId("exit-conversation");
  await expect(talk).toContainText("Por quê?");
  await page.getByRole("radio", { name: "Fim do mandato" }).click();
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("radio", { name: "Outra data" }).click();
  const later = new Date(Date.now() + 20 * 86400000);
  const iso = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(later);
  await page.getByLabel("Até 90 dias").fill(iso);
  await expect(talk).toContainText("nada é apagado");
  await expect(page.getByTestId("exit-dossier")).toBeVisible();
  await page.getByTestId("exit-confirm").click();
  await expect(talk).toContainText("Saída marcada para");

  await page.goto(`/dia-a-dia/${id}`);
  await expect(page.getByTestId("day-exit-pending")).toBeVisible();
  await page.getByTestId("day-exit-pending").click();
  await expect(page.getByTestId("exit-pending")).toBeVisible();
  await page.getByRole("button", { name: "Desfazer a saída" }).click();
  await expect(page.getByTestId("exit-conversation")).toBeVisible();
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scroll).toBeLessThanOrEqual(390);
});
