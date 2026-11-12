import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const REVISORA = "gabriela.revisora@condoos.example.com"; // CondoOS reviewer, Mirante do Vale
const SINDICA = "carla.sindica@mirante.example.com";

// VS-03 (D76, D81): contract + invoice → opportunity → internal review → the condominium decides.
test("revisora aprova a oportunidade do reajuste e a síndica decide", async ({ page, browser }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, REVISORA);

  // The R03 case planted in the seed: elevators adjusted 9% against the IGP-M.
  const me = (await (await page.request.get("/api/me")).json()) as {
    condominiums: { id: string; name: string }[];
  };
  const condo = me.condominiums[0]!;
  const findings = (await (
    await page.request.get(`/api/condominiums/${condo.id}/findings?competence=2026-10`)
  ).json()) as { id: string; rule_code: string }[];
  const r03 = findings.find((f) => f.rule_code === "R03");
  test.skip(!r03, "Sem achado R03 no seed. Rode `make reset && make up`.");
  await page.goto(`/admin/achados/${condo.id}/${r03!.id}`);

  const generate = page.getByRole("button", { name: "Gerar oportunidade" });
  test.skip(
    !(await generate.isVisible()),
    "A oportunidade deste achado já foi gerada neste banco. Rode `make reset && make up`.",
  );
  await generate.click();
  await expect(page.getByRole("heading", { name: /Reajuste acima do índice/ })).toBeVisible();
  await expect(page.getByText("Em revisão CondoOS", { exact: true })).toBeVisible();
  await expect(page.getByText("Economia potencial identificada")).toBeVisible();
  await expect(
    page.getByText("ainda não apresentada ao condomínio", { exact: false }),
  ).toBeVisible();
  const url = page.url();

  // Before the review, the síndica does not see it.
  const ctx = await browser.newContext();
  const sindica = await ctx.newPage();
  await loginAs(sindica, SINDICA);
  await sindica.goto(`/condominio/${condo.id}/oportunidades`);
  await expect(sindica.getByText("Nenhuma oportunidade apresentada")).toBeVisible();

  await page.getByRole("button", { name: "Aprovar para o condomínio" }).click();
  await expect(page.getByText("Apresentada ao condomínio", { exact: true })).toBeVisible();
  await expect(page.getByText("Economia estimada validada").first()).toBeVisible();
  expect(page.url()).toBe(url);

  // The síndica finds it on the summary, sees the validated estimate only, and decides.
  await sindica.goto(`/condominio/${condo.id}/resumo`);
  await expect(sindica.getByText(/aguardando sua decisão/)).toBeVisible();
  await sindica
    .getByRole("link", { name: /Reajuste acima do índice/ })
    .first()
    .click();
  await expect(sindica.getByText("Economia estimada validada").first()).toBeVisible();
  await expect(sindica.getByText("Economia potencial identificada")).toHaveCount(0);
  await sindica.getByRole("button", { name: "Aprovar e seguir" }).click();
  await expect(sindica.getByText("Aprovada pelo condomínio", { exact: true })).toBeVisible();
  await expect(sindica.getByText("Economia aprovada para execução")).toBeVisible();
  await expect(sindica.getByRole("link", { name: "Abrir assunto para acompanhar" })).toBeVisible();

  // CB-063: the síndica records the agreement with its document; nothing is paid or sent.
  const oppId = sindica.url().split("/").pop()!;
  const detail = (await (
    await sindica.request.get(`/api/condominiums/${condo.id}/opportunities/${oppId}`)
  ).json()) as { stages: { stage: string; baseline_amount: string }[] };
  const baseline = Number(detail.stages[0]!.baseline_amount);
  await sindica.getByRole("button", { name: "Registrar contratação" }).click();
  await sindica.getByLabel("Documento do acordo").setInputFiles({
    name: "aditivo-reajuste.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from(`%PDF-1.4\n% aditivo ${Date.now()}\n%%EOF\n`),
  });
  await sindica.getByLabel("Novo valor mensal (R$)").fill(String(baseline - 100));
  await sindica.getByRole("button", { name: "Confirmar contratação" }).click();
  await expect(sindica.getByText("Em execução", { exact: true }).first()).toBeVisible();
  await expect(sindica.getByText(/registrou a contratação/)).toBeVisible();
  await ctx.close();
});
