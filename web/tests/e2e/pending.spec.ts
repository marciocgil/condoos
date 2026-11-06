import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const GERENTE = "diego.gerente@atlantida.example.com";

test.describe("gerente — pendências", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  });

  test("vê o faturamento dos contratos e vincula aprovação a um avulso", async ({ page }) => {
    await loginAs(page, GERENTE);
    await page.getByRole("link", { name: "Pendências" }).click();
    await expect(page.getByRole("heading", { name: "Pendências", level: 1 })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Faturamento dos contratos" }).first(),
    ).toBeVisible();
    await expect(page.getByText("Faturado").first()).toBeVisible();

    const link = page.getByRole("button", { name: "Vincular aprovação" }).first();
    test.skip((await link.count()) === 0, "nenhum avulso sem aprovação neste mês do seed");
    await link.click();
    await page.getByLabel("Data da aprovação").fill("2026-10-01");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(
      page.getByText(/Aprovado por Conselho consultivo em 01\/10\/2026/).first(),
    ).toBeVisible();
  });
});
