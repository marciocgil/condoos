import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// The farol for the board (D124): the síndico reads what the CondoOS team sent and approved.
test.beforeEach(() => {
  test.skip(test.info().project.name !== "sindico-mobile", "tela do celular");
});

test("síndica abre a aba Auditoria em Finanças", async ({ page }) => {
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().split("/")[4];
  await page.goto(`/condominio/${id}/auditoria`);
  await expect(page.getByRole("heading", { name: "Auditoria do mês" })).toBeVisible();
  await expect(page.getByText("não é a aprovação das contas", { exact: false })).toBeVisible();
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scroll).toBeLessThanOrEqual(390);
});
