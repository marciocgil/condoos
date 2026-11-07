# PROMPT 03 — Product breakdown, prioridades, dependências e plano de release

Atue como **Product Manager técnico + Delivery Manager**. Leia Especificação Mestra v1.0, Plano Diretor e diagnóstico real do repositório. Seu objetivo é converter o conhecimento em um backlog implementável com valor observável, dependências verificáveis e releases coerentes.

## Tarefa

1. Cruzar 12 CAPs, 65 FRs, histórias existentes e WP-00..24. Não apagar IDs originais.
2. Agrupar em épicos: Identidade, Memória documental, Assuntos, Advisor, Aprovações, Optimize, Operate, Procurement, Governança, Medição.
3. Para cada história, preencher: ID, problema, persona, resultado, FR/CAP, prioridade, valor, esforço estimado como faixa, dependências, dados, interface, API, política, critérios de aceite, teste automatizado/manual, métrica e decisão pendente.
4. Aplicar dois rankings: `segurança/dependência obrigatória` e `valor ao piloto`. Nenhum item de alto valor passa na frente de controle P0 necessário.
5. Estabelecer caminhos críticos e execução paralela permitida; identificar integração/terceiro que ameaça a sequência.
6. Criar **fatias verticais**, cada qual com persistência, API, serviço, autorização, UI, observabilidade e teste. Não usar entregas 'front-end pronto' como marco de negócio.
7. Definir marcos M0–M5, gates G0–G5 e visão dos ciclos C0–C12+ sem prometer datas.
8. Priorizar MVP seguro: VS-01, VS-02, VS-04, VS-03 e VS-05; justificar variações pelo estado real do repositório.
9. Criar backlog de riscos e de pesquisas para hipóteses não confirmadas (ERPs, canais, data quality, preço, retenção).
10. Construir um plano de validação cruzado com o backlog: nenhuma hipótese de valor fica sem experimento ou métrica.

## Saídas obrigatórias

- `docs/backlog.md` com histórias e critérios; `docs/product-roadmap.md` com marcos e gates; `docs/traceability.md` com IDs; `docs/roadmap-status.md` com apenas o que está evidenciado.
- Diagrama de dependências (Mermaid ou lista ordenada), tabela de 10 primeiras histórias, 5 bloqueios e próximos 3 incrementos.
- Tabela `Não fazer agora` com justificativa (pagamentos, biometria, ERP integral, sensores, previsões sem dados).

**Pergunta de fechamento:** 'Qual pequena entrega verificável produz o maior avanço no valor do piloto sem criar risco de autonomia?' Responda com um único próximo incremento.
