"use client";

import { Archive, Download, ExternalLink, FolderPlus, RotateCcw, Send } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, Field, textareaClass } from "@/components/ui/Field";
import { send } from "@/lib/client";
import { formatDate, formatDateTime } from "@/lib/format";
import type { ComplianceDetail, ComplianceEvidenceRow } from "@/lib/types";

import { ComplianceBadge } from "./ComplianceBadge";

const SOURCE: Record<ComplianceEvidenceRow["source"], string> = {
  pessoa: "informado por pessoa",
  ia: "lido pela IA, a confirmar",
  texto: "lido do texto do documento, a confirmar",
  lendo: "lendo o documento",
};

const EVENT: Record<string, string> = {
  criada: "Cadastrada",
  validada: "Aplicabilidade registrada",
  alterada: "Dados alterados",
  evidencia: "Documento ou datas registrados",
  arquivada: "Arquivada",
  reativada: "Reativada",
};

function months(n: number | null): string {
  if (!n) return "não informada";
  return n === 1 ? "mensal" : `a cada ${n} meses`;
}

function withQuery(href: string, query: URLSearchParams): string {
  return `${href}${href.includes("?") ? "&" : "?"}${query.toString()}`;
}

function fileHref(condominiumId: string, documentId: string): string {
  return `/api/condominiums/${condominiumId}/documents/${documentId}/file`;
}

