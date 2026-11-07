export const DOC_TYPE_LABEL: Record<string, string> = {
  nfse: "Nota fiscal de serviço (NFS-e)",
  nfe: "Nota fiscal de produto (NF-e)",
  boleto: "Boleto / conta",
  recibo: "Recibo",
  extrato: "Extrato bancário",
  cnab_retorno: "Retorno CNAB",
  contrato: "Contrato",
  convencao: "Convenção",
  ata: "Ata",
  outro: "Outro",
};

export const SEVERITY_LABEL = { alta: "Grave", media: "Médio", baixa: "Baixo" } as const;
export const SEVERITY_PLURAL = { alta: "graves", media: "médios", baixa: "baixos" } as const;

export const STATUS_LABEL: Record<string, string> = {
  aguardando_validacao: "Aguardando validação",
  publicado: "Novo",
  confirmado: "Confirmado",
  contestado: "Contestado",
  ignorado: "Ignorado",
  descartado: "Descartado",
  // The rule stopped detecting it after new data, before anyone acted (D61).
  superado: "Superado por novos dados",
  // A reviewer asked for more evidence before deciding (D74).
  pendente_evidencia: "Evidência pendente",
};

export const ACTION_LABEL: Record<string, { verb: string; button: string }> = {
  confirmar: { verb: "confirmou", button: "Confirmar" },
  contestar: { verb: "contestou", button: "Contestar" },
  ignorar: { verb: "ignorou", button: "Ignorar" },
  validar: { verb: "validou", button: "Validar" },
  descartar: { verb: "descartou", button: "Descartar" },
  reabrir: { verb: "reabriu", button: "Reabrir" },
  solicitar_evidencia: { verb: "pediu evidência", button: "Pedir evidência" },
};

export const ROLE_LABEL: Record<string, string> = {
  sindico: "Síndico(a)",
  subsindico: "Subsíndico(a)",
  conselheiro: "Conselheiro(a)",
  gerente: "Gerente",
  analista: "Analista",
  zelador: "Zelador(a)",
  fornecedor: "Fornecedor",
  morador: "Morador(a)",
  condoos_admin: "Administração CondoOS",
  condoos_reviewer: "Revisão CondoOS",
};

export const INDEX_LABEL: Record<string, string> = {
  IPCA: "IPCA",
  IGPM: "IGP-M",
  INPC: "INPC",
  FIXO: "Fixo",
  NENHUM: "Sem reajuste",
  OUTRO: "Outro",
};

/** "IGP-DI" for an OUTRO index with a description; the standard label otherwise. */
export function indexLabel(index: string, other?: string | null): string {
  if (index === "OUTRO") return other ? other : "Outro";
  return INDEX_LABEL[index] ?? index;
}
