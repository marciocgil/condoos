import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";
import { fictitiousCnpj } from "./files";

// LF6-a (D109, gate LG6): the CondoOS admin removes the síndica's access; she loses access
// at once, "Ações com sua aprovação" goes back to partial, and the change shows in the
// capability history with its reason.
test("troca de síndico: acesso removido, capacidade rebaixada e histórico", async ({
  page,
  browser,
}, info) => {
  test.skip(info.project.name !== "admin-desktop", "fluxo do desktop");
  test.setTimeout(120_000);
  const tag = Date.now();
  const email = `sindica.troca-${tag}@troca.example.com`;
  const name = `Síndica Troca ${tag}`;
  await loginAs(page, "fabio.admin@condoos.example.com");
  const created = await page.request.post("/api/portfolio/condominiums", {
    data: {
      condominium: {
        name: `Condomínio Troca ${tag} (fictício)`,
        slug: `troca-${tag}`,
        cnpj: fictitiousCnpj(tag + 7),
        units: 18,
        address: "Rua Fictícia da Troca, 7 — Cidade Modelo/SP",
        approval_limits: { default: "5000.00", by_category: {} },
      },
      board: [{ name, position: "sindico", term_start: "2026-01-01", email }],
    },
  });
  expect(created.status()).toBe(201);
  const id = ((await created.json()) as { id: string }).id;

  // The síndica enters on her phone: the worker records that C7 now works.
  const phone = await browser.newContext();
  const sindica = await phone.newPage();
  await loginAs(sindica, email);
  await expect(async () => {
    const hist = (await (
      await page.request.get(`/api/condominiums/${id}/launch/history`)
    ).json()) as { key: string; to: string }[];
    expect(hist.some((h) => h.key === "C7" && h.to === "supervisionada")).toBeTruthy();
  }).toPass({ timeout: 30_000 });

  // LF6-b (D110): the same check ran the monitors. No management company and no CondoOS
  // reviewer: the team sees the alert in the Validation Centre and handles it.
  await page.goto(`/admin/validacao?condominio=${id}`);
  const alert = page.getByTestId("alert-revisor_ausente");
  await expect(alert).toContainText("Sem revisora CondoOS atribuída");
  await expect(alert).toContainText("Só equipe");
  // While it is open, the síndica does not see the team's alerts in her Ajustes.
  await sindica.goto(`/condominio/${id}/ajustes`);
  await expect(sindica.getByRole("heading", { name: "Ajustes" })).toBeVisible();
  await expect(sindica.getByTestId("alert-revisor_ausente")).toHaveCount(0);
  await alert.getByLabel("O que foi feito").fill("Revisora será atribuída na próxima reunião.");
  await alert.getByRole("button", { name: "Marcar como tratado" }).click();
  await expect(page.getByTestId("alert-revisor_ausente")).toHaveCount(0);

  // The admin removes her access from Configurações.
  await page.goto(`/admin/configuracoes?condominio=${id}`);
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: `Remover acesso de ${name}` }).click();
  await expect(page.getByRole("button", { name: `Remover acesso de ${name}` })).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("readiness-C7")).toContainText("Análise parcial");
  const history = page.getByTestId("capability-history");
  await expect(history).toContainText("Ações com sua aprovação");
  await expect(history).toContainText("Troca de síndico");

  // Residual access is denied: her open session no longer reaches the condominium.
  const r = await sindica.request.get(`/api/condominiums/${id}`);
  expect(r.status()).toBe(404);
  await phone.close();
});
