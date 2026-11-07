import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

test("síndica vê a agenda no resumo e a lista dos próximos 30 dias", async ({ page }) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  await expect(page.getByRole("heading", { name: /Agenda/ }).first()).toBeVisible();
  await page.getByRole("link", { name: "Ver agenda" }).click();
  await expect(page.getByRole("heading", { name: "Agenda", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Próximos 30 dias" })).toBeVisible();
});

test("gerente navega a agenda do mês e filtra por tipo", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.goto("/admin/agenda?mes=2026-10");
  await expect(page.getByRole("heading", { name: "Agenda", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Outubro de 2026 por dia" })).toBeVisible();
  await page
    .getByRole("group", { name: "Mostrar" })
    .getByRole("link", { name: "Vencimentos" })
    .click();
  await expect(page).toHaveURL(/tipo=vencimento/);
  await expect(page.getByText(/Vencimento ·/).first()).toBeVisible();
  await expect(page.getByText(/Reajuste ·/)).toHaveCount(0);
});
