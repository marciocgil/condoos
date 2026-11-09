/** The síndico's phone menu by purpose (D115, docs/proposta-menu.md): four tabs, each with
 * its sections. URLs did not change; only how they are grouped. */
export type Section = { slug: string; label: string };
export type Tab = { key: string; label: string; sections: Section[] };

export const SINDICO_TABS: Tab[] = [
  { key: "hoje", label: "Hoje", sections: [{ slug: "resumo", label: "Hoje" }] },
  {
    key: "financas",
    label: "Finanças",
    sections: [
      { slug: "achados", label: "Achados" },
      { slug: "aprovacoes", label: "Aprovações" },
      { slug: "oportunidades", label: "Oportunidades" },
      { slug: "historico", label: "Relatórios" },
    ],
  },
  {
    key: "rotina",
    label: "Rotina",
    sections: [
      { slug: "assuntos", label: "Assuntos" },
      { slug: "agenda", label: "Agenda" },
      { slug: "conformidade", label: "Conformidade" },
      { slug: "pedidos", label: "Pedidos" },
    ],
  },
  {
    key: "documentos",
    label: "Documentos",
    sections: [
      { slug: "contratos", label: "Contratos" },
      { slug: "enviar", label: "Enviar documentos" },
    ],
  },
];

/** The tab and section of a path like /condominio/<id>/<slug>/... */
export function locate(pathname: string): { tab: Tab; section: Section } | null {
  const slug = pathname.split("/")[3];
  for (const tab of SINDICO_TABS) {
    const section = tab.sections.find((s) => s.slug === slug);
    if (section) return { tab, section };
  }
  return null;
}
