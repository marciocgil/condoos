import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const GERENTE = "diego.gerente@atlantida.example.com";

test.describe("gerente — cadastros", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  });

  test("cadastra conselheiro e contrato pela tela", async ({ page }) => {
    const tag = Date.now().toString().slice(-6);
    await loginAs(page, GERENTE);

    await page.goto("/admin/configuracoes");
    await page.getByRole("link", { name: /Mirante do Vale/ }).click();
    await page.getByRole("button", { name: "Adicionar" }).click();
    await page.getByLabel("Nome completo").fill(`Conselheira Teste ${tag}`);
    await page.getByLabel("Início do mandato").fill("2026-01-01");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(page.getByText(`Conselheira Teste ${tag}`)).toBeVisible();

    await page.goto("/admin/contratos");
    await page.getByRole("link", { name: "Novo contrato" }).click();
    await page.getByRole("link", { name: /Mirante do Vale/ }).click();
    // A seed supplier (fictitious and already enriched): a random valid CNPJ may belong to a
    // real company, and the registry lookup would bring real data into the test database.
    const suppliers = (await (await page.request.get("/api/portfolio/suppliers")).json()) as {
      name: string;
      cnpj: string;
    }[];
    const seed = suppliers.find((s) => s.name.startsWith("Verde Vivo"))!;
    await page.getByLabel("CNPJ do fornecedor").fill(seed.cnpj);
    await page.getByLabel("Razão social").fill(seed.name);
    await page.getByLabel("Objeto").fill(`Jardins teste ${tag}`);
    await page.getByLabel("Valor mensal (R$)").fill("1.250,00");
    await page.getByLabel("Mês do reajuste").selectOption("4");
    await page.getByLabel("Início da vigência").fill("2026-04-01");
    await page.getByRole("button", { name: "Cadastrar contrato" }).click();
    await expect(page).toHaveURL(/\/admin\/contratos$/);
    await expect(page.getByText(`Jardins teste ${tag}`)).toBeVisible();
  });
});
