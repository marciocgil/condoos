import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// CondoOS Audit, cycle 1 (D122): the farol, a control with "how it was produced", and the
// full prompt of an agent with its version.
test.beforeEach(() => {
  test.skip(test.info().project.name !== "admin-desktop", "telas do desktop");
});

test("gerente roda a auditoria do mês e vê como um controle foi produzido", async ({ page }) => {
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.getByRole("link", { name: "Farol" }).click();
  await expect(page.getByRole("heading", { name: "Farol da auditoria" })).toBeVisible();
  await page
    .getByRole("link", { name: /Jardim das Acácias/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Rodar auditoria do mês" }).click();
  await expect(page.getByRole("status")).toContainText("Execução");
  await expect(page.getByTestId("farol-counts")).toBeVisible();
  await expect(page.locator('[data-testid^="control-"]')).toHaveCount(25);
  await page.getByTestId("control-BAN-01").getByRole("link").click();
  await expect(page.getByRole("heading", { name: /BAN-01/ })).toBeVisible();
  const produced = page.getByTestId("produced-by");
  await expect(produced).toContainText("Como este resultado foi produzido?");
  await expect(produced).toContainText("prompt versão");
  await expect(produced).toContainText("A4");
});

test("equipe CondoOS lê o prompt integral de A4 e a versão em vigor", async ({ page }) => {
  await loginAs(page, "fabio.admin@condoos.example.com");
  await page.getByRole("link", { name: "Agentes & Prompts" }).click();
  await expect(page.locator('[data-testid^="agent-A"]')).toHaveCount(10);
  await page.getByRole("link", { name: "A4 — Bancário" }).click();
  await expect(page.getByTestId("prompt-text")).toContainText(
    "Você é A4, agente de conciliação bancária",
  );
  await expect(page.getByTestId("active-prompt")).toContainText("SHA-256");
  await page.getByRole("link", { name: "Regras, não prompts" }).click();
  await expect(page.getByTestId("rule-BAN-01")).toContainText("ao centavo");
});
