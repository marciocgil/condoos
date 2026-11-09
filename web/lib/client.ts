/** Browser-side calls to the API (through the /api proxy) with readable pt-BR errors. */

const FIELD_LABEL: Record<string, string> = {
  name: "nome",
  full_name: "nome",
  email: "e-mail",
  cnpj: "CNPJ",
  supplier_cnpj: "CNPJ do fornecedor",
  supplier_name: "fornecedor",
  units: "unidades",
  address: "endereço",
  retention_years: "anos de retenção",
  term_start: "início do mandato",
  term_end: "fim do mandato",
  object: "objeto",
  monthly_value: "valor mensal",
  adjustment_base_month: "mês do reajuste",
  start_date: "início da vigência",
  end_date: "fim da vigência",
  slug: "endereço curto (slug)",
  timezone: "fuso horário",
};

type Detail = string | { loc?: (string | number)[]; msg?: string }[] | undefined;

function message(detail: Detail | { message?: string }, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && !Array.isArray(detail) && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => {
        const field = String(d.loc?.[d.loc.length - 1] ?? "");
        const label = FIELD_LABEL[field] ?? field;
        const msg = (d.msg ?? "").replace(/^Value error, /, "");
        return label ? `${label}: ${msg}` : msg;
      })
      .join("; ");
  }
  return fallback;
}

export async function send<T = unknown>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
): Promise<{ ok: true; data: T } | { ok: false; error: string }> {
  try {
    const res = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = (await res.json().catch(() => null)) as ({ detail?: Detail } & T) | null;
    if (!res.ok) {
      return { ok: false, error: message(data?.detail, "Não foi possível salvar. Tente de novo.") };
    }
    return { ok: true, data: data as T };
  } catch {
    return { ok: false, error: "Sem conexão com o servidor. Tente de novo." };
  }
}
