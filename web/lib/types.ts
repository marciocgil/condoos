export type Role = "sindico" | "subsindico" | "conselheiro" | "gerente" | "analista";

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
  adjustment_base_month: number | null;
  start_date: string;
  end_date: string | null;
}

export type Severity = "alta" | "media" | "baixa";
export type FindingStatus =
  | "aguardando_validacao"
  | "publicado"
  | "confirmado"
  | "contestado"
  | "ignorado"
  | "descartado"
  | "superado";

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
  allowed_actions: string[];
  can_comment: boolean;
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
  next_adjustment: string | null;
  end_date: string | null;
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
  members: { name: string; email: string; role: string; scope: string }[];
  board: { full_name: string; position: string }[];
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
