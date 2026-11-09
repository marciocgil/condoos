import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAs } from "./auth";
import { fictitiousCnpj } from "./files";

const CONTRACT = path.resolve(__dirname, "../../../api/tests/fixtures/corpus/20_contrato.pdf");

// Launch F01 (D89) with the guided steps (LB-080, LB-081, D108): a new condominium's
// síndica chooses a goal, follows "Passo 1 de N" to the upload screen that says what was
// asked, sends a contract, sees the reading and goes back to the guide.
test("síndica nova segue o guia passo a passo e volta a ele depois do envio", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(180_000);
  const tag = Date.now();
  const sindica = `sindica.guia-${tag}@novo.example.com`;
  await loginAs(page, "fabio.admin@condoos.example.com");
  const created = await page.request.post("/api/portfolio/condominiums", {
    data: {
      condominium: {
        name: `Condomínio Guia ${tag} (fictício)`,
        slug: `guia-${tag}`,
        cnpj: fictitiousCnpj(tag),
        units: 24,
        address: "Rua Fictícia do Guia, 10 — Cidade Modelo/SP",
        approval_limits: null,
      },
      board: [
        { name: "Síndica do Guia", position: "sindico", term_start: "2026-01-01", email: sindica },
      ],
    },
  });
  expect(created.status()).toBe(201);

  await loginAs(page, sindica);
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  const card = page.getByTestId("journey-card");
  await expect(card.getByRole("heading", { name: "Implantação do seu assessor" })).toBeVisible();
  await card.getByRole("button", { name: "Economizar dinheiro" }).click();
  await expect(card.getByRole("list", { name: "Objetivo inicial" })).toBeHidden();
  await expect(card.getByTestId("journey-progress")).toHaveText("Passo 1 de 5");
  await card.getByText("Marcos e o que cada função precisa").click();
  await expect(card.getByRole("list", { name: "Marcos" }).getByRole("listitem")).toHaveCount(5);

  // The step leads to the upload screen, which says what was asked.
  await card.getByRole("link", { name: "Envie um contrato de serviço contínuo" }).click();
  await expect(page).toHaveURL(/\/enviar\?passo=enviar_contrato/);
  await expect(page.getByTestId("upload-step")).toContainText(
    "Envie um contrato de serviço contínuo",
  );
  await expect(page.getByRole("link", { name: "Hoje" }).first()).toBeVisible();

  const unique = Buffer.concat([readFileSync(CONTRACT), Buffer.from(`\n% e2e ${tag}\n`)]);
  await page.getByLabel("Escolher arquivos").setInputFiles({
    name: `contrato-e2e-${tag}.pdf`,
    mimeType: "application/pdf",
    buffer: unique,
  });
  const reading = page.getByTestId("first-value");
  await expect(reading).not.toContainText("Lendo", { timeout: 120_000 });
  await expect(reading).toContainText("O que esta leitura não cobre");
  await expect(reading).toContainText("não uma auditoria");
  await expect(reading.getByTestId("field-valor_mensal")).toContainText(
    /Lido no documento|A confirmar|Não encontrado/,
  );

  // Back to the guide: the contract is either with the CondoOS team or already counted.
  await page.getByTestId("continue-guide").click();
  await expect(page).toHaveURL(new RegExp(`/condominio/${id}/resumo`));
  const inReview = card.getByTestId("journey-in-review");
  await expect(inReview.or(card.getByText("Passo 2 de 5")).first()).toBeVisible();
  if (await inReview.isVisible()) {
    await expect(inReview).toContainText(/em conferência|em leitura/);
    await page.goto(`/condominio/${id}/contratos`);
    await expect(page.getByTestId("contracts-in-review")).toContainText("em conferência");
  }
  // A new condominium is starting, not late.
  await page.goto(`/condominio/${id}/resumo`);
  const headline = page.getByText(/^(Bom dia|Boa tarde|Boa noite)\. Em /);
  await expect(headline).toContainText("nada pendente com você hoje.");
  await expect(headline).not.toContainText(/\(ões\)|\(s\)/);
  await expect(page.getByTestId("briefing-starting")).toContainText(
    "Ainda não recebemos documentos",
  );
});

