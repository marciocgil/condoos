import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const ADMIN = "fabio.admin@condoos.example.com";
const REVISORA = "gabriela.revisora@condoos.example.com";
const SINDICA = "ana.sindica@acacias.example.com";

// CB-018 (D77): the CondoOS admin assigns a reviewer to a condominium and removes it.
test("admin atribui e remove a revisora pela tela de Configurações", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, ADMIN);
  await page.goto("/admin/configuracoes");
  await page.getByRole("link", { name: "Jardim das Acácias" }).click();
  await page.waitForURL(/configuracoes\?condominio=/);
  const card = page.locator("section, article, div").filter({
    has: page.getByText("Equipe CondoOS", { exact: true }),
  });
  await expect(page.getByText("Equipe CondoOS", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Atribuir" }).first().click();
  await page.getByLabel("E-mail").last().fill(REVISORA);
  await page.getByLabel("Motivo").last().fill("Cobertura de férias da revisão");
  await page.getByRole("button", { name: "Atribuir", exact: true }).last().click();
  await expect(page.getByText(`Atribuição criada para ${REVISORA}.`)).toBeVisible();
  const remove = page.getByRole("button", { name: /Remover atribuição de Gabriela/ });
  await expect(remove).toBeVisible();
  page.once("dialog", (d) => void d.accept());
  await remove.click();
  await expect(page.getByText(/Atribuição removida/)).toBeVisible();
  await expect(remove).toHaveCount(0);
  await expect(card.getByText("Encerrada").first()).toBeVisible();
});

// CB-019 (D74): the síndica sees and changes who reviews findings, on the phone.
test("síndica vê e muda quem revisa os achados em Ajustes", async ({ page }) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, SINDICA);
  await page.getByRole("link", { name: "Ajustes" }).click();
  await expect(page.getByText("Quem revisa os achados")).toBeVisible();
  const allow = page.getByRole("button", { name: "Permitir à administradora" });
  const remove = page.getByRole("button", { name: "Retirar da administradora" });
  const allowedFirst = await remove.isVisible();
  await (allowedFirst ? remove : allow).click();
  await expect(allowedFirst ? allow : remove).toBeVisible();
  await (allowedFirst ? allow : remove).click(); // back as it was
  await expect(allowedFirst ? remove : allow).toBeVisible();
});

// CB-023 and CB-028: filter the queue and link a contract from the case screen.
test("síndica filtra a fila e vincula um contrato ao assunto", async ({ page }) => {
  test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, SINDICA);
  const me = (await (await page.request.get("/api/me")).json()) as {
    condominiums: { id: string }[];
  };
  const id = me.condominiums[0]!.id;
  const title = `Portão da garagem ${Date.now()}`;
  const created = await page.request.post(`/api/condominiums/${id}/cases`, {
    data: {
      title,
      category: "seguranca",
      severity: "alta",
      next_action: "Chamar o técnico do portão",
      next_action_due_at: new Date(Date.now() + 2 * 86400_000).toISOString(),
      resolution_criterion: "Portão abrindo e fechando normalmente",
      create_anyway_reason: "Teste automatizado: assunto distinto",
    },
  });
  expect(created.status()).toBe(201);

  await page.goto(`/condominio/${id}/assuntos`);
  await page.getByLabel("Categoria").selectOption("seguranca");
  await page.getByLabel("Prazo").selectOption("7dias");
  await expect(page).toHaveURL(/categoria=seguranca/);
  await page.getByRole("link", { name: new RegExp(title) }).click();

  await page.getByRole("button", { name: "Vincular registro" }).click();
  await page.getByLabel("Tipo").selectOption("contract");
  await page.getByRole("button", { name: "Buscar" }).click();
  const first = page.getByRole("button", { name: /^Vincular / }).first();
  await first.click();
  const reason = page.getByLabel(/Por que também pertence a este assunto/);
  if (await reason.isVisible().catch(() => false)) {
    await reason.fill("Mesmo contrato, outro problema");
    await page.getByRole("button", { name: "Confirmar vínculo" }).click();
  }
  await expect(page.getByRole("button", { name: "Vincular registro" })).toBeVisible();
  await expect(page.getByText("Nenhum registro vinculado.")).toHaveCount(0);
});

// CB-060 and CB-012: the contract shows its notice period with the excerpt; settings keep the
// history of the approval limits.
test("contrato mostra o aviso prévio e Configurações mostram as versões", async ({ page }) => {
  test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "diego.gerente@atlantida.example.com");
  const me = (await (await page.request.get("/api/me")).json()) as {
    condominiums: { id: string; name: string }[];
  };
  const condo = me.condominiums.find((c) => c.name.includes("Acácias"))!;
  const contracts = (await (
    await page.request.get(`/api/condominiums/${condo.id}/contracts`)
  ).json()) as { id: string; notice_days: number | null }[];
  const withNotice = contracts.find((c) => c.notice_days)!;
  await page.goto(`/admin/contratos/${condo.id}/${withNotice.id}`);
  await expect(page.getByText("Rescisão e renovação")).toBeVisible();
  await expect(page.getByText(`${withNotice.notice_days} dias`, { exact: true })).toBeVisible();
  await expect(page.getByText(/aviso prévio de \d+ dias/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Enviar nova versão do contrato" })).toBeVisible();

  await page.goto(`/admin/configuracoes?condominio=${condo.id}`);
  await expect(page.getByText("Histórico das alçadas e parâmetros")).toBeVisible();
  await expect(page.getByLabel("Motivo da mudança")).toBeVisible();
});
