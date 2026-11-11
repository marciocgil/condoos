"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";

export type Governance = {
  competencia: string;
  can_edit: boolean;
  accounts: { id: string; label: string; kind: string; closing_balance: string | null }[];
  funds: {
    id: string;
    name: string;
    kind: string;
    purpose: string | null;
    account_ids: string[];
    balance: {
      opening: string | null;
      inflows: string | null;
      outflows: string | null;
      yield: string | null;
      closing: string | null;
    } | null;
  }[];
  budget: {
    id: string;
    year: number;
    version: number;
    approved_on: string | null;
    document: string | null;
    lines: { category: string; label: string; budgeted: string; realized: string }[];
  } | null;
  notes: { id: string; category: string; label: string; text: string; at: string }[];
  categories: { key: string; label: string }[];
  approvals: {
    id: string;
    body: string;
    period: string;
    approved_on: string;
    document: string | null;
    signatories: { nome?: string; cargo?: string; papel?: string }[];
    with_reservations: boolean;
  }[];
  board: { id: string; name: string; position: string; term_end: string | null }[];
  documents: { id: string; name: string; doc_type: string }[];
};

const KIND_LABEL: Record<string, string> = {
  corrente: "Conta corrente",
  aplicacao: "Aplicação",
  poupanca: "Poupança",
};
const input =
  "h-9 rounded-[var(--radius-button)] border border-control bg-transparent px-2 text-sm";

function useAction() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  async function run(fn: () => Promise<{ ok: boolean; error?: string }>, done: string) {
    setBusy(true);
    setMessage(null);
    const r = await fn();
    setBusy(false);
    setMessage(r.ok ? done : (r.error ?? "Não foi possível salvar."));
    if (r.ok) router.refresh();
  }
  return { busy, message, run };
}

function Status({ message }: { message: string | null }) {
  return message ? (
    <p role="status" className="text-sm">
      {message}
    </p>
  ) : null;
}

/** What each bank account is: the checking account or an investment with its own statement. */
export function AccountKindSelect({
  condominiumId,
  account,
}: {
  condominiumId: string;
  account: Governance["accounts"][number];
}) {
  const { busy, message, run } = useAction();
  return (
    <span className="inline-flex flex-col gap-1">
      <select
        aria-label={`Tipo da conta ${account.label}`}
        className={input}
        defaultValue={account.kind}
        disabled={busy}
        onChange={(e) =>
          void run(
            () =>
              send("PUT", `/condominiums/${condominiumId}/audit/accounts/${account.id}`, {
                kind: e.target.value,
              }),
            "Tipo da conta salvo.",
          )
        }
      >
        {Object.entries(KIND_LABEL).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
      <Status message={message} />
    </span>
  );
}

/** Which accounts back a fund (several funds may share one). */
export function FundAccounts({
  condominiumId,
  fund,
  accounts,
}: {
  condominiumId: string;
  fund: Governance["funds"][number];
  accounts: Governance["accounts"];
}) {
  const { busy, message, run } = useAction();
  const [chosen, setChosen] = useState<string[]>(fund.account_ids);
  return (
    <div className="space-y-1">
      {accounts.map((a) => (
        <label key={a.id} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={chosen.includes(a.id)}
            onChange={(e) =>
              setChosen(e.target.checked ? [...chosen, a.id] : chosen.filter((x) => x !== a.id))
            }
          />
          {a.label} ({KIND_LABEL[a.kind] ?? a.kind})
        </label>
      ))}
      <Button
        disabled={busy}
        onClick={() =>
          void run(
            () =>
              send("PUT", `/condominiums/${condominiumId}/audit/funds/${fund.id}`, {
                account_ids: chosen,
              }),
            "Contas de lastro salvas.",
          )
        }
      >
        Salvar contas de lastro
      </Button>
      <Status message={message} />
    </div>
  );
}

export function NewFundForm({ condominiumId }: { condominiumId: string }) {
  const { busy, message, run } = useAction();
  const [name, setName] = useState("");
  const [kind, setKind] = useState("reserva");
  function submit(e: FormEvent) {
    e.preventDefault();
    void run(
      () => send("POST", `/condominiums/${condominiumId}/audit/funds`, { name, kind }),
      "Fundo criado.",
    );
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col text-xs text-fg-2">
        Nome do fundo
        <input
          className={input}
          value={name}
          onChange={(e) => setName(e.target.value)}
          minLength={3}
          required
        />
      </label>
      <label className="flex flex-col text-xs text-fg-2">
        Tipo
        <select className={input} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="reserva">Reserva</option>
          <option value="obras">Obras</option>
          <option value="outro">Outro</option>
        </select>
      </label>
      <Button type="submit" disabled={busy}>
        Criar fundo
      </Button>
      <Status message={message} />
    </form>
  );
}

async function upload(path: string, form: FormData): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`/api${path}`, { method: "POST", body: form });
  const body = (await res.json().catch(() => null)) as {
    detail?: string;
    erros?: string[];
  } | null;
  if (!res.ok) return { ok: false, error: body?.detail ?? "Não foi possível importar." };
  if (body?.erros?.length)
    return { ok: false, error: `Importado com erro em: ${body.erros.slice(0, 3).join(" ")}` };
  return { ok: true };
}

