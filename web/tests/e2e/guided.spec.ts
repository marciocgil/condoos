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
