import { expect, type Cookie, type Page } from "@playwright/test";

import { existingMessageIds, latestMagicLink } from "./mailpit";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

// Each e-mail may ask for 5 access links per hour (a security limit). Tests run serially in
// one worker, so a session opened by the magic link is reused for the same user.
const sessions = new Map<string, Cookie[]>();

async function landed(page: Page): Promise<boolean> {
  await page.goto("/");
  await page.waitForURL(/\/(resumo|carteira|login)/);
  return !page.url().includes("/login");
}

export async function loginAs(page: Page, email: string): Promise<void> {
  const cached = sessions.get(email);
  if (cached) {
    await page.context().clearCookies();
    await page.context().addCookies(cached);
    if (await landed(page)) return;
    sessions.delete(email); // expired or revoked: ask a new link
  }
  const startedAt = new Date(Date.now() - 1000);
  const seen = await existingMessageIds(email);
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByRole("button", { name: "Receber link de acesso" }).click();
  await expect(page.getByRole("status")).toContainText("Se o e-mail estiver cadastrado");
  const link = new URL(await latestMagicLink(email, startedAt, seen));
  // The link points to WEB_BASE_URL; keep the path so the test works on any host.
  await page.goto(new URL(link.pathname + link.search, BASE).toString());
  // The verify page consumes the token with a POST and then redirects; wait for it.
  await page.waitForURL(/\/(resumo|carteira)$/);
  sessions.set(email, await page.context().cookies());
}