export function FundBalancesImport({ condominiumId }: { condominiumId: string }) {
  const { busy, message, run } = useAction();
  return (
    <div className="space-y-1">
      <label className="inline-flex cursor-pointer items-center gap-2">
        <input
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          aria-label="Importar saldos dos fundos"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            const form = new FormData();
            form.append("file", file);
            void run(
              () => upload(`/condominiums/${condominiumId}/audit/funds/import`, form),
              "Saldos importados.",
            );
          }}
        />
        <span className="inline-flex h-9 items-center gap-2 rounded-[var(--radius-button)] border border-control px-3 text-sm">
          <Upload size={14} aria-hidden /> Saldos dos fundos (CSV)
        </span>
      </label>
      <p className="text-xs text-fg-2">
        Colunas: fundo; competencia; saldo inicial; entradas; saidas; rendimentos; saldo final.
        Célula vazia fica vazia (nunca zero).
      </p>
      <Status message={message} />
    </div>
  );
}

export function BudgetImport({
  condominiumId,
  year,
  documents,
}: {
  condominiumId: string;
  year: number;
  documents: Governance["documents"];
}) {
  const { busy, message, run } = useAction();
  const [file, setFile] = useState<File | null>(null);
  const [approvedOn, setApprovedOn] = useState("");
  const [doc, setDoc] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("year", String(year));
    if (approvedOn) form.append("approved_on", approvedOn);
    if (doc) form.append("source_document_id", doc);
    void run(
      () => upload(`/condominiums/${condominiumId}/audit/budget/import`, form),
      "Orçamento importado (nova versão).",
    );
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-xs text-fg-2">
          Planilha do orçamento de {year}
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="Planilha do orçamento"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label className="flex flex-col text-xs text-fg-2">
          Aprovado em
          <input
            type="date"
            className={input}
            value={approvedOn}
            onChange={(e) => setApprovedOn(e.target.value)}
          />
        </label>
        <label className="flex flex-col text-xs text-fg-2">
          Ata da aprovação
          <select className={input} value={doc} onChange={(e) => setDoc(e.target.value)}>
            <option value="">(sem documento)</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" disabled={busy || !file}>
          Importar orçamento
        </Button>
      </div>
      <p className="text-xs text-fg-2">
        Colunas: categoria; mes; valor. Linha sem mês é anual e vira doze meses iguais.
      </p>
      <Status message={message} />
    </form>
  );
}

export function BudgetNoteForm({
  condominiumId,
  competencia,
  categories,
}: {
  condominiumId: string;
  competencia: string;
  categories: Governance["categories"];
}) {
  const { busy, message, run } = useAction();
  const [category, setCategory] = useState(categories[0]?.key ?? "");
  const [text, setText] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    void run(
      () =>
        send("POST", `/condominiums/${condominiumId}/audit/budget/notes`, {
          competencia,
          category,
          text,
        }),
      "Explicação registrada.",
    );
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col text-xs text-fg-2">
        Categoria
        <select className={input} value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-w-[260px] flex-1 flex-col text-xs text-fg-2">
        Explicação do desvio
        <input
          className={input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          minLength={10}
          required
        />
      </label>
      <Button type="submit" disabled={busy}>
        Registrar
      </Button>
      <Status message={message} />
    </form>
  );
}

