import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const ADMIN = "fabio.admin@condoos.example.com"; // CondoOS admin, both condominiums
const SINDICA = "ana.sindica@acacias.example.com";
const SINDICA_MIRANTE = "carla.sindica@mirante.example.com";

// VS-05 (D83): request with frozen scope → síndica approves the version on screen → the
// dispatcher hands it to a person (nothing is sent) → the execution is recorded.
test("ação pedida, aprovada pela síndica e executada por uma pessoa", async ({ page, browser }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  const title = `Visita técnica à bomba ${Date.now()}`;
  await loginAs(page, ADMIN);
  const me = (await (await page.request.get("/api/me")).json()) as {
    condominiums: { id: string; name: string }[];
  };
  const condo = me.condominiums.find((c) => c.name.includes("Acácias"))!;

  await page.goto(`/admin/aprovacoes?condominio=${condo.id}`);
  await page.getByRole("link", { name: "Pedir ação" }).click();
  await page.getByLabel("Tipo de ação").selectOption("visita.agendar");
  await page.getByLabel("O que será autorizado").fill(title);
  await page
    .getByLabel("Efeito exato depois da aprovação")
    .fill("Agendar visita técnica para diagnosticar a bomba de recalque 2.");
  await page
    .getByLabel("Por quê, e o impacto de não agir")
    .fill("A bomba desarma desde segunda; sem ela a caixa superior esvazia.");
  await page.getByLabel("Quem executará").fill("Hidráulica do contrato de manutenção");
  await page.getByLabel("Teto de custo (R$)").fill("350,00");
  await page.getByRole("button", { name: "Enviar para aprovação" }).click();

  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("Aguardando aprovação", { exact: true })).toBeVisible();
  await expect(page.getByText(/Nada é enviado pelo sistema/)).toBeVisible();
  // The CondoOS admin asks but never approves (D77).
  await expect(page.getByRole("button", { name: "Aprovar", exact: true })).toHaveCount(0);
  const adminUrl = page.url();

  const ctx = await browser.newContext();
  const sindica = await ctx.newPage();
  await loginAs(sindica, SINDICA);
  await sindica.goto(`/condominio/${condo.id}/aprovacoes`);
  await sindica.getByRole("link", { name: new RegExp(title) }).click();
  await expect(sindica.getByText("Efeito exato")).toBeVisible();
  await expect(sindica.getByText(/Alçada do síndico/)).toBeVisible();
  await sindica.getByRole("button", { name: "Aprovar", exact: true }).click();
  // The worker checks everything again and hands it to a person (no connector in the pilot).
  await expect(async () => {
    await sindica.reload();
    await expect(sindica.getByText("Aprovada, aguardando execução", { exact: true })).toBeVisible({
      timeout: 1000,
    });
  }).toPass({ timeout: 30_000 });
  await ctx.close();

  await page.goto(adminUrl);
  await page.getByRole("button", { name: "Registrar execução" }).click();
  await page.getByLabel("O que foi feito").fill("Visita feita; disjuntor trocado sem custo extra.");
  await page.getByLabel("Custo final (R$)").fill("350,00");
  await page.getByRole("button", { name: "Confirmar execução" }).click();
  await expect(page.getByText("Executada", { exact: true })).toBeVisible();
  await expect(page.getByText("registrou a execução")).toBeVisible();
});

// FR-007 (D83): the síndica pauses every automation, a new request is refused, then resumes.
test("síndica pausa e retoma as automações", async ({ page }) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, SINDICA_MIRANTE);
  const me = (await (await page.request.get("/api/me")).json()) as {
    condominiums: { id: string }[];
  };
  const id = me.condominiums[0]!.id;
  await page.goto(`/condominio/${id}/aprovacoes`);
  await page.getByRole("button", { name: "Pausar", exact: true }).click();
  await page.getByLabel("O que pausar").selectOption("*");
  await page.getByLabel("Motivo").fill("Teste automatizado do kill switch");
  await page.getByRole("button", { name: "Confirmar pausa" }).click();
  await expect(page.getByText("Pausado: Todas as automações")).toBeVisible();

  const refused = await page.request.post(`/api/condominiums/${id}/actions`, {
    data: {
      action_type: "fornecedor.cobrar",
      title: "Cobrar o fornecedor da limpeza",
      cost_cap: "0",
      idempotency_key: `e2e-${Date.now()}`,
      payload: {
        effect: "Cobrar a nota de outubro que não chegou.",
        reason: "Sem a nota a competência não fecha.",
        executor: "Síndica",
      },
    },
  });
  expect(refused.status()).toBe(409);

  await page.getByRole("button", { name: "Retomar" }).click();
  await expect(page.getByText("Automações ativas")).toBeVisible();
});
