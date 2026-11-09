import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const REVISORA = "gabriela.revisora@condoos.example.com"; // assigned to Mirante do Vale only
const ADMIN = "fabio.admin@condoos.example.com"; // assigned to both condominiums

test.describe("equipe CondoOS (D77)", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  });

  test("revisora vê só o condomínio atribuído e não configura", async ({ page }) => {
    await loginAs(page, REVISORA);
    await expect(page).toHaveURL(/\/admin\/carteira$/);
    const table = page.getByRole("table", { name: "Condomínios da carteira" });
    await expect(table).toContainText("Mirante do Vale");
    await expect(table).not.toContainText("Jardim das Acácias");
    await expect(page.getByRole("link", { name: "Novo condomínio" })).toHaveCount(0);
    // D111: the menu hides what the role does not use; the page still refuses.
    await expect(page.getByRole("link", { name: "Dados do condomínio" })).toHaveCount(0);
    await page.goto("/admin/configuracoes");
    await expect(page.getByText("Sem permissão")).toBeVisible();
  });

  test("admin vê quem revisa os achados e o fuso do condomínio", async ({ page }) => {
    await loginAs(page, ADMIN);
    await expect(page.getByRole("link", { name: "Novo condomínio" })).toBeVisible();
    await page.getByRole("link", { name: "Dados do condomínio" }).first().click();
    await expect(page.getByText("Quem revisa os achados")).toBeVisible();
    await expect(
      page.getByText("Achados graves: revisados por uma pessoa antes de publicar."),
    ).toBeVisible();
    await expect(page.getByText("Administradora revisa achados")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retirar da administradora" })).toBeVisible();
    await expect(page.getByLabel("Fuso horário")).toHaveValue("America/Sao_Paulo");
    await expect(page.getByText("equipe CondoOS").first()).toBeVisible();
  });
});
