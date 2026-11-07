import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

test("síndica entra pelo link mágico e vê só o próprio condomínio", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile");
  await loginAs(page, "ana.sindica@acacias.example.com");
  await expect(page).toHaveURL(/\/condominio\/[\w-]+\/resumo/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Condomínio Residencial Jardim das Acácias",
  );
  await expect(page.getByTestId("amount-at-risk")).toBeVisible();
  await page.getByRole("link", { name: "Contratos" }).click();
  await expect(page.getByText("Vigilare Serviços de Portaria Ltda")).toBeVisible();
});

test("gerente entra e vê a carteira com os dois condomínios", async ({ page }, info) => {
  test.skip(info.project.name !== "admin-desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await expect(page).toHaveURL(/\/admin\/carteira/);
  // The Carteira also lists implementations (D90): look at the portfolio table only.
  const portfolio = page.getByRole("table", { name: "Condomínios da carteira" });
  await expect(portfolio.getByRole("cell", { name: /Jardim das Acácias/ })).toBeVisible();
  await expect(portfolio.getByRole("cell", { name: /Mirante do Vale/ })).toBeVisible();
});

test("link inválido mostra mensagem de erro", async ({ page }) => {
  await page.goto("/auth/verify?token=invalido");
  // Next.js also renders an empty role="alert" route announcer; match ours by its text.
  await expect(
    page.getByRole("alert").filter({ hasText: "Link inválido ou expirado" }),
  ).toBeVisible();
});
