import { expect, test, type Page } from "@playwright/test";

import { loginAs } from "./auth";

const SINDICA = "ana.sindica@acacias.example.com";
const GERENTE = "diego.gerente@atlantida.example.com";

/** Opens, one by one, the October findings until one offers the wanted action. */
async function openFindingWith(page: Page, action: string): Promise<string> {
  await page.getByRole("link", { name: "Achados" }).click();
  await expect(page).toHaveURL(/\/achados/);
  await page.goto(page.url().split("?")[0] + "?mes=2026-10");
  const hrefs = await page
    .locator('a[href*="/achados/"]')
    .evaluateAll((els) => els.map((e) => (e as HTMLAnchorElement).getAttribute("href") ?? ""));
  for (const href of hrefs) {
    await page.goto(href);
    if (await page.getByRole("button", { name: action, exact: true }).isVisible()) return href;
  }
  throw new Error(`Nenhum achado com a ação ${action}`);
}

test.describe("síndico", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  });

  test("síndico confirma achado", async ({ page }) => {
    await loginAs(page, SINDICA);
    await openFindingWith(page, "Confirmar");
    await expect(page.getByRole("heading", { name: "Por que foi apontado" })).toBeVisible();
    await expect(page.getByRole("list", { name: "Evidências" })).toBeVisible();
    // LB-086 (D108): what each decision does is said before the click.
    await expect(page.getByTestId("decision-effects")).toContainText("Confirmar: você concorda");
    await page.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("Decisão registrada: Confirmar");
    // ...and after it, the way to the next point or back to Hoje.
    await expect(page.getByRole("link", { name: "Voltar ao Hoje" })).toBeVisible();
    await expect(
      page
        .getByRole("link", { name: "Próximo ponto de atenção" })
        .or(page.getByText("Tudo decidido por enquanto."))
        .first(),
    ).toBeVisible();
    await expect(page.getByText("Confirmado", { exact: true })).toBeVisible();
    await expect(page.getByRole("list", { name: "Histórico de decisões" })).toContainText(
      "Ana Ribeiro Sampaio confirmou o achado",
    );
  });

  // LB-084 (D108): severity in words in the list, not only a colour.
  test("lista de achados mostra a severidade em texto", async ({ page }) => {
    await loginAs(page, SINDICA);
    await page.getByRole("link", { name: "Achados" }).click();
    const first = page.locator('a[href*="/achados/"]').first();
    await expect(first).toContainText(/Grave|Médio|Baixo/);
  });

  test("síndico contesta com comentário", async ({ page }) => {
    await loginAs(page, SINDICA);
    await openFindingWith(page, "Contestar");
    await page.getByRole("button", { name: "Contestar", exact: true }).click();
    const send = page.getByRole("button", { name: "Enviar contestar" });
    await expect(send).toBeDisabled(); // the comment is mandatory
    const reason = `Serviço extra aprovado em reunião (${Date.now()}).`;
    await page.getByLabel("Por que você contesta este achado?").fill(reason);
    await send.click();
    await expect(page.getByRole("status")).toContainText("Decisão registrada: Contestar");
    await expect(page.getByText("Contestado", { exact: true })).toBeVisible();
    await expect(page.getByRole("list", { name: "Histórico de decisões" })).toContainText(reason);
  });
});

test.describe("gerente", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  });

  test("gerente valida achado grave", async ({ page }) => {
    await loginAs(page, GERENTE);
    await page.getByRole("link", { name: "Fila de exceções" }).first().click();
    const validate = page.getByRole("link", { name: "Validar" });
    test.skip(
      (await validate.count()) === 0,
      "Os achados graves do seed já foram validados. Rode `make reset && make up` para recriá-los.",
    );
    await validate.first().click();
    await expect(page.getByText("Aguardando validação", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Validar", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("Decisão registrada: Validar");
    await expect(page.getByText("Validado pela administradora")).toBeVisible();
    await expect(page.getByRole("list", { name: "Histórico de decisões" })).toContainText(
      "Diego Fontes Arruda validou o achado",
    );
  });
});