function useAction(condominiumId: string, obligationId: string) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/condominiums/${condominiumId}/compliance/${obligationId}`;
  async function run(method: "POST" | "PATCH", path: string, body?: unknown): Promise<boolean> {
    setBusy(true);
    setError(null);
    const r = await send(method, `${base}${path}`, body);
    setBusy(false);
    if (!r.ok) {
      setError(r.error);
      return false;
    }
    router.refresh();
    return true;
  }
  return { busy, error, run };
}

function ErrorLine({ error }: { error: string | null }) {
  return error ? (
    <p role="alert" className="text-sm text-danger">
      {error}
    </p>
  ) : null;
}

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <p className="text-[13px]">
      <span className="text-fg-2">{label}: </span>
      {children}
    </p>
  );
}

/** Confirm (or correct) the dates the model read from a document: a person has the last word. */
function ConfirmDates({ condominiumId, ob }: { condominiumId: string; ob: ComplianceDetail }) {
  const ev = ob.evidence[0]!;
  const { busy, error, run } = useAction(condominiumId, ob.id);
  const [issued, setIssued] = useState(ev.issued_on ?? "");
  const [until, setUntil] = useState(ev.valid_until ?? "");
  return (
    <Card tone="highlight" aria-label="Conferir datas">
      <CardTitle>Confira as datas lidas</CardTitle>
      <p className="text-sm text-fg-2">
        {ev.valid_until || ev.issued_on
          ? "Estas datas foram lidas do documento. Abra o arquivo, confira e confirme ou corrija."
          : (ev.note ?? "Não encontrei a validade no documento. Informe a data.")}
      </p>
      {ev.document && (
        <a
          href={fileHref(condominiumId, ev.document.id)}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
        >
          <ExternalLink size={14} aria-hidden /> {ev.document.filename}
        </a>
      )}
      {ev.quote && (
        <blockquote className="mt-2 border-l-2 border-line pl-3 text-[13px] text-fg-2">
          “{ev.quote}”
        </blockquote>
      )}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Field id="cf-issued" label="Emissão">
          <input
            id="cf-issued"
            type="date"
            className={controlClass}
            value={issued}
            onChange={(e) => setIssued(e.target.value)}
          />
        </Field>
        <Field id="cf-until" label="Validade">
          <input
            id="cf-until"
            type="date"
            className={controlClass}
            value={until}
            onChange={(e) => setUntil(e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-3">
        <Button
          variant="primary"
          disabled={busy || (!issued && !until)}
          onClick={() =>
            run("POST", `/evidence/${ev.id}/confirm`, {
              issued_on: issued || null,
              valid_until: until || null,
            })
          }
        >
          Confirmar datas
        </Button>
      </div>
      <ErrorLine error={error} />
    </Card>
  );
}

function Validation({ condominiumId, ob }: { condominiumId: string; ob: ComplianceDetail }) {
  const { busy, error, run } = useAction(condominiumId, ob.id);
  const [applies, setApplies] = useState(ob.applicability !== "nao_aplicavel");
  const [period, setPeriod] = useState<string>(
    String(ob.periodicity_months ?? ob.suggested_months ?? ""),
  );
  const [reason, setReason] = useState("");
  return (
    <Card aria-label="Se aplica ao condomínio">
      <CardTitle>Se aplica ao condomínio?</CardTitle>
      {ob.validated_at ? (
        <p className="text-[13px] text-fg-2">
          Decidido por {ob.validated_by ?? "pessoa removida"} em {formatDateTime(ob.validated_at)}:{" "}
          {ob.validation_reason}
        </p>
      ) : (
        <p className="text-[13px] text-fg-2">
          {ob.hint && <span className="mb-1 block text-info">Sugestão: {ob.hint.text}</span>}
          Ainda não confirmado. Regras mudam por cidade, estado e equipamento: confirme com o
          responsável técnico ou a administradora.
        </p>
      )}
      {ob.can_validate && (
        <div className="mt-3 space-y-3">
          <fieldset className="flex gap-4 text-sm">
            <legend className="sr-only">Se aplica</legend>
            <label className="flex items-center gap-2">
              <input type="radio" checked={applies} onChange={() => setApplies(true)} /> Se aplica
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={!applies} onChange={() => setApplies(false)} /> Não se
              aplica
            </label>
          </fieldset>
          {applies && (
            <Field
              id="v-period"
              label="Renova a cada quantos meses"
              hint={
                ob.suggested_months
                  ? `Sugestão: ${months(ob.suggested_months)}. Confirme com o responsável técnico.`
                  : "Varia por caso: confirme com o responsável técnico. Pode ficar em branco."
              }
            >
              <input
                id="v-period"
                type="number"
                min={1}
                max={120}
                className={controlClass}
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
              />
            </Field>
          )}
          <Field id="v-reason" label="Motivo" required hint="Quem orientou ou onde consta.">
            <textarea
              id="v-reason"
              className={textareaClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <Button
            variant="primary"
            disabled={busy || reason.trim().length < 3}
            onClick={async () => {
              const ok = await run("POST", "/validation", {
                applies,
                reason,
                periodicity_months: applies && period ? Number(period) : null,
              });
              if (ok) setReason("");
            }}
          >
            Registrar decisão
          </Button>
          <ErrorLine error={error} />
        </div>
      )}
    </Card>
  );
}

function Evidence({ condominiumId, ob }: { condominiumId: string; ob: ComplianceDetail }) {
  const { busy, error, run } = useAction(condominiumId, ob.id);
  const [doc, setDoc] = useState("");
  const [issued, setIssued] = useState("");
  const [until, setUntil] = useState("");
  return (
    <Card aria-label="Registrar documento">
      <CardTitle>Registrar documento ou datas</CardTitle>
      <p className="text-[13px] text-fg-2">
        Escolha o documento (apólice, laudo, certificado). Se deixar as datas em branco, a IA lê as
        datas no documento e você confere.
      </p>
      <div className="mt-3 space-y-3">
        <Field id="e-doc" label="Documento">
          <select
            id="e-doc"
            className={controlClass}
            value={doc}
            onChange={(e) => setDoc(e.target.value)}
          >
            <option value="">Sem documento (só as datas)</option>
            {ob.documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename} · {formatDate(d.created_at)}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="e-issued" label="Emissão">
            <input
              id="e-issued"
              type="date"
              className={controlClass}
              value={issued}
              onChange={(e) => setIssued(e.target.value)}
            />
          </Field>
          <Field id="e-until" label="Validade">
            <input
              id="e-until"
              type="date"
              className={controlClass}
              value={until}
              onChange={(e) => setUntil(e.target.value)}
            />
          </Field>
        </div>
        <Button
          variant="primary"
          disabled={busy || (!doc && !issued && !until)}
          onClick={async () => {
            const ok = await run("POST", "/evidence", {
              document_id: doc || null,
              issued_on: issued || null,
              valid_until: until || null,
            });
            if (ok) {
              setDoc("");
              setIssued("");
              setUntil("");
            }
          }}
        >
          {doc && !issued && !until ? "Registrar e ler as datas" : "Registrar"}
        </Button>
        <ErrorLine error={error} />
      </div>
    </Card>
  );
}

function Settings({ condominiumId, ob }: { condominiumId: string; ob: ComplianceDetail }) {
  const { busy, error, run } = useAction(condominiumId, ob.id);
  const [lead, setLead] = useState(ob.lead_days);
  const [responsible, setResponsible] = useState(ob.responsible ?? "");
  const [supplier, setSupplier] = useState(ob.supplier?.id ?? "");
  return (
    <Card aria-label="Aviso e responsável">
      <CardTitle>Aviso e responsável</CardTitle>
      <div className="space-y-3">
        <Field id="s-lead" label="Avisar quantos dias antes do vencimento">
          <input
            id="s-lead"
            type="number"
            min={1}
            max={365}
            className={controlClass}
            value={lead}
            onChange={(e) => setLead(Number(e.target.value))}
          />
        </Field>
        <Field id="s-supplier" label="Fornecedor responsável">
          <select
            id="s-supplier"
            className={controlClass}
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
          >
            <option value="">Nenhum</option>
            {ob.suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        <Field id="s-resp" label="Outro responsável" hint="Ex.: zelador, engenheiro, corretora.">
          <input
            id="s-resp"
            className={controlClass}
            value={responsible}
            onChange={(e) => setResponsible(e.target.value)}
          />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={busy}
            onClick={() =>
              run("PATCH", "", {
                lead_days: lead,
                responsible,
                supplier_id: supplier || null,
                clear_supplier: !supplier,
              })
            }
          >
            Salvar
          </Button>
          <Button
            variant="ghost"
            disabled={busy}
            icon={
              ob.archived ? <RotateCcw size={14} aria-hidden /> : <Archive size={14} aria-hidden />
            }
            onClick={() => run("POST", "/archive", { archived: !ob.archived })}
          >
            {ob.archived ? "Reativar" : "Arquivar"}
          </Button>
        </div>
        <ErrorLine error={error} />
      </div>
    </Card>
  );
}

/** One compliance obligation (D112): its situation, whether it applies (a person decides),
 * the documents and dates registered (the model's reading waits for a person) and the history.
 * Nothing here is sent outside the system. */
export function ComplianceDetailView({
  condominiumId,
  ob,
  requestHref,
  caseHref,
}: {
  condominiumId: string;
  ob: ComplianceDetail;
  /** Page that prepares a document request (query string appended). */
  requestHref: string;
  /** Page that opens a new case (query string appended). */
  caseHref: string;
}) {
  const s = ob.situation;
  const who = ob.supplier?.name ?? ob.responsible ?? "";
  const requestQuery = new URLSearchParams({
    item: `${ob.name}: documento atualizado (com validade)`,
    ...(who ? { para: who } : {}),
    ...(ob.supplier ? { papel: "fornecedor" } : {}),
  });
  const caseQuery = new URLSearchParams({ titulo: `Renovar: ${ob.name}` });
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">{ob.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <ComplianceBadge situation={s} />
          <span className="text-sm">{s.text}</span>
        </div>
        {s.to_confirm && <p className="mt-1 text-[13px] text-warning">{s.to_confirm}</p>}
        {s.computed && (
          <p className="mt-1 text-[13px] text-fg-2">
            Validade calculada pela emissão e pela periodicidade confirmada.
          </p>
        )}
        <div className="mt-2 space-y-0.5">
          <Line label="Área">{ob.category_label}</Line>
          <Line label="Renovação">{months(ob.periodicity_months)}</Line>
          <Line label="Aviso">{ob.lead_days} dias antes do vencimento</Line>
          {who && <Line label="Responsável">{who}</Line>}
        </div>
      </div>

      {ob.can_export && (
        <a
          href={`/api/condominiums/${condominiumId}/compliance/${ob.id}/dossier.pdf`}
          className={buttonClass("secondary", "sm")}
        >
          <Download size={14} aria-hidden /> Baixar dossiê (PDF)
        </a>
      )}

      {ob.pending_confirmation && ob.can_manage && (
        <ConfirmDates key={ob.pending_confirmation} condominiumId={condominiumId} ob={ob} />
      )}

      <Validation condominiumId={condominiumId} ob={ob} />

      {ob.can_manage && !ob.archived && ob.applicability !== "nao_aplicavel" && (
        <>
          <Evidence condominiumId={condominiumId} ob={ob} />
          <div className="flex flex-wrap gap-2">
            <Link
              href={withQuery(requestHref, requestQuery)}
              className={buttonClass("secondary", "sm")}
            >
              <Send size={14} aria-hidden /> Pedir documento
            </Link>
            <Link href={withQuery(caseHref, caseQuery)} className={buttonClass("secondary", "sm")}>
              <FolderPlus size={14} aria-hidden /> Criar assunto de renovação
            </Link>
          </div>
        </>
      )}

      {ob.can_manage && <Settings condominiumId={condominiumId} ob={ob} />}

      <Card aria-label="Documentos registrados">
        <CardTitle>Documentos e datas registrados</CardTitle>
        {ob.evidence.length === 0 ? (
          <p className="text-[13px] text-fg-2">Nenhum documento registrado no CondoOS.</p>
        ) : (
          <ul className="divide-y divide-line text-[13px]">
            {ob.evidence.map((e) => (
              <li key={e.id} className="py-2">
                <span className="block">
                  {e.valid_until ? `Validade ${formatDate(e.valid_until)}` : "Sem validade"}
                  {e.issued_on && ` · emissão ${formatDate(e.issued_on)}`} · {SOURCE[e.source]}
                </span>
                <span className="block text-fg-2">
                  {formatDateTime(e.created_at)}
                  {e.document && (
                    <>
                      {" · "}
                      <a
                        href={fileHref(condominiumId, e.document.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
                      >
                        {e.document.filename}
                      </a>
                    </>
                  )}
                  {e.note && ` · ${e.note}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card aria-label="Histórico">
        <CardTitle>Histórico</CardTitle>
        <ul className="space-y-1 text-[13px]">
          {ob.events.map((e, i) => (
            <li key={`${e.at}-${i}`}>
              {formatDateTime(e.at)} · {EVENT[e.kind] ?? e.kind}
              {e.by ? ` · ${e.by}` : " · sistema"}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
