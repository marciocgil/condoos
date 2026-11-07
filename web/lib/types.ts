export type Role =
  | "sindico"
  | "subsindico"
  | "conselheiro"
  | "gerente"
  | "analista"
  | "zelador"
  | "fornecedor"
  | "morador"
  | "condoos_admin"
  | "condoos_reviewer";

export interface CondoMembership {
  id: string;
  name: string;
  slug: string;
  management_company_id: string | null;
  roles: Role[];
  permissions: string[];
}

export interface Me {
  id: string;
  name: string;
  email: string;
  condominiums: CondoMembership[];
  management_companies: { id: string; name: string; roles: Role[] }[];
  /** CondoOS staff roles (D77): condoos_admin | condoos_reviewer. */
  platform_roles: Role[];
}

export interface Condominium {
  id: string;
  name: string;
  slug: string;
  cnpj: string;
  units: number;
  address: string;
}

export interface Competence {
  id: string;
  month: string;
  status: "aberta" | "fechada";
}

export interface Expense {
  id: string;
  competence: string;
  amount: string;
  category: string;
  description: string;
}

export interface Contract {
  id: string;
  supplier_id: string;
  supplier_name: string | null;
  object: string;
  monthly_value: string;
  adjustment_index: string;
  adjustment_index_other?: string | null;
  adjustment_base_month: number | null;
  start_date: string;
  end_date: string | null;
  amendments?: number;
  supplier_cnpj?: string | null;
  scope_items?: string[];
  original_monthly_value?: string | null;
  billing_frequency_months?: number;
}

export type Severity = "alta" | "media" | "baixa";
export type FindingStatus =
  | "aguardando_validacao"
  | "publicado"
  | "confirmado"
  | "contestado"
  | "ignorado"
  | "descartado"
  | "superado"
  | "pendente_evidencia";

export interface Finding {
  id: string;
  rule_code: string;
  severity: Severity;
  title: string;
  explanation: string;
  amount_at_risk: string;
  status: FindingStatus;
  competence: string;
  ai_assisted: boolean;
  supplier_id: string | null;
  supplier_name: string | null;
  category: string | null;
  category_label: string | null;
}

export interface Evidence {
  kind: string;
  id: string;
  label: string;
  excerpt: string;
  file_url: string | null;
  page: number | null;
}

export interface DecisionItem {
  id: string;
  action: string;
  comment: string | null;
  user_name: string;
  decided_at: string;
}

export interface FindingDetail extends Finding {
  rule_inputs: Record<string, unknown>;
  evidence: Evidence[];
  supplier: { id: string; name: string; cnpj: string; registration_status: string | null } | null;
  decisions: DecisionItem[];
  comments: { id: string; body: string; user_name: string; created_at: string }[];
  validated_by_management: boolean;
  validated_by_condoos?: boolean;
  allowed_actions: string[];
  can_comment: boolean;
  approval_expense_id?: string | null;
  approvals?: { id: string; approved_by: string; approved_at: string; notes: string | null }[];
  can_record_approval?: boolean;
}

export interface Summary {
  competence: string | null;
  competence_status: string | null;
  amount_at_risk: string;
  findings: number;
  by_severity: Record<Severity, number>;
  top: Finding[];
  expenses: number;
  expenses_total: string;
}

export interface TrailItem {
  finding_id: string;
  finding_title: string;
  rule_code: string;
  competence: string;
  action: string;
  comment: string | null;
  user_name: string;
  decided_at: string;
}

export interface PortfolioRow {
  id: string;
  name: string;
  amount_at_risk: string;
  open_findings: number;
  serious: number;
  pending_validation: number;
  queue_items: number;
  status: "revisar" | "enviado" | "em_dia";
}

export interface Portfolio {
  condominiums: PortfolioRow[];
  amount_at_risk: string;
  open_findings: number;
  serious: number;
  queue_items: number;
  latest_competence: string | null;
}

