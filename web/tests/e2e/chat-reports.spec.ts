import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const SINDICA = "ana.sindica@acacias.example.com";
const GERENTE = "diego.gerente@atlantida.example.com";

test.describe("síndico — chat e relatórios", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  });

  test("pergunta a partir de um achado leva o contexto da tela", async ({ page }) => {
    await loginAs(page, SINDICA);
    await page.getByRole("link", { name: "Achados" }).click();
    await page.goto(page.url().split("?")[0] + "?mes=2026-10");
    await page.locator('a[href*="/achados/"]').first().click();
    await expect(page.getByRole("heading", { name: "Por que foi apontado" })).toBeVisible();
    // LB-085 (D108): without a model the button is not shown and the page says so.
    const ask = page.getByRole("link", { name: "Pergunte ao CondoOS" });
    if (!(await ask.isVisible())) {
      const id = page.url().match(/condominio\/([^/]+)/)?.[1];
      await page.goto(`/condominio/${id}/pergunte`);
      await expect(page.getByText("Indisponível no momento")).toBeVisible();
      return;
    }
    await ask.click();
    await expect(page).toHaveURL(/\/pergunte\?tela=achado&achado=[0-9a-f-]{36}/);
    await expect(page.getByRole("heading", { name: "Pergunte ao CondoOS" })).toBeVisible();
    await expect(page.getByText("Respondendo sobre o achado que você estava vendo")).toBeVisible();
    await expect(page.getByText("Só dados deste condomínio.")).toBeVisible();

    const question = "Explique este achado.";
    await page.getByLabel("Sua pergunta").fill(question);
    await page.getByRole("button", { name: "Enviar pergunta" }).click();
    // With an API key the answer card appears; without one, a clear message and the
    // question stays in the field. Either way nothing breaks.
    const answer = page.getByRole("log").locator("article");
    // (Next.js also renders an empty role="alert" route announcer; take the chat's own.)
    const unavailable = page.getByRole("alert").filter({ hasText: /\S/ });
    await expect(answer.or(unavailable).first()).toBeVisible({ timeout: 120_000 });
    if (await unavailable.isVisible()) {
      await expect(unavailable).toContainText(/chave de API|não respondeu|limite/);
      await expect(page.getByLabel("Sua pergunta")).toHaveValue(question);
    } else {
      await expect(answer.last()).toBeVisible();
    }
  });

  test("baixa o relatório do mês e o histórico", async ({ page }) => {
    await loginAs(page, SINDICA);
    const pdf = page.waitForEvent("download");
    await page.getByRole("link", { name: "Baixar relatório em PDF" }).click();
    expect((await pdf).suggestedFilename()).toMatch(
      /relatorio-jardim-das-acacias-\d{4}-\d{2}\.pdf$/,
    );

    await page.getByRole("link", { name: "Histórico" }).click();
    await expect(page.getByRole("heading", { name: "Relatórios mensais" })).toBeVisible();
    const xlsx = page.waitForEvent("download");
    await page.getByRole("link", { name: "XLSX" }).first().click();
    expect((await xlsx).suggestedFilename()).toMatch(/\.xlsx$/);

    const exportTrail = page.getByRole("link", { name: "Exportar PDF" });
    if (await exportTrail.isVisible()) {
      const trail = page.waitForEvent("download");
      await exportTrail.click();
      expect((await trail).suggestedFilename()).toBe("trilha-de-decisoes-jardim-das-acacias.pdf");
    }
  });
});

test.describe("gerente — chat e fechamento", () => {
  test.beforeEach(() => {
    test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  });

  test("pergunte à IA escolhe um condomínio por vez", async ({ page }) => {
    await loginAs(page, GERENTE);
    await page.goto("/admin/pergunte");
    const picker = page.getByRole("navigation", { name: "Condomínio da conversa" });
    expect(await picker.getByRole("link").count()).toBeGreaterThanOrEqual(2);
    await picker.getByRole("link", { name: /Mirante do Vale/ }).click();
    await expect(page.getByText("Condomínio Edifício Mirante do Vale").last()).toBeVisible();
    await expect(picker.getByRole("link", { name: /Mirante do Vale/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("fechar mês com fila pendente é recusado", async ({ page }) => {
    await loginAs(page, GERENTE);
    const row = page.getByRole("row", { name: /Jardim das Acácias/ });
    const close = row.getByRole("button", { name: "Fechar mês" });
    test.skip(!(await close.isVisible()), "o mês de Acácias já foi fechado neste banco");
    // The refusal needs a pending item: once the seed's serious findings were all validated
    // (by the validation test in earlier runs), closing is rightly accepted.
    test.skip(
      (await row.getByText("Revisar").count()) === 0,
      "sem pendências em Acácias. Rode `make reset && make up` para recriá-las.",
    );
    page.once("dialog", (d) => void d.accept());
    await close.click();
    await expect(row.getByRole("alert")).toContainText("fila de exceções");
  });
});
