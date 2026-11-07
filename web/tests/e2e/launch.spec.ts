import path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// The name sorts after the seed condominiums: admin screens open the first one by name.
// F01 of the CondoOS Launch (LF2-b, D91): a condominium created by the CondoOS admin
// (assisted implementation, D89); its new síndica picks a goal, sends a contract from the
// corpus and sees what was read, with doubtful fields labelled and the reading's limits.

const CONTRACT = path.resolve(__dirname, "../../../api/tests/fixtures/corpus/20_contrato.pdf");

function cnpj(): string {
  const base = Array.from({ length: 12 }, () => Math.floor(Math.random() * 10));
  const digit = (nums: number[]) => {
    const weights =
      nums.length === 12
        ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const sum = nums.reduce((acc, n, i) => acc + n * (weights[i] ?? 0), 0);
    const rest = sum % 11;
    return rest < 2 ? 0 : 11 - rest;
  };
  const d1 = digit(base);
  const d2 = digit([...base, d1]);
  return [...base, d1, d2].join("");
}

test("síndica nova escolhe o objetivo, envia o contrato e vê a leitura", async ({
  page,
  browser,
}) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(120_000);
  const tag = Date.now().toString(36);
  const email = `sindica.${tag}@launch.example.com`;

  // The CondoOS admin creates the condominium and invites the síndica (assisted, D89).
  await loginAs(page, "fabio.admin@condoos.example.com");
  const created = await page.request.post("/api/portfolio/condominiums", {
    data: {
      condominium: {
        name: `Residencial Bosque ${tag} (fictício)`,
        slug: `bosque-${tag}`,
        cnpj: cnpj(),
        units: 24,
        address: "Rua Fictícia, 20 — Cidade Modelo/SP",
        approval_limits: null, // assisted onboarding may leave the limit for later (D93)
      },
      board: [{ name: "Síndica Bosque", position: "sindico", term_start: "2026-01-01", email }],
    },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };

  await loginAs(page, email);
  await page.goto(`/condominio/${id}/resumo`);
  const card = page.getByTestId("journey-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Por onde quer começar?", { exact: false })).toBeVisible();
  await card.getByRole("button", { name: "Economizar dinheiro" }).click();
  await expect(card.getByText("Por onde quer começar?", { exact: false })).toBeHidden();
  await expect(card.getByText(/Envie um contrato de serviço contínuo/)).toBeVisible();

  // The page fits the phone: no horizontal scroll at 390 px.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  await card.getByLabel("Escolher o arquivo do contrato").setInputFiles(CONTRACT);
  const reading = page.getByTestId("first-value");
  await expect(reading).toBeVisible({ timeout: 90_000 });
  // Every field says its state in text (and an icon), never by colour alone.
  const states = await reading
    .locator("[data-state]")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-state")));
  expect(states.length).toBeGreaterThan(0);
  for (const s of states) expect(["lido", "a_confirmar", "nao_encontrado"]).toContain(s);
  await expect(reading.getByText("O que esta leitura não cobre")).toBeVisible();
  await expect(reading.getByText(/não uma auditoria/)).toBeVisible();

  // The reading stays on screen while the journey moves on to confirming the contract.
  await expect(card.getByText(/Um revisor vai confirmar os campos do contrato/)).toBeVisible();
  await expect(reading).toBeVisible();
  const progress = (await card.getByText(/Sua implantação/).textContent()) ?? "";
  expect(progress).toMatch(/\d de 5 marcos/);

  // Gate LG2 (D93): without the síndico's limit, actions are off and the screen says why.
  await page.getByRole("link", { name: "Ajustes" }).click();
  const actions = page.getByTestId("readiness").locator('[data-capability="C7"]');
  await expect(actions.getByText("Ainda não configurado")).toBeVisible();
  await expect(actions.getByText("Falta: Alçada do síndico configurada")).toBeVisible();
  await page.goto(`/condominio/${id}/resumo`);

  // The journey lives on the server: another device sees the same goal and progress.
  const cookies = await page.context().cookies();
  const other = await browser.newContext();
  await other.addCookies(cookies);
  const second = await other.newPage();
  await second.goto(`/condominio/${id}/resumo`);
  const again = second.getByTestId("journey-card");
  await expect(again).toBeVisible();
  await expect(again.getByText("Por onde quer começar?", { exact: false })).toBeHidden();
  await expect(again.getByText(/Sua implantação/)).toHaveText(progress);
  await expect(again.getByText(/Um revisor vai confirmar os campos do contrato/)).toBeVisible();
  await other.close();
});

// LB-011 and LB-012 (LF2-c, D92): readiness per capability and implementations in progress.
test("síndica vê em Ajustes o que o CondoOS já consegue fazer", async ({ page }) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  await page.getByRole("link", { name: "Ajustes" }).click();
  const card = page.getByTestId("readiness");
  await expect(card.getByText("O que o CondoOS já consegue fazer")).toBeVisible();
  for (const name of [
    "Perguntas sobre documentos",
    "Leitura de contrato",
    "Confronto de cobranças",
    "Recomendação de economia",
    "Ações com sua aprovação",
    "Documentos esperados",
    "Fechamento do mês",
  ])
    await expect(card.getByText(name, { exact: true })).toBeVisible();
  // Without an API key the assistant is unavailable: said in text, never hidden.
  await expect(card.getByText("Falta: Assistente disponível")).toBeVisible();
});

test("equipe CondoOS acompanha as implantações; gerente não vê", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "fabio.admin@condoos.example.com");
  const section = page.getByRole("region", { name: "Implantações em andamento" });
  await expect(section).toBeVisible();
  await expect(section.getByRole("cell", { name: /Jardim das Acácias/ })).toBeVisible();
  await page.getByRole("link", { name: "Configurações" }).first().click();
  await expect(page.getByTestId("readiness")).toBeVisible();

  await loginAs(page, "diego.gerente@atlantida.example.com");
  await expect(page.getByRole("heading", { name: "Carteira" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Implantações em andamento" })).toHaveCount(0);
});

// LB-031 and LB-037 (LF3-a, D94): coverage month by month, never "completo".
test("gerente vê a cobertura dos últimos meses nas pendências", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.getByRole("link", { name: "Pendências" }).first().click();
  const cards = page.getByTestId("reconciliation");
  await expect(cards.first()).toBeVisible();
  await expect(cards.first().getByText(/Cobertura dos últimos 6 meses/)).toBeVisible();
  await expect(
    cards
      .first()
      .getByText(/^Cobertura( parcial)? de /)
      .first(),
  ).toBeVisible();
  for (const text of await cards.allInnerTexts())
    expect(text.toLowerCase()).not.toContain("complet");
});