export interface SupplierRow {
  id: string;
  name: string;
  cnpj: string;
  registration_status: string | null;
  condominiums: string[];
  total_paid_12m: string;
  open_findings: number;
  amount_at_risk: string;
}

export interface PortfolioContract {
  id: string;
  condominium_id: string;
  condominium_name: string;
  supplier_name: string;
  object: string;
  monthly_value: string;
  adjustment_index: string;
  adjustment_index_other?: string | null;
  next_adjustment: string | null;
  end_date: string | null;
  amendments?: number;
}

export interface Settings {
  approval_limits: { default?: string; by_category?: Record<string, string> };
  expense_categories: string[];
  rules: {
    code: string;
    name: string;
    defaults: Record<string, unknown>;
    overrides: Record<string, unknown>;
  }[];
  members: {
    id: string | null;
    name: string;
    email: string;
    role: string;
    scope: string; // condominio | administradora | condoos
    status?: string; // convidado | ativo
    expires_at?: string | null;
  }[];
  board: {
    id: string | null;
    full_name: string;
    position: string;
    term_start: string | null;
    term_end: string | null;
    has_login: boolean;
  }[];
  profile: {
    name: string;
    cnpj: string;
    units: number;
    address: string;
    retention_years: number;
    timezone: string;
    management_company_reviews: boolean;
  };
}

export interface QueueItem {
  kind: "extracao" | "achado_grave" | "casamento";
  id: string;
  condominium_id: string;
  condominium_name: string;
  title: string;
  detail: string;
  created_at: string;
}

export interface QueueCount {
  total: number;
  extracao: number;
  achado_grave: number;
  casamento: number;
}

export interface MatchIssue {
  id: string;
  kind: string;
  description: string;
  subject_type: string;
  subject_id: string;
  candidates: { type: string; id: string; label: string }[];
  status: string;
}

export interface FieldSpec {
  name: string;
  label: string;
  kind: "cnpj" | "doc" | "date" | "month" | "money" | "text" | "list" | "int" | "index";
  required: boolean;
}

export interface Review {
  document_id: string;
  condominium_id: string;
  condominium_cnpj: string;
  original_filename: string;
  mime_type: string;
  doc_type: string;
  reviewable_types: string[];
  fields_by_type: Record<string, FieldSpec[]>;
  values: Record<string, unknown>;
  confidence: Record<string, number>;
  reasons: string[];
  threshold: number;
  file_url: string;
  text_content: string | null;
  reviewed_at: string | null;
}

export interface UploadResult {
  filename: string;
  document_id: string | null;
  duplicate: boolean;
  error: string | null;
}

export interface ChatCitation {
  ref: string;
  kind: "achado" | "despesa" | "contrato" | "documento" | "movimento" | "fornecedor" | "resumo";
  id: string;
  label: string;
}

export interface SuggestedAction {
  tipo: "abrir_achado" | "ver_contrato" | "ver_despesas";
  ref: string | null;
  id: string | null;
  rotulo: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  suggested_action: SuggestedAction | null;
  created_at: string;
}

export interface ChatScreen {
  screen: "resumo" | "achados" | "achado" | "contratos" | "historico" | "carteira" | "outra";
  finding_id?: string;
  competence?: string;
}

export interface MonthlyReport {
  competence: string;
  status: "aberta" | "fechada";
  closed_at: string | null;
  published_at: string | null;
  findings: number;
}

export interface ClosingStatus {
  competence: string;
  status: "aberta" | "fechada";
  pending: { documentos: number; casamentos: number; achados_graves: number };
  can_close: boolean;
}

export interface MetricSummary {
  findings_reviewed: number;
  findings_confirmed: number;
  precision: number | null;
  docs_processed: number;
  docs_automatic: number;
  automatic_rate: number | null;
  review_count: number;
  review_hours_median: number | null;
  llm_cost_usd: string;
  llm_calls: number;
}

