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
  source_document_id?: string | null;
  notice_days?: number | null;
  auto_renewal?: boolean | null;
  termination_penalty?: string | null;
  clause_evidence?: Record<string, { excerpt?: string } | undefined>;
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
  can_close: boolean; // the user may close this condominium's competences
  has_competence: boolean; // a competence exists for the portfolio's latest month
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
  history: {
    version: number;
    valid_from: string;
    changed_by: string | null;
    reason: string | null;
    approval_limits: { default?: string; by_category?: Record<string, string> };
    rule_params: Record<string, Record<string, unknown>>;
  }[];
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
  provenance?: Record<string, ProvenanceItem | undefined>;
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
  expenses: number;
  findings_disputed: number;
  disputed_rate: number | null;
  confirmed_at_risk: string;
  cross_tenant_attempts: number;
  denied_by_policy: number;
  board_sessions: number;
  savings_validated_annual: string;
  savings_realized_annual: string;
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

export type AgendaKind =
  "vencimento" | "nf_prevista" | "reajuste" | "aviso_previo" | "fim_contrato";

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

// --------------------------------------------------------------------------- opportunities (D76, D81)

export interface OpportunityRow {
  id: string;
  condominium_id: string;
  condominium_name: string;
  number: string;
  title: string;
  opportunity_type: string;
  status: string;
  supplier_name: string | null;
  presented: boolean;
  headline_stage: string | null;
  headline_annualized: string | null;
  created_at: string;
}

export interface SavingsStage {
  stage: string;
  amount: string;
  periodicity: string;
  annualized_amount: string;
  one_time_cost: string;
  net_amount: string;
  baseline_period_start: string;
  baseline_period_end: string;
  baseline_amount: string;
  method_code: string;
  assumptions: string[];
  confidence: string;
  quality_risks: string;
  recorded_by: string;
  recorded_at: string;
}

export interface OpportunityDetail extends OpportunityRow {
  recommendation: string;
  operational_impact: string;
  legal_contractual_risk: string;
  implementation_readiness: string;
  review_requirement: string;
  findings: { id: string; title: string; rule_code: string; status: string }[];
  stages: SavingsStage[];
  history: {
    at: string;
    who: string;
    action: string;
    from_status: string;
    to_status: string;
    comment: string | null;
  }[];
  allowed_actions: string[];
  follow_up_actions: string[];
  can_adjust: boolean;
}

// --------------------------------------------------------------------------- briefing (D82)

export interface BriefingItem {
  kind: string;
  title: string;
  detail: string;
  ref: { type: string; id: string } | null;
  when: string | null;
  tone: "danger" | "warning" | "info" | "success" | "neutral";
}

export interface Briefing {
  id: string;
  condominium_id: string;
  condominium_name: string;
  local_date: string;
  version: number;
  timezone: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  read_at: string | null;
  headline: string;
  sections: { key: string; title: string; count: number; items: BriefingItem[] }[];
  partial_sources: { source: string; label: string; reason: string }[];
}

// --------------------------------------------------------------------------- actions (D83)

export interface ActionRow {
  id: string;
  condominium_id: string;
  condominium_name: string;
  title: string;
  action_type: string;
  type_label: string;
  status: string;
  cost_cap: string;
  case_id: string | null;
  case_number: string | null;
  requested_by: string;
  created_at: string;
  approval_expires_at: string | null;
}

export interface ActionPayload {
  effect: string;
  reason: string;
  executor: string;
  supplier_id?: string | null;
  due_date?: string | null;
  risks?: string;
  evidence?: Record<string, string>[];
}

export interface ActionDetail extends ActionRow {
  level: string;
  payload: ActionPayload;
  payload_hash: string;
  supplier_name: string | null;
  policy_decision: string;
  policy_version: number;
  policy_reason: string;
  approval_limit: string | null;
  approval_valid_days: number;
  case_title: string | null;
  opportunity_id: string | null;
  approved_by: string | null;
  executed_at: string | null;
  executed_by: string | null;
  execution_note: string | null;
  history: {
    at: string;
    who: string;
    kind: string;
    from_status: string;
    to_status: string;
    comment: string | null;
    payload_hash: string;
  }[];
  allowed_actions: string[];
}

