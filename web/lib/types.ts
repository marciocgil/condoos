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