// LB-082, LB-083 (D108): a condominium in operation sees its month first, the implementation
// in one line, and the audit block says which month it shows.
test("síndica em operação vê o mês, a implantação resumida e o mês do resumo", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  await page.request.put(`/api/condominiums/${id}/launch/dismissed`, {
    data: { dismissed: false },
  });
  await page.reload();
  const month = page.getByTestId("month-routine");
  await expect(month.getByRole("heading", { name: /^Seu mês: / })).toBeVisible();
  const card = page.getByTestId("journey-card");
  await expect(card).toContainText(/Implantação: \d de 5 marcos/);
  await expect(card.getByRole("list", { name: "Objetivo inicial" })).toHaveCount(0);
  await expect(page.getByTestId("audit-month")).toHaveText(
    /^(Último mês fechado|Mês em aberto \(prévia\)): /,
  );
  const decide = month.getByRole("link", { name: "Decidir o primeiro" });
  if (await decide.isVisible()) {
    await decide.click();
    await expect(page.getByRole("heading", { name: "Por que foi apontado" })).toBeVisible();
    await expect(page.getByTestId("decision-effects")).toContainText("Ignorar: o ponto sai");
  }
});

// LF2-b (D90): the CondoOS team follows implementations across the portfolio.
test("admin CondoOS acompanha implantações, prontidão e tempo até o primeiro valor", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "admin-desktop", "fluxo do desktop");
  await loginAs(page, "fabio.admin@condoos.example.com");
  await page.goto("/admin/carteira");
  const table = page.getByRole("table", { name: "Implantações em andamento" });
  await expect(table).toContainText("Jardim das Acácias");
  await expect(table.getByRole("columnheader", { name: "Próximo marco" })).toBeVisible();

  await page.goto("/admin/configuracoes");
  await expect(page.getByRole("heading", { name: "O que já funciona" })).toBeVisible();
  await expect(page.getByTestId("readiness-C7")).toContainText("Ações com sua aprovação");

  await page.goto("/admin/metricas");
  await expect(page.getByRole("table", { name: "Implantação por condomínio" })).toContainText(
    "Jardim das Acácias",
  );
});

// LB-033 (D94): "Faça por mim" — a batch is read and followed file by file.
test("síndica envia um lote e acompanha a leitura de cada arquivo", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  test.setTimeout(150_000);
  await loginAs(page, "ana.sindica@acacias.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  const corpus = path.resolve(__dirname, "../../../api/tests/fixtures/corpus");
  const stamp = Date.now();
  const file = (name: string) => ({
    name: `${stamp}-${name}`,
    mimeType: "application/pdf",
    buffer: Buffer.concat([
      readFileSync(path.join(corpus, name)),
      Buffer.from(`\n% e2e ${stamp}\n`),
    ]),
  });
  await page.goto(`/condominio/${id}/enviar`);
  await page
    .getByLabel("Escolher arquivos")
    .setInputFiles([file("01_nfse.pdf"), file("17_recibo.pdf")]);
  const batch = page.getByTestId("batch-progress");
  await expect(batch).toBeVisible();
  await expect(batch).toContainText("leitura concluída", { timeout: 120_000 });
  await expect(batch.getByRole("listitem")).toHaveCount(2);
});

// D101 (LF5): the síndica sees the inbound address and changes it; the old one stops.
test("síndica vê o e-mail de entrada e troca o endereço", async ({ page }, info) => {
  test.skip(info.project.name !== "sindico-mobile", "fluxo do celular");
  await loginAs(page, "carla.sindica@mirante.example.com");
  const id = page.url().match(/condominio\/([^/]+)/)?.[1];
  await page.goto(`/condominio/${id}/ajustes`);
  const card = page.getByRole("region", { name: "E-mail de entrada" });
  const address = card.getByTestId("inbound-address");
  const before = await address.innerText();
  expect(before).toMatch(/^mirante-do-vale-[a-z2-9]{8}@/);
  await card.getByRole("button", { name: "Trocar o endereço" }).click();
  await card.getByRole("button", { name: "Trocar endereço", exact: true }).click();
  await expect(address).not.toHaveText(before);
  await expect(address).toHaveText(/^mirante-do-vale-[a-z2-9]{8}@/);
});
