import { expect, test } from "@playwright/test";

import { latestMagicLink } from "./mailpit";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

async function loginAs(page: import("@playwright/test").Page, email: string) {
  const startedAt = new Date(Date.now() - 1000);
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByRole("button", { name: "Receber link de acesso" }).click();
  await expect(page.getByRole("status")).toContainText("Se o e-mail estiver cadastrado");
  const link = await latestMagicLink(email, startedAt);
  // The link points to WEB_BASE_URL; keep the path so the test works on any host.
  await page.goto(new URL(new URL(link).pathname + new URL(link).search, BASE).toString());
}

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
  await expect(page.getByRole("cell", { name: /Jardim das Acácias/ })).toBeVisible();
  await expect(page.getByRole("cell", { name: /Mirante do Vale/ })).toBeVisible();
});

test("link inválido mostra mensagem de erro", async ({ page }) => {
  await page.goto("/auth/verify?token=invalido");
  // Next.js also renders an empty role="alert" route announcer; match ours by its text.
  await expect(
    page.getByRole("alert").filter({ hasText: "Link inválido ou expirado" }),
  ).toBeVisible();
});
