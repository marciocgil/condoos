import { expect, type Page } from "@playwright/test";

import { latestMagicLink } from "./mailpit";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export async function loginAs(page: Page, email: string): Promise<void> {
  const startedAt = new Date(Date.now() - 1000);
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByRole("button", { name: "Receber link de acesso" }).click();
  await expect(page.getByRole("status")).toContainText("Se o e-mail estiver cadastrado");
  const link = new URL(await latestMagicLink(email, startedAt));
  // The link points to WEB_BASE_URL; keep the path so the test works on any host.
  await page.goto(new URL(link.pathname + link.search, BASE).toString());
  // The verify page consumes the token with a POST and then redirects; wait for it.
  await page.waitForURL(/\/(resumo|carteira)$/);
}
