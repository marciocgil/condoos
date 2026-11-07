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
        approval_limits: { default: "5000.00", by_category: {} },
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
