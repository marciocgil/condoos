import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// VS-04 (D82): the day's briefing, built from records, each item linked to its source.
test("síndica abre o Hoje, segue um item até a fonte e atualiza o briefing", async ({ page }) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  await expect(page.getByRole("link", { name: "Hoje" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Hoje", exact: true })).toBeVisible();
  await expect(page.getByText(/decisão\(ões\) aguardam você/)).toBeVisible();
  // The month's audit summary is still on the same screen.
  await expect(page.getByRole("heading", { name: "Auditoria do mês" })).toBeVisible();

  const version = page.getByText(/versão \d+ de/);
  const before = Number((await version.textContent())?.match(/versão (\d+)/)?.[1]);
  await page.getByRole("button", { name: "Atualizar" }).click();
  await expect(page.getByText(`versão ${before + 1} de`, { exact: false })).toBeVisible();

  const decisions = page
    .locator("div", { has: page.getByRole("heading", { name: /Decisões aguardando você/ }) })
    .last();
  const link = decisions.locator('a[href*="/achados/"]').first();
  test.skip((await link.count()) === 0, "Sem achado aguardando decisão neste banco.");
  await link.click();
  await expect(page).toHaveURL(/\/achados\//);
  await expect(page.getByRole("heading", { name: "Por que foi apontado" })).toBeVisible();
});

test("gerente vê um briefing por condomínio, sem misturar", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.getByRole("link", { name: "Hoje" }).first().click();
  await expect(page.getByRole("heading", { name: "Hoje", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Hoje · .*Jardim das Acácias/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Hoje · .*Mirante do Vale/ })).toBeVisible();
});
