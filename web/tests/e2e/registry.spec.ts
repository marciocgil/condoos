import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const GERENTE = "diego.gerente@atlantida.example.com";

/** A fictitious CNPJ with valid check digits, new on every run. */
function randomCnpj(): string {
  const base = Array.from({ length: 8 }, () => Math.floor(Math.random() * 10)).concat([0, 0, 0, 1]);
  const digit = (nums: number[]) => {
    const weights =
      nums.length === 12
        ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const r = nums.reduce((sum, n, i) => sum + n * weights[i]!, 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  const d1 = digit(base);
  const d2 = digit([...base, d1]);
  return [...base, d1, d2].join("");
}

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
    await page.getByLabel("CNPJ do fornecedor").fill(randomCnpj());
    await page.getByLabel("Razão social").fill(`Jardins Teste ${tag} Ltda`);
    await page.getByLabel("Objeto").fill("Manutenção de jardins");
    await page.getByLabel("Valor mensal (R$)").fill("1.250,00");
    await page.getByLabel("Mês do reajuste").selectOption("4");
    await page.getByLabel("Início da vigência").fill("2026-04-01");
    await page.getByRole("button", { name: "Cadastrar contrato" }).click();
    await expect(page).toHaveURL(/\/admin\/contratos$/);
    await expect(page.getByText(`Jardins Teste ${tag} Ltda`)).toBeVisible();
  });
});
