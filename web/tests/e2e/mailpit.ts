/** Reads the latest magic link sent to an address through the Mailpit HTTP API. */
const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://localhost:8025";

interface MailpitList {
  messages: { ID: string; To: { Address: string }[]; Created: string }[];
}

export async function latestMagicLink(email: string, after: Date): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt++) {
    const res = await fetch(
      `${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`,
    );
    const list = (await res.json()) as MailpitList;
    const msg = list.messages.find((m) => new Date(m.Created) >= after);
    if (msg) {
      const full = (await (await fetch(`${MAILPIT_URL}/api/v1/message/${msg.ID}`)).json()) as {
        Text: string;
      };
      const match = full.Text.match(/https?:\/\/\S+\/auth\/verify\?token=[\w-]+/);
      if (match) return match[0];
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Nenhum link de acesso recebido para ${email}`);
}
