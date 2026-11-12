import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, type Cookie, type Page } from "@playwright/test";

import { existingMessageIds, latestMagicLink } from "./mailpit";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

// Each e-mail may ask for 5 access links per hour (a security limit). Tests run serially, so a
// session opened by the magic link is reused for the same user. The sessions are also kept in
// a file of this run (test-results is emptied at the start of each run): after a failed test
// Playwright starts a new worker, and without the file every user would ask a new link and the
// limit would fail the tests that come after.
const SESSIONS_FILE = path.join(process.cwd(), "test-results", ".e2e-sessions.json");

function loadSessions(): Map<string, Cookie[]> {
  try {
    if (existsSync(SESSIONS_FILE)) {
      return new Map(
        Object.entries(JSON.parse(readFileSync(SESSIONS_FILE, "utf8")) as Record<string, Cookie[]>),
      );
    }
  } catch {
    // A broken file only means new links.
  }
  return new Map();
}

function saveSessions(): void {
  mkdirSync(path.dirname(SESSIONS_FILE), { recursive: true });
  writeFileSync(SESSIONS_FILE, JSON.stringify(Object.fromEntries(sessions)));
}

const sessions = loadSessions();

async function landed(page: Page): Promise<boolean> {
  await page.goto("/");
  await page.waitForURL(/\/(resumo|carteira|login|inicio|dia-a-dia|implantacao)/);
  if (page.url().includes("/login")) return false;
  await toTabs(page);
  return true;
}

/** The síndico now starts guided (D127): "/inicio" or the day to day. Most tests work on the
 * tabs of one condominium ("Hoje"), so they start there; tests of the guided screens go to
 * them on purpose. */
async function toTabs(page: Page): Promise<void> {
  const day = page.url().match(/\/(?:dia-a-dia|implantacao)\/([^/?#]+)/);
  if (day) {
    await page.goto(`/condominio/${day[1]}/resumo`);
    await page.waitForURL(/\/resumo$/);
  }
}

export async function loginAs(page: Page, email: string): Promise<void> {
  const cached = sessions.get(email);
  if (cached) {
    await page.context().clearCookies();
    await page.context().addCookies(cached);
    if (await landed(page)) return;
    sessions.delete(email); // expired or revoked: ask a new link
    saveSessions();
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
  await page.waitForURL(/\/(resumo|carteira|inicio|dia-a-dia\/[^/]+|implantacao\/[^/]+)$/);
  await toTabs(page);
  sessions.set(email, await page.context().cookies());
  saveSessions();
}
