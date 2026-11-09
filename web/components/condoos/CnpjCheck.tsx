"use client";

import { AlertTriangle, Building2, CheckCircle2, CloudOff, SearchX } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";
import { formatDate } from "@/lib/format";

type Lookup = {
  cnpj: string;
  available: boolean;
  found: boolean;
  legal_name: string | null;
  trade_name: string | null;
  status: string | null;
  status_date: string | null;
  legal_nature: string | null;
  is_condominium: boolean | null;
  address: Record<string, string> | null;
};

/** One line from the Receita's address: "RUA X, 100 - BAIRRO, CIDADE/UF". */
export function formatRegistryAddress(a: Record<string, string>): string {
  const street = [a.street, a.number].filter(Boolean).join(", ");
  const place = [a.district, [a.city, a.state].filter(Boolean).join("/")].filter(Boolean);
  return [street, ...place].filter(Boolean).join(" - ");
}

/** The condominium's CNPJ at the Receita (D119), shown before saving: name, situation,
 * legal nature and address, with shortcuts to use them. Never blocks saving: a person
 * decides, and the Receita may be down. */
export function CnpjCheck({
  cnpj,
  onUseName,
  onUseAddress,
}: {
  cnpj: string;
  onUseName: (name: string) => void;
  onUseAddress: (address: string) => void;
}) {
  const digits = cnpj.replace(/\D/g, "");
  const [result, setResult] = useState<Lookup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setResult(null);
    setError(null);
    if (digits.length !== 14) return;
    let stale = false;
    const timer = setTimeout(async () => {
      setBusy(true);
      const r = await send<Lookup>("GET", `/portfolio/cnpj/${digits}`);
      if (stale) return;
      setBusy(false);
      if (!r.ok) return setError(r.error);
      setResult(r.data);
    }, 400);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [digits]);

  if (digits.length !== 14) return null;
  if (busy) return <p className="text-[13px] text-fg-2">Consultando a Receita Federal…</p>;
  if (error)
    return (
      <p role="alert" className="text-[13px] text-danger">
        {error}
      </p>
    );
  if (!result) return null;
  if (!result.available)
    return (
      <p className="flex items-center gap-2 text-[13px] text-fg-2">
        <CloudOff size={14} aria-hidden /> Não foi possível consultar a Receita agora. Você pode
        salvar e conferir depois.
      </p>
    );
  if (!result.found)
    return (
      <p className="flex items-center gap-2 text-[13px] text-warning" role="status">
        <SearchX size={14} aria-hidden /> CNPJ não encontrado na Receita. Confira os números.
      </p>
    );

  const active = result.status === "ATIVA";
  const address = result.address ? formatRegistryAddress(result.address) : null;
  return (
    <div
      aria-label="Dados na Receita Federal"
      role="region"
      className="space-y-2 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3 text-sm"
    >
      <p className="flex items-center gap-2 text-[13px] text-fg-2">
        <Building2 size={14} aria-hidden /> Dados na Receita Federal
      </p>
      <p className="font-medium" data-testid="registry-name">
        {result.legal_name}
      </p>
      {result.trade_name && <p className="text-[13px] text-fg-2">{result.trade_name}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          tone={active ? "success" : "warning"}
          icon={active ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
        >
          Situação: {result.status ? result.status.toLowerCase() : "não informada"}
          {result.status_date && ` desde ${formatDate(result.status_date)}`}
        </Badge>
        {result.legal_nature && (
          <span className="text-[13px] text-fg-2">{result.legal_nature}</span>
        )}
      </div>
      {!active && result.status && (
        <p className="text-[13px] text-warning">
          A Receita não mostra este CNPJ como ativo. Confira o número com a administradora antes de
          salvar.
        </p>
      )}
      {result.is_condominium === false && (
        <p className="text-[13px] text-warning">
          Este CNPJ não está registrado como condomínio. Confira se é o do condomínio, e não o da
          administradora ou de um fornecedor.
        </p>
      )}
      {address && <p className="text-[13px] text-fg-2">{address}</p>}
      <div className="flex flex-wrap gap-2">
        {result.legal_name && (
          <Button size="sm" variant="ghost" onClick={() => onUseName(result.legal_name!)}>
            Usar como nome
          </Button>
        )}
        {address && (
          <Button size="sm" variant="ghost" onClick={() => onUseAddress(address)}>
            Usar o endereço
          </Button>
        )}
      </div>
    </div>
  );
}
