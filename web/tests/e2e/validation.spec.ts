import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// D93 (LF3-b): a second contract of a seed supplier for the same service, with periods that
// cross, is a data conflict. The síndica sees the capability as partial; the manager decides
// which version prevails, with a reason, in the Validation Centre.
// A seed supplier no other test looks for by name: each run adds one contract of it.
const SUPPLIER = { cnpj: "30980381000183", name: "Verde Vivo Paisagismo Ltda" };
const TITLE = "Dois contratos vigentes do mesmo fornecedor para o mesmo serviço";

test("conflito entre contratos: síndica vê análise parcial e a gerente decide", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "admin-desktop", "fluxo do desktop");
  test.setTimeout(90_000);
  await loginAs(page, "diego.gerente@atlantida.example.com");
  const portfolio = await (await page.request.get("/api/portfolio")).json();
  const acacias = portfolio.condominiums.find((c: { name: string }) =>
    c.name.includes("Jardim das Acácias"),
  );
  const r = await page.request.post(`/api/condominiums/${acacias.id}/contracts`, {
    data: {
      supplier_cnpj: SUPPLIER.cnpj,
      supplier_name: SUPPLIER.name,
      object: "Serviço de manutenção de jardins",
      monthly_value: "2900,00",
      adjustment_index: "IPCA",
      start_date: "2026-06-01",
      end_date: "2026-12-31",
    },
  });
  expect(r.status()).toBe(201);

  await loginAs(page, "ana.sindica@acacias.example.com");
  await page.goto(`/condominio/${acacias.id}/ajustes`);
  await expect(page.getByTestId("readiness-C2")).toContainText("Divergência em validação");

  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.goto(`/admin/validacao?condominio=${acacias.id}`);
  await expect(page.getByRole("heading", { name: "Conflitos de dados" })).toBeVisible();
  const cards = page.locator('[data-testid^="issue-"]').filter({ hasText: TITLE });
  await expect(cards.first()).toBeVisible();
  // Earlier runs left more contracts of this supplier: settle every conflict this test made.
  for (let n = await cards.count(); n > 0; n = await cards.count()) {
    const card = cards.first();
    await expect(card.getByText("Em validação")).toBeVisible();
    await card.getByRole("radio").first().check();
    await card.getByLabel("Motivo").fill("Conferido no teste: vale o contrato original assinado.");
    await card.getByRole("button", { name: "Manter a versão escolhida" }).click();
    await expect(cards).toHaveCount(n - 1);
  }
});