export interface Metrics {
  months: string[];
  totals: MetricSummary;
  by_month: (MetricSummary & { month: string })[];
  condominiums: (MetricSummary & { id: string; name: string })[];
}

export interface PendingContract {
  contract_id: string;
  supplier: string;
  object: string;
  expected_value: string;
  status: "faturado" | "sem_nf" | "sem_faturamento" | "aguardando";
  expense_id: string | null;
  billed_value: string | null;
  invoice_number: string | null;
}

export interface PendingOneOff {
  expense_id: string;
  supplier: string | null;
  description: string;
  amount: string;
  issue_date: string;
  invoice_number: string | null;
  approvals: {
    id: string;
    approved_by: string;
    approved_at: string;
    document: string | null;
    document_id: string | null;
  }[];
  pending: boolean;
}

export interface PendingCockpit {
  month: string;
  months: { month: string; open: number }[];
  condominiums: {
    id: string;
    name: string;
    open_count: number;
    contracts: PendingContract[];
    one_off: PendingOneOff[];
  }[];
}

export interface DocumentItem {
  id: string;
  doc_type: string;
  original_filename: string;
  created_at: string;
}

export type AgendaKind = "vencimento" | "nf_prevista" | "reajuste" | "fim_contrato";

export interface AgendaEvent {
  date: string;
  kind: AgendaKind;
  title: string;
  detail: string;
  status: string;
  predicted: boolean;
  amount: string | null;
  contract_id: string | null;
  expense_id: string | null;
  condominium_id?: string;
  condominium?: string;
}

export interface Agenda {
  start: string;
  end: string;
  events: AgendaEvent[];
}

/** Review policy of a condominium (D74). */
export interface ReviewPolicy {
  version: number;
  condominium_specific: boolean;
  rules: {
    object: "finding" | "opportunity";
    match?: { severity?: string[]; rule_code?: string[]; min_amount?: string };
    requirement: "none" | "qualified_review" | "internal_review" | "pending_evidence";
    reviewers?: string[];
  }[];
  has_management_company: boolean;
  management_company_reviews: boolean;
  can_configure: boolean;
}

// --------------------------------------------------------------------------- cases (D75, D80)

export interface Person {
  id: string;
  name: string;
}

export interface CaseRow {
  id: string;
  condominium_id: string;
  condominium_name: string;
  number: string;
  title: string;
  category: string;
  severity: string;
  status: string;
  origin: string;
  owner: Person | null;
  next_action: string | null;
  next_action_due_at: string | null;
  suspended_until: string | null;
  open_tasks: number;
  attention: string[];
  created_at: string;
}

export interface CaseTask {
  id: string;
  title: string;
  assignee: Person | null;
  assignee_label: string | null;
  due_at: string;
  status: string;
  blocked_reason: string | null;
  requires_evidence: boolean;
  overdue: boolean;
  completed_at: string | null;
  can_update: boolean;
  allowed_moves: string[];
}

export interface CaseLink {
  id: string;
  target_type: string;
  target_id: string;
  label: string;
  detail: string | null;
  as_evidence: boolean;
  reason: string | null;
  linked_by: string;
  linked_at: string;
  unlinked_at: string | null;
  active: boolean;
}

export interface CaseEvent {
  id: string;
  at: string;
  who: string;
  kind: string;
  from_value: string | null;
  to_value: string | null;
  reason: string | null;
  details: Record<string, unknown>;
}

export interface CaseDetail extends CaseRow {
  description: string;
  resolution_criterion: string;
  requires_evidence: boolean;
  suspension_reason: string | null;
  created_by: string;
  closed_at: string | null;
  can_manage: boolean;
  can_comment: boolean;
  can_add_evidence: boolean;
  allowed_transitions: string[];
  tasks: CaseTask[];
  links: CaseLink[];
  cited_by: { id: string; number: string; title: string }[];
  events: CaseEvent[];
  people: Person[];
}

export interface CaseRef {
  id: string;
  number: string;
  title: string;
  status: string;
}
