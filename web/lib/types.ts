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

export interface Finding {
  id: string;
  rule_code: string;
  severity: "alta" | "media" | "baixa";
  title: string;
  amount_at_risk: string;
  status: string;
  competence: string;
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
