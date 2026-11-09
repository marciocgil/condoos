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
    // D115: the menu hides what the role does not use; the page still refuses.
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

// D119: the CNPJ of a new condominium is checked at the Receita before saving. The answer is
// simulated here: a valid random CNPJ may belong to a real company.
test("admin vê a razão social e a situação do CNPJ antes de cadastrar", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await page.route("**/api/portfolio/cnpj/*", (route) =>
    route.fulfill({
      json: {
        cnpj: "12345678000195",
        available: true,
        found: true,
        legal_name: "CONDOMINIO EDIFICIO FICTICIO",
        trade_name: null,
        status: "BAIXADA",
        status_date: "2020-01-15",
        legal_nature: "Condomínio Edilício",
        is_condominium: true,
        address: { street: "RUA DAS FLORES", number: "100", city: "SAO PAULO", state: "SP" },
      },
    }),
  );
  await loginAs(page, ADMIN);
  await page.getByRole("link", { name: "Novo condomínio" }).click();
  await page.getByLabel("CNPJ").fill("12.345.678/0001-95");
  const card = page.getByRole("region", { name: "Dados na Receita Federal" });
  await expect(card.getByTestId("registry-name")).toHaveText("CONDOMINIO EDIFICIO FICTICIO");
  await expect(card).toContainText("Situação: baixada desde 15/01/2020");
  await expect(card).toContainText("não mostra este CNPJ como ativo");
  await card.getByRole("button", { name: "Usar como nome" }).click();
  await expect(page.getByRole("textbox", { name: "Nome", exact: true })).toHaveValue(
    "CONDOMINIO EDIFICIO FICTICIO",
  );
  await card.getByRole("button", { name: "Usar o endereço" }).click();
  await expect(page.getByRole("textbox", { name: "Endereço", exact: true })).toHaveValue(
    "RUA DAS FLORES, 100 - SAO PAULO/SP",
  );
});
