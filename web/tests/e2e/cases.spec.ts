import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";

const SINDICA = "ana.sindica@acacias.example.com";
const ADMIN = "fabio.admin@condoos.example.com";

// VS-01 (D75, D80): a case from opening to resolution with evidence; history stays.
test.describe("assuntos", () => {
  test("síndica abre, acompanha e resolve um assunto com evidência", async ({ page }) => {
    test.skip(test.info().project.name !== "sindico-mobile", "fluxo do celular");
    const title = `Infiltração na garagem ${Date.now()}`;
    await loginAs(page, SINDICA);
    await page.getByRole("link", { name: "Assuntos" }).click();
    await page.getByRole("link", { name: "Novo assunto" }).click();
    await page.getByLabel("Título").fill(title);
    await page.getByLabel("Categoria").selectOption("manutencao");
    await page
      .getByRole("textbox", { name: "Próxima ação", exact: true })
      .fill("Vistoria do zelador");
    await page.getByLabel("Critério de conclusão").fill("Foto do teto seco após o reparo");
    await page.getByRole("button", { name: "Abrir assunto" }).click();
    // Another case of the same category may exist in this database: explain and go on.
    const anyway = page.getByLabel("Por que abrir outro assunto?");
    const heading = page.getByRole("heading", { name: title });
    const duplicate = await Promise.race([
      heading.waitFor().then(() => false),
      anyway.waitFor().then(() => true),
    ]);
    if (duplicate) {
      await expect(page.getByText("Pode já existir um assunto para isso:")).toBeVisible();
      await anyway.fill("Teste automatizado: outro local da garagem");
      await page.getByRole("button", { name: "Abrir assunto" }).click();
    }
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await expect(page.getByText("Novo", { exact: true })).toBeVisible();

    // A task for a person without access.
    await page.getByLabel("O que fazer").fill("Fotografar o teto");
    await page.getByLabel("Nome de quem faz").fill("Zelador Paulo");
    await page.getByRole("button", { name: "Criar tarefa" }).click();
    await expect(page.getByText("Zelador Paulo")).toBeVisible();

    // Cannot resolve yet; walk the states, close the task and attach evidence.
    for (const move of ["Iniciar triagem", "Planejar", "Executar", "Enviar para validação"]) {
      await page.getByRole("button", { name: move, exact: true }).click();
      await expect(page.getByRole("button", { name: move, exact: true })).toHaveCount(0);
    }
    await page.getByRole("button", { name: "Resolver", exact: true }).click();
    await page.getByLabel("Como o critério foi atendido?").fill("Teto seco, conforme foto.");
    await page.getByRole("button", { name: "Confirmar: resolver" }).click();
    await expect(page.getByText("Ainda há 1 tarefa(s) em aberto")).toBeVisible();

    await page.getByRole("button", { name: "Concluir", exact: true }).click();
    await expect(page.getByText("Concluída", { exact: true })).toBeVisible();
    await page.getByLabel("Arquivo (foto, laudo, nota)").setInputFiles({
      name: "teto-seco.jpg",
      mimeType: "image/jpeg",
      // JPEG signature + unique bytes (a new file each run, not a duplicate document).
      buffer: Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.from(` ${Date.now()}`)]),
    });
    await page.getByLabel("O que este arquivo comprova").fill("Foto do teto após o reparo");
    await page.getByRole("button", { name: "Anexar evidência" }).click();
    await expect(page.getByRole("link", { name: "teto-seco.jpg" })).toBeVisible();

    // The reason form stayed open after the refused attempt; open it only if closed.
    const reasonField = page.getByLabel("Como o critério foi atendido?");
    if (!(await reasonField.isVisible())) {
      await page.getByRole("button", { name: "Resolver", exact: true }).click();
    }
    await page.getByLabel("Como o critério foi atendido?").fill("Teto seco, conforme foto.");
    await page.getByRole("button", { name: "Confirmar: resolver" }).click();
    await expect(page.getByText("Resolvido", { exact: true }).first()).toBeVisible();
    const timeline = page.getByRole("list", { name: "Linha do tempo do assunto" });
    await expect(timeline).toContainText("abriu o assunto");
    await expect(timeline).toContainText("anexou evidência");
    await expect(page.getByRole("button", { name: "Reabrir" })).toBeVisible();
  });

  test("administração CondoOS vê os assuntos da carteira", async ({ page }) => {
    test.skip(test.info().project.name !== "admin-desktop", "fluxo do desktop");
    await loginAs(page, ADMIN);
    await page.getByRole("link", { name: "Assuntos" }).first().click();
    await expect(page.getByRole("heading", { name: "Assuntos" })).toBeVisible();
    await page.getByRole("link", { name: "Encerrados" }).click();
    await page.waitForURL(/ver=encerrados/);
    await expect(page.getByRole("table")).toContainText("Infiltração na garagem");
    await expect(page.getByRole("table")).toContainText("Resolvido");
  });
});
