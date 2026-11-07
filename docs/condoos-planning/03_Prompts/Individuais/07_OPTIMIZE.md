# PROMPT 07 — CondoOS Optimize: contratos, faturas, oportunidades e revisão humana

Atue como **Product Engineer + Financial Domain Engineer + QA de IA**. Implemente o primeiro mecanismo de valor financeiro do CondoOS, usando o Core. A primeira entrega deve operar com documentos importados, sem presumir ERP integrado.

## Escopo FR

`FR-041..046` como núcleo; `FR-047..050` após evidência e dados suficientes. Reaproveitar `Document`, `Supplier`, `Case`, `Task`, `Approval`, `Event`, `AuditLog` e políticas.

## Fluxo completo (VS-03)

1. Receber contrato e aditivos; validar origem, vigência, tipo de serviço e versão.
2. Extrair `valor base`, `periodicidade`, `índice`, `data-base`, `prazo de aviso`, `escopo`, `SLA` e `exclusões`, com trecho/página e `confidence_state`.
3. Mostrar interface de revisão humana para campos materiais; nunca calcular com dado incerto como se fosse confirmado.
4. Receber fatura/planilha; normalizar competência, itens, quantidade, tributos e total, mantendo documento de origem.
5. Determinar comparabilidade de escopo; classificar `comparável`, `parcialmente comparável`, `não comparável`.
6. Calcular diferenças em código determinístico e testar arredondamento, reajuste, proporcionalidade, datas e múltiplos aditivos.
7. Gerar `Finding` e `Opportunity` com descrição, evidência, valor potencial, suposições, risco, confiança e ação proposta.
8. Enviar à **fila do revisor humano interno do CondoOS** (não ao condomínio). Revisar/editar/aprovar/reprovar/devolver com justificativa.
9. Somente após aprovação do revisor, preparar o dossiê para o condomínio. Envio externo requer política e canal autorizados.
10. Acompanhar negociação/implantação e medir economia realizada com baseline comparável, descartando mudança de escopo e custos de transição.

## Casos especiais obrigatórios

- Contrato sem assinatura ou sem data validada.
- Fatura duplicada e nota de crédito.
- Vigência de aditivo que muda preço no meio da competência.
- Reajuste por índice com defasagem e arredondamento.
- Preço fixo vs. variável por unidade, posto ou serviço.
- Contrato com taxa adicional excepcional prevista.
- Fornecedor com múltiplos contratos do mesmo condomínio.
- Escopo não comparável (troca de postos, horário, frequência, material).
- Dados insuficientes: classificar como `precisa de revisão`, sem inventar economia.

## Entregáveis e provas

- Esquema versionado de contrato/fatura/oportunidade, parser com procedência e UI de validação.
- Calculadora com testes reproduzíveis e data fixtures anonimizadas/sintéticas.
- Agenda de vencimentos/reajustes e estado de revisão interna.
- Dossiê da recomendação com fontes e cálculo explícito.
- Métrica de economia `identificada`, `validada`, `negociada`, `implantada` e `realizada`; nunca somá-las como dinheiro economizado.
- Testes de não divulgação da oportunidade sem revisão interna e de acesso entre tenants.
- Documento `docs/optimize-validation.md` com riscos, amostras, falsos positivos, custos de revisão e lista de melhorias.

**Gate:** não publicar recomendação se faltar origem, comparabilidade, cálculo verificável ou revisão humana interna aprovada. Não transmitir mensagem ao fornecedor sem autorização específica.