export interface ActionTypes {
  policy_version: number;
  types: { code: string; label: string; level: string; zero_cost_only: boolean }[];
}

export interface AutomationPause {
  id: string;
  automation_type: string;
  label: string;
  reason: string;
  paused_by: string;
  paused_at: string;
  resumed_at: string | null;
  resumed_by: string | null;
}

export interface AutomationPauses {
  can_pause: boolean;
  types: { code: string; label: string }[];
  active: AutomationPause[];
  history: AutomationPause[];
}

export interface StaffAssignment {
  id: string;
  name: string;
  email: string;
  platform_role: string;
  reason: string;
  valid_until: string | null;
  active: boolean;
}

export interface ProvenanceItem {
  source: string;
  page?: number;
  excerpt?: string;
  status?: string;
  confirmed_by?: string;
}

// --------------------------------------------------------------------------- Launch (D90, D91)

export type LaunchGoal = "economizar" | "pendencias" | "fornecedores" | "panorama";
export type ReadinessState = "nao_configurado" | "analise_parcial" | "supervisionada";

export interface LaunchMilestone {
  key: string;
  name: string;
  done: boolean;
  fact: { type: string; id: string } | null;
  when: string | null;
  missing: string[];
  details: Record<string, string | number>;
}

export interface LaunchRequirement {
  key: string;
  label: string;
  met: boolean;
  detail: string;
  entry: boolean;
}

export interface LaunchReadiness {
  capability: string;
  name: string;
  state: ReadinessState;
  state_label: string;
  requirements: LaunchRequirement[];
  coverage: Record<string, string | number>;
}

export interface LaunchStep {
  key: string;
  title: string;
  why: string;
  unlocks: string;
  screen: "enviar" | "contratos" | "assuntos";
  action_label: string;
  primary: boolean;
}

export interface Launch {
  goal: LaunchGoal | null;
  goal_answered: boolean;
  dismissed: boolean;
  postponed: Record<string, string>;
  milestones: LaunchMilestone[];
  readiness: LaunchReadiness[];
  steps: LaunchStep[];
  done_for_you: { key: string; count: number; label: string }[];
}

export type FirstValueStatus =
  "lendo" | "lido" | "lido_parcial" | "nao_contrato" | "nao_identificado" | "falhou";

export interface FirstValueField {
  name: string;
  label: string;
  kind: string;
  state: "lido" | "a_confirmar" | "nao_encontrado";
  value: string | number | string[] | null;
  source: string | null;
  page: number | null;
  excerpt: string | null;
}

export interface FirstValue {
  document_id: string;
  filename: string;
  status: FirstValueStatus;
  message: string;
  doc_type: string;
  fields: FirstValueField[];
  limits: string[];
  next_step: { key: string; title: string } | null;
}

export interface LaunchImplementation {
  id: string;
  name: string;
  in_progress: boolean;
  milestones_done: number;
  milestones_total: number;
  next_milestone: string | null;
  first_access_at: string | null;
  first_value_at: string | null;
  hours_to_first_value: number | null;
  last_activity_at: string | null;
  days_without_activity: number | null;
  postponed_steps: number;
  review_queue: number;
  documents: number;
  corrections_per_document: number | null;
  llm_cost_per_document_usd: string | null;
  readiness: Record<string, ReadinessState>;
}

export interface MonthCoverage {
  month: string;
  contracts_expected: number;
  invoiced: number;
  waiting: number;
  missing: number;
  queue: number;
  covered: boolean;
  label: string;
}

export interface Reconciliation {
  months: MonthCoverage[];
  recurring_without_contract: {
    supplier_id: string;
    supplier: string;
    months: string[];
    label: string;
  }[];
}
