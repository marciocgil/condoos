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

// --------------------------------------------------------------------------- cases (D75, D80)

export const CASE_STATUS_LABEL: Record<string, string> = {
  novo: "Novo",
  em_triagem: "Em triagem",
  em_planejamento: "Em planejamento",
  aguardando_aprovacao: "Aguardando aprovação",
  em_execucao: "Em execução",
  aguardando_terceiro: "Aguardando terceiro",
  aguardando_validacao: "Aguardando validação",
  resolvido: "Resolvido",
  cancelado: "Cancelado",
  reaberto: "Reaberto",
  suspenso_justificadamente: "Suspenso",
};

/** Button text for each move (spec §8.2): what the person does, not the state name. */
export const CASE_MOVE_LABEL: Record<string, string> = {
  em_triagem: "Iniciar triagem",
  em_planejamento: "Planejar",
  aguardando_aprovacao: "Pedir aprovação",
  em_execucao: "Executar",
  aguardando_terceiro: "Aguardar terceiro",
  aguardando_validacao: "Enviar para validação",
  resolvido: "Resolver",
  cancelado: "Cancelar",
  reaberto: "Reabrir",
  suspenso_justificadamente: "Suspender",
};

export const CASE_MOVE_NEEDS_REASON = new Set([
  "cancelado",
  "suspenso_justificadamente",
  "reaberto",
  "resolvido",
]);

export const CASE_CATEGORY_LABEL: Record<string, string> = {
  financeiro: "Financeiro",
  contrato: "Contrato",
  manutencao: "Manutenção",
  conformidade: "Conformidade",
  administrativo: "Administrativo",
  atendimento: "Atendimento",
  seguranca: "Segurança",
  obra: "Obra",
  outro: "Outro",
};

export const CASE_SEVERITY_LABEL: Record<string, string> = {
  baixa: "Baixa",
  media: "Média",
  alta: "Alta",
  critica: "Crítica",
};

export const CASE_ORIGIN_LABEL: Record<string, string> = {
  finding: "Achado",
  opportunity: "Oportunidade",
  human_request: "Pedido",
  maintenance: "Manutenção",
  obligation: "Obrigação",
  external_event: "Evento externo",
};

export const CASE_ATTENTION_LABEL: Record<string, string> = {
  sem_dono: "Sem responsável",
  sem_prazo: "Sem prazo",
  atrasado: "Próxima ação atrasada",
  suspensao_vencida: "Suspensão vencida",
};

export const TASK_STATUS_LABEL: Record<string, string> = {
  aberta: "Aberta",
  em_andamento: "Em andamento",
  bloqueada: "Bloqueada",
  concluida: "Concluída",
  cancelada: "Cancelada",
};

export const TASK_MOVE_LABEL: Record<string, string> = {
  em_andamento: "Começar",
  bloqueada: "Bloquear",
  concluida: "Concluir",
  cancelada: "Cancelar",
};

export const LINK_TYPE_LABEL: Record<string, string> = {
  finding: "Achado",
  opportunity: "Oportunidade",
  document: "Documento",
  contract: "Contrato",
  supplier: "Fornecedor",
  expense: "Despesa",
  case: "Assunto",
};

// --------------------------------------------------------------------------- opportunities (D76, D81)

export const OPPORTUNITY_STATUS_LABEL: Record<string, string> = {
  identificada: "Identificada",
  em_revisao_interna: "Em revisão CondoOS",
  devolvida: "Devolvida para ajuste",
  rejeitada: "Rejeitada na revisão",
  aprovada_para_cliente: "Apresentada ao condomínio",
  aprovada_pelo_condominio: "Aprovada pelo condomínio",
  recusada_pelo_condominio: "Recusada pelo condomínio",
  em_execucao: "Em execução",
  implementada: "Implementada",
  resultado_medido: "Resultado medido",
  encerrada: "Encerrada",
};

export const OPPORTUNITY_TYPE_LABEL: Record<string, string> = {
  reajuste: "Reajuste",
  cobranca_inconsistente: "Cobrança acima do contrato",
  renegociacao: "Renegociação",
  racionalizacao_escopo: "Ajuste de escopo",
  recuperacao: "Recuperação",
  compra_alternativa: "Compra alternativa",
  eficiencia_operacional: "Eficiência operacional",
};

/** DV-04: each stage has its own name; estimates are never shown as captured savings. */
export const SAVINGS_STAGE_LABEL: Record<string, string> = {
  potencial: "Economia potencial identificada",
  estimada_validada: "Economia estimada validada",
  aprovada: "Economia aprovada para execução",
  contratada: "Economia contratada ou negociada",
  realizada: "Economia realizada e comprovada",
};

export const OPPORTUNITY_ACTION_LABEL: Record<string, string> = {
  aprovar: "Aprovar para o condomínio",
  ajustar: "Ajustar estimativa",
  devolver: "Devolver",
  rejeitar: "Rejeitar",
  reabrir_revisao: "Reabrir revisão",
  condominio_aprovar: "Aprovar e seguir",
  condominio_recusar: "Recusar",
};

export const OPPORTUNITY_ACTION_VERB: Record<string, string> = {
  aprovar: "aprovou na revisão CondoOS",
  ajustar: "ajustou a estimativa",
  devolver: "devolveu para ajuste",
  rejeitar: "rejeitou",
  reabrir_revisao: "reabriu a revisão",
  condominio_aprovar: "aprovou pelo condomínio",
  condominio_recusar: "recusou pelo condomínio",
  contratada: "registrou a contratação, com o documento do acordo",
  realizada: "mediu a economia nas faturas posteriores",
};

export const OPPORTUNITY_NEEDS_COMMENT = new Set([
  "devolver",
  "rejeitar",
  "reabrir_revisao",
  "condominio_recusar",
]);

export const PERIODICITY_LABEL: Record<string, string> = {
  mensal: "por mês",
  anual: "por ano",
  unica: "uma vez",
};

export const CONFIDENCE_LABEL: Record<string, string> = {
  alta: "Confiança alta",
  media: "Confiança média",
  baixa: "Confiança baixa",
};

// --------------------------------------------------------------------------- actions (D83)

export const ACTION_STATUS_LABEL: Record<string, string> = {
  aguardando_aprovacao: "Aguardando aprovação",
  enfileirada: "Aprovada, na fila",
  aguardando_execucao_manual: "Aprovada, aguardando execução",
  executada: "Executada",
  recusada: "Recusada",
  cancelada: "Cancelada",
  bloqueada: "Bloqueada na conferência",
};

export const ACTION_BUTTON_LABEL: Record<string, string> = {
  aprovar: "Aprovar",
  pedir_ajustes: "Pedir ajustes",
  recusar: "Recusar",
  ajustar: "Ajustar pedido",
  cancelar: "Cancelar pedido",
  registrar_execucao: "Registrar execução",
};

export const ACTION_DECISION_VERB: Record<string, string> = {
  solicitar: "pediu a ação",
  ajustar: "ajustou o pedido",
  aprovar: "aprovou",
  recusar: "recusou",
  cancelar: "cancelou",
  invalidar: "anulou a aprovação",
  despachar: "encaminhou para execução",
  bloquear: "bloqueou na conferência",
  expirar: "aprovação vencida",
  executar: "registrou a execução",
};
