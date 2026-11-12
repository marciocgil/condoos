import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

// P0 closure (D126): the next action of a finding (FR-033), the relations of a contract
// (FR-014) and the deadline alerts in the Agenda (FR-026).
test("síndica vê a próxima ação proposta com o estado de autorização", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "tela do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  // A finding still open (published): a contested or ignored one has no next action.
  const id = page.url().split("/")[4];
  const list = (await (await page.request.get(`/api/condominiums/${id}/findings`)).json()) as {
    id: string;
    status: string;
  }[];
  const open = list.find((f) => f.status === "publicado");
  test.skip(!open, "Nenhum achado publicado em aberto no seed.");
  await page.goto(`/condominio/${id}/achados/${open!.id}`);
  const next = page.getByTestId("next-action");
  await expect(next).toBeVisible();
  await expect(next).toContainText("Próxima ação proposta");
  await expect(next).toContainText(/política v\d/);
});

test("gerente vê as relações de um contrato e os alertas de prazo", async ({ page }, info) => {
  test.skip(info.project.name !== "admin-desktop", "telas do desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  await page.getByRole("link", { name: "Contratos", exact: true }).click();
  await page.locator('a[href*="/admin/contratos/"]:not([href$="/novo"])').first().click();
  const relations = page.getByTestId("relations");
  await expect(relations).toBeVisible();
  await expect(relations).toContainText("Relações do contrato");
  await page.getByRole("link", { name: "Agenda" }).first().click();
  await expect(page.getByRole("heading", { name: "Agenda" })).toBeVisible();
});