export function AccountsApprovalForm({
  condominiumId,
  competencia,
  board,
  documents,
}: {
  condominiumId: string;
  competencia: string;
  board: Governance["board"];
  documents: Governance["documents"];
}) {
  const { busy, message, run } = useAction();
  const [body, setBody] = useState("conselho_fiscal");
  const [start, setStart] = useState(competencia);
  const [end, setEnd] = useState(competencia);
  const [approvedOn, setApprovedOn] = useState("");
  const [doc, setDoc] = useState(documents[0]?.id ?? "");
  const [members, setMembers] = useState<string[]>([]);
  const [chair, setChair] = useState("");
  const [secretary, setSecretary] = useState("");
  const [reservations, setReservations] = useState(false);
  function submit(e: FormEvent) {
    e.preventDefault();
    const signatories =
      body === "assembleia"
        ? [
            { nome: chair, papel: "presidente da mesa" },
            { nome: secretary, papel: "secretário da mesa" },
          ]
        : members.map((id) => ({ board_member_id: id }));
    void run(
      () =>
        send("POST", `/condominiums/${condominiumId}/audit/accounts-approvals`, {
          body,
          period_start: start,
          period_end: end,
          approved_on: approvedOn,
          document_id: doc,
          signatories,
          with_reservations: reservations,
        }),
      "Aprovação das contas registrada.",
    );
  }
  return (
    <form onSubmit={submit} className="space-y-2" data-testid="accounts-approval-form">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-xs text-fg-2">
          Quem aprovou
          <select className={input} value={body} onChange={(e) => setBody(e.target.value)}>
            <option value="conselho_fiscal">Conselho fiscal</option>
            <option value="conselho_consultivo">Conselho consultivo</option>
            <option value="assembleia">Assembleia</option>
          </select>
        </label>
        <label className="flex flex-col text-xs text-fg-2">
          De (mês)
          <input
            type="month"
            className={input}
            value={start}
            onChange={(e) => setStart(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col text-xs text-fg-2">
          Até (mês)
          <input
            type="month"
            className={input}
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col text-xs text-fg-2">
          Aprovada em
          <input
            type="date"
            className={input}
            value={approvedOn}
            onChange={(e) => setApprovedOn(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col text-xs text-fg-2">
          Documento (ata ou parecer)
          <select className={input} value={doc} onChange={(e) => setDoc(e.target.value)} required>
            {documents.length === 0 && <option value="">Envie a ata primeiro</option>}
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {body === "assembleia" ? (
        <div className="flex flex-wrap gap-2">
          <label className="flex flex-col text-xs text-fg-2">
            Presidente da mesa
            <input
              className={input}
              value={chair}
              onChange={(e) => setChair(e.target.value)}
              required
            />
          </label>
          <label className="flex flex-col text-xs text-fg-2">
            Secretário da mesa
            <input
              className={input}
              value={secretary}
              onChange={(e) => setSecretary(e.target.value)}
              required
            />
          </label>
        </div>
      ) : (
        <fieldset className="text-sm">
          <legend className="text-xs text-fg-2">Signatários (corpo diretivo)</legend>
          {board.map((m) => (
            <label key={m.id} className="mr-4 inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={members.includes(m.id)}
                onChange={(e) =>
                  setMembers(
                    e.target.checked ? [...members, m.id] : members.filter((x) => x !== m.id),
                  )
                }
              />
              {m.name} ({m.position})
            </label>
          ))}
        </fieldset>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={reservations}
          onChange={(e) => setReservations(e.target.checked)}
        />
        Aprovada com ressalvas
      </label>
      <Button type="submit" disabled={busy || !doc}>
        Registrar aprovação
      </Button>
      <Status message={message} />
    </form>
  );
}
