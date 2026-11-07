# Modelo de dados — evolução após as decisões DV-01..DV-05

Data: 07/11/2026. Decisões de origem: D73–D77 (`docs/decisions.md`). **Status:** plano aprovado pelo Marcio; **0011 e 0012 implementadas** (D79), **0013 implementada** (D80, com as tabelas `case_record` e `case_task`, porque `case` é palavra reservada) e **0014 implementada** (D81; estados do condomínio `aprovada_pelo_condominio`/`recusada_pelo_condominio` e as ações correspondentes em `opportunity_review`). Plano completo. Depois, **0015 (`briefing`)** foi aprovada e entregue à parte (D82), e **0016 (`action_request`, `action_decision` só inclusão, `outbox_event`, `automation_pause`)** também (D83; detalhes em `docs/decisions.md`). **0017** (D85): `condominium_settings_version` (só inclusão), `document.field_provenance`, `document.version`, `document.supersedes_id`, `contract.notice_days`, `auto_renewal`, `termination_penalty`, `clause_evidence`. Diferenças em relação ao texto abaixo: a tabela de papéis de plataforma chama `platform_role` (modelo `PlatformRoleGrant`); o padrão da plataforma não tem regra de `pending_evidence` automática (o estado nasce da ação `solicitar_evidencia`), porque R04/R07 sem IA não geram achado.

Princípios da evolução:
- **Somente acréscimos.** Nenhuma tabela ou coluna existente é removida ou renomeada. Achado, decisão, aprovação (R12), contratos, despesas e regras continuam como estão.
- **Os padrões reproduzem o comportamento atual.** Cada migração vem com valores padrão que mantêm o produto igual para os condomínios existentes; a mudança de comportamento só acontece por configuração explícita.
- **Multi-tenant como hoje.** Toda tabela nova com dados de condomínio tem `condominium_id`, entra em `RLS_TABLES` e tem a política `tenant_isolation` na própria migração (listas congeladas na migração, D32). Tabelas de histórico são só de inclusão, como `decision` e `audit_log` (D14).
- **Dinheiro** em `NUMERIC(14,2)`/`Decimal`, enums em `VARCHAR + CHECK` (D12, D21).

## 1. Visão geral dos objetos

```
                      ┌──────────────┐  N:N (case_link)  ┌──────────────┐
  regras R01–R12 ───► │   finding    │◄─────────────────►│    case      │◄── pedido humano,
  (sem mudança)       │  (achado)    │                   │  (assunto)   │    manutenção,
                      └──────┬───────┘                   └──────┬───────┘    obrigação, evento
                N:N          │ review_requirement               │ 1:N
     (opportunity_finding)   │ + review (decision)              ▼
                      ┌──────▼───────┐                   ┌──────────────┐
                      │ opportunity  │◄── case_link ────►│    task      │
                      └──────┬───────┘                   └──────────────┘
                             │ 1:N (só inclusão)
                      ┌──────▼──────────┐         case_event (só inclusão): timeline do assunto
                      │ savings_record  │  potencial → validada → aprovada → contratada → realizada
                      └─────────────────┘

  review_policy (versionada) ──► decide se finding/opportunity exigem revisão e de quem
  platform_role + condo_assignment ──► CondoOS Admin / CondoOS Reviewer com escopo explícito
```

## 2. Permissões e papéis (D77, ADR-P08)

### 2.1 Papéis

| Papel (decisão DV-05) | Implementação | Escopo | Situação |
|---|---|---|---|
| Síndico | `membership.role = sindico` (existe) | condomínio | Ativo; ganha permissões de Assunto, Oportunidade e aprovação no condomínio |
| Subsíndico | `subsindico` (existe) | condomínio | Ativo, sem mudança |
| Conselho | `conselheiro` (existe) | condomínio | Ativo, sem mudança (leitura e comentário); aprovação só com atribuição formal (futuro) |
| Administradora — colaborador externo | `gerente` e `analista` (existem) no nível da administradora ou do condomínio | administradora/condomínio | Ativo; **deixa de ser obrigatória** (ver 2.3) |
| CondoOS Admin | **novo** `platform_role.role = condoos_admin` | plataforma + condomínios atribuídos | A criar |
| CondoOS Reviewer | **novo** `platform_role.role = condoos_reviewer` | só condomínios atribuídos | A criar |
| Zelador, Fornecedor, Morador | valores reservados no CHECK de `membership.role`, sem permissões | condomínio | **Não ativados** antes de necessidade do piloto |

### 2.2 Tabelas novas

**`platform_role`** (fora do tenant; sem RLS de condomínio, só o papel do dono e a API leem por função dedicada)
`id, user_id → app_user, role ∈ {condoos_admin, condoos_reviewer}, granted_by_user_id, granted_at, expires_at NULL, revoked_at NULL, reason`.

**`condo_assignment`** (RLS por `condominium_id`)
`id, condominium_id, user_id, platform_role ∈ {condoos_admin, condoos_reviewer}, granted_by_user_id, valid_from, valid_until NULL, revoked_at NULL, reason`.
Um usuário de plataforma **só enxerga condomínios atribuídos e vigentes** (menor privilégio, §9.4). Acesso de suporte é uma atribuição temporária com motivo, auditada (*break-glass*).

### 2.3 Colunas acrescentadas

- `membership`: `expires_at NULL`, `revoked_at NULL`, `invited_at NULL`, `accepted_at NULL` — acesso temporário e revogável para externos (administradora, futuros zelador/fornecedor) e convite com prazo (FR-002). Linhas atuais ficam com tudo nulo = acesso permanente, como hoje.
- `membership.role` CHECK passa a aceitar também `zelador`, `fornecedor`, `morador` (reservados; `ROLE_PERMISSIONS` vazio para eles).
- `condominium`: `timezone` (padrão `America/Sao_Paulo`, ADR-P07) e `management_company_reviews` (booleano: a administradora pode validar achados; **padrão `true` para os condomínios existentes, `false` para os criados sem administradora**).

### 2.4 Função de escopo (ponto crítico de segurança)

`app_accessible_condominium_ids(p_user)` ganha um terceiro ramo:
```sql
UNION
SELECT a.condominium_id FROM condo_assignment a
  JOIN platform_role p ON p.user_id = a.user_id AND p.role = a.platform_role
  JOIN app_user u ON u.id = a.user_id AND u.is_active
 WHERE a.user_id = p_user
   AND a.revoked_at IS NULL AND (a.valid_until IS NULL OR a.valid_until > now())
   AND p.revoked_at IS NULL AND (p.expires_at IS NULL OR p.expires_at > now())
```
e os ramos de `membership` passam a ignorar linhas com `revoked_at` ou `expires_at` vencido. Nenhum papel de plataforma vê "todos os condomínios" por padrão.

### 2.5 Permissões (granulares, separando ler / editar / validar / aprovar / executar)

Novas em `Permission`: `MANAGE_CASES`, `UPDATE_TASK`, `REVIEW_FINDING`, `REVIEW_OPPORTUNITY`, `VIEW_OPPORTUNITY_DRAFT`, `APPROVE_IN_CONDO` (aprovação de decisão dentro da competência do síndico; não implica revisão), `CONFIGURE_POLICY`, `MANAGE_PLATFORM`. Matriz completa em `docs/authorization-matrix.md`. `VALIDATE_FINDING` continua existindo para não quebrar D48, mas a validação passa a consultar a política de revisão (seção 3).

## 3. Revisão proporcional ao risco (D74, ADR-P09)

### 3.1 `review_policy` (RLS; versionada, só inclusão)
`id, condominium_id NULL (NULL = padrão da plataforma, lido por função), version, valid_from, created_by_user_id, rules JSONB, reason`.
Cada regra: `{object: finding|opportunity, match: {rule_code?, category?, severity?, min_amount?, max_confidence?, ai_assisted?}, requirement: none|internal_review|qualified_review|pending_evidence, reviewers: [condoos_reviewer, gerente?]}`. A primeira regra que casa vale; regras são avaliadas por código tipado (sem `eval`, §9.2).

**Política padrão da plataforma (reproduz o comportamento atual + DV-02):**
1. `opportunity` → `internal_review` por `condoos_reviewer` (obrigatório no piloto; não editável por condomínio nesta fase).
2. `finding` com `severity = alta` → `qualified_review` (`condoos_reviewer`; `gerente` também se `condominium.management_company_reviews`).
3. `finding` com parte "não avaliada" (R04/R07 sem IA) → `pending_evidence` (hoje esses casos já não geram achado; a regra só formaliza).
4. demais `finding` → `none` (publicados direto, como hoje).

### 3.2 Colunas em `finding`
`review_requirement` (padrão calculado na criação; backfill: `qualified_review` para `alta`, `none` para os demais), `review_policy_version`, `confidence` (`alta|media|baixa`, NULL nos existentes), `category` (NULL nos existentes; preenchida pelas regras novas).
O status `aguardando_validacao` continua significando "aguarda revisão"; **quem** pode revisar passa a vir da política. Status novo `pendente_evidencia` (inconclusivo, DV-02), invisível ao corpo diretivo e fora do valor em risco, como `aguardando_validacao`.
As ações existentes `validar`/`descartar` de `decision` cobrem a revisão; só se acrescenta `solicitar_evidencia` (→ `pendente_evidencia`). Quem decidiu fica em `decision.user_id`, e o papel efetivo em `audit_log.details`.

### 3.3 Alertas urgentes
Nenhuma revisão segura alerta crítico: quando existirem incidentes (FL-08, P2), o protocolo aprovado é exibido sem esperar a fila. No produto atual não há alerta urgente; a regra fica registrada para o motor de política.

## 4. Assunto (D75, ADR-P01 aceita)

### 4.1 `case` (RLS)
`id, condominium_id, number (sequencial por condomínio, ex. "A-2026-0001"), title, description, category, origin ∈ {finding, opportunity, human_request, maintenance, obligation, external_event}, severity ∈ {baixa, media, alta, critica}, status, owner_user_id NULL, next_action, next_action_due_at, suspended_until NULL, suspension_reason NULL, resolution_criterion, created_by_user_id NULL (NULL = sistema), created_at, updated_at`.
Status (§8.2): `novo, em_triagem, em_planejamento, aguardando_aprovacao, em_execucao, aguardando_terceiro, aguardando_validacao, resolvido, cancelado, reaberto, suspenso_justificadamente`.

### 4.2 `case_event` (RLS, só inclusão)
`id, condominium_id, case_id, at, actor_user_id NULL, actor_kind ∈ {user, system, ai}, kind (created, status_changed, owner_changed, due_changed, linked, unlinked, task_*, comment, evidence_added…), from_value, to_value, reason, details JSONB (só ids)`. É a timeline (FR-023); toda transição grava autor, momento e motivo.

### 4.3 `case_link` (RLS)
`id, condominium_id, case_id, target_type ∈ {finding, opportunity, document, contract, supplier, expense, case}, target_id, reason, linked_by_user_id NULL, linked_at, unlinked_at NULL, unlinked_by_user_id NULL`.
N:N nos dois sentidos: um achado pode estar em mais de um assunto; desvincular só preenche `unlinked_at` (histórico preservado). Sem chave estrangeira polimórfica: a integridade é verificada no serviço e por teste; o `condominium_id` do alvo tem de ser o mesmo do assunto (checado no serviço e pelo RLS).

### 4.4 `task` (RLS)
`id, condominium_id, case_id, title, assignee_user_id NULL, assignee_label NULL (externo sem login), due_at, status ∈ {aberta, em_andamento, bloqueada, concluida, cancelada}, blocked_reason, requires_evidence (bool), completed_at, completed_by_user_id`. Mudança de prazo exige motivo (gravado em `case_event`).

### 4.5 Duplicidade antes de criar
Antes de criar, o serviço procura assuntos abertos do mesmo condomínio com sobreposição de vínculos (mesmo contrato, fornecedor ou achado) ou mesma categoria nos últimos N dias e devolve candidatos; a criação só segue com "criar mesmo assim" (motivo) ou "vincular ao existente". Determinístico no primeiro corte; similaridade de texto depois.

## 5. Oportunidade e economia (D76, ADR-P05 aceita)

### 5.1 `opportunity` (RLS)
`id, condominium_id, number, title, opportunity_type ∈ {reajuste, cobranca_inconsistente, renegociacao, racionalizacao_escopo, recuperacao, compra_alternativa, eficiencia_operacional}, status, contract_id NULL, supplier_id NULL, operational_impact, legal_contractual_risk ∈ {baixo, medio, alto}, implementation_readiness ∈ {dados_suficientes, precisa_cotacao, precisa_aprovacao, precisa_parecer}, created_by_user_id NULL, created_at, updated_at`.
Status (Plano §6.4 + DV-04): `identificada → em_qualificacao → em_revisao_interna → (aprovada_para_cliente | devolvida | rejeitada) → apresentada → aprovada_pelo_condominio → em_execucao → implementada → resultado_medido → encerrada`. **Invisível ao corpo diretivo até `aprovada_para_cliente`** (FR-046, OPT-01) — garantido no backend, não só na tela.

### 5.2 `opportunity_finding` (RLS)
`opportunity_id, finding_id, condominium_id, linked_at, unlinked_at NULL`. Uma oportunidade reúne vários achados; pode existir oportunidade sem achado (análise estratégica).

### 5.3 `savings_record` (RLS, só inclusão)
Cada linha é uma **fotografia** de valor, nunca sobrescrita:
`id, condominium_id, opportunity_id, stage ∈ {potencial, estimada_validada, aprovada, contratada, realizada}, amount (NUMERIC), periodicity ∈ {unica, mensal, anual}, annualized_amount, one_time_cost, net_amount, baseline_period_start, baseline_period_end, baseline_amount, method_code (identifica a função de cálculo e sua versão), assumptions JSONB, evidence JSONB (refs), confidence ∈ {alta, media, baixa}, quality_risks, validation_state, recorded_by_user_id NULL, recorded_at, supersedes_id NULL`.
- `potencial`: calculada por código a partir dos achados.
- `estimada_validada`: só pelo `condoos_reviewer` (REVIEW_OPPORTUNITY).
- `aprovada`: registrada pela decisão do síndico (APPROVE_IN_CONDO).
- `contratada`: exige documento (aditivo, novo contrato, acordo) em `evidence`.
- `realizada`: exige faturas posteriores verificadas e baseline comparável; nunca calculada só da promessa.
A interface mostra cada estágio com rótulo próprio e **nunca** soma estágios diferentes; "realizada" só aparece com evidência.

### 5.4 Revisão interna
Reaproveita o padrão de `decision`: tabela `opportunity_review` (RLS, só inclusão) `id, condominium_id, opportunity_id, reviewer_user_id, action ∈ {aprovar, ajustar, devolver, rejeitar}, reason_code, comment, reviewed_version_hash, reviewed_at`. Qualquer mudança material depois de `aprovar` (valor, premissa, evidência) muda o hash e devolve a oportunidade para `em_revisao_interna`.

### 5.5 `data_issue` (RLS, migração 0020, D95)

Conflito de dados: tipo (`conflito_documentos`, `documento_esperado_ausente`, `dado_vencido`, `duplicidade_suspeita`), estado (`aberto`, `resolvido`, `descartado`), capacidade afetada, objeto (`subject_type`, `subject_id`), campo, versões lado a lado em `sources` (rótulo, valor, documento, página, trecho), `dedupe_key` única por condomínio (inclui os valores: a decisão de uma pessoa vale para aqueles valores), resolução (`prevailing`, valor, motivo, `applied` quando o valor foi aplicado ao contrato; `auto` quando o sistema fechou porque os dados deixaram de divergir). Nunca é apagado; o histórico fica em `audit_log` (`data_issue.*`).

## 6. O que não muda

`finding` (exceto 4 colunas novas e 1 status), `decision`, `finding_comment`, `approval` (R12), `contract`, `contract_amendment`, `expense`, `document`, `bank_transaction`, `match_issue`, `competence`, `job`, `llm_calls`, `document_chunk`, `audit_log`; as 12 regras; os relatórios (que passam apenas a excluir também `pendente_evidencia`).

## 7. Plano de migração (proposto)

| Migração | Conteúdo | Backfill / padrão | Reversível? |
|---|---|---|---|
| 0011_access_model | `platform_role`, `condo_assignment` (RLS), colunas de `membership`, CHECK de papéis ampliado, `condominium.timezone`, `condominium.management_company_reviews`, nova versão de `app_accessible_condominium_ids` | `management_company_reviews = (management_company_id IS NOT NULL)`; timezone padrão | Sim (downgrade restaura a função anterior) |
| 0012_review_policy | `review_policy` (RLS, só inclusão), colunas de `finding`, status `pendente_evidencia`, ação `solicitar_evidencia`; política padrão da plataforma inserida | `review_requirement` por severidade; `review_policy_version = 1` | Sim, se nenhum achado estiver em `pendente_evidencia` |
| 0013_cases | `case`, `case_event` (só inclusão), `case_link`, `task` (RLS) | Nenhum | Sim (tabelas novas) |
| 0014_opportunities | `opportunity`, `opportunity_finding`, `savings_record` e `opportunity_review` (só inclusão) (RLS) | Nenhum (oportunidades nascem sob demanda) | Sim |

Cada migração entra em uma fatia própria, com testes, na ordem do roadmap (0011 e 0012 antes de VS-01; 0013 na VS-01; 0014 na VS-03). Nenhuma delas importa listas do código (D32).

## 8. Critérios de validação

Comuns a todas:
- `test_isolation.py::test_every_tenant_table_has_rls` cobre as tabelas novas; teste de leitura e escrita cruzada para cada uma.
- `test_planted_cases.py` continua **exato** e `test_rules.py` inalterado (a política padrão não muda o que é publicado).
- Suíte completa e E2E existentes passando sem alteração de rótulos.
- `make migrate` de banco vazio e `upgrade → downgrade → upgrade` em banco com seed.

Específicos:
- **0011:** reviewer sem atribuição recebe 404 em qualquer condomínio; atribuição revogada ou vencida perde acesso na próxima requisição; `condoos_admin` não vê condomínio não atribuído; gerente continua vendo a carteira (D69); membership expirado perde acesso; nenhum papel reservado (zelador/fornecedor/morador) tem permissão.
- **0012:** com a política padrão, os graves do seed ficam em `aguardando_validacao` como hoje; gerente valida só se `management_company_reviews`; reviewer atribuído valida; `pendente_evidencia` fora do relatório e do valor em risco; nova versão de política não altera achados já decididos.
- **0013:** aceite VS-01 (outro tenant não lê; sem permissão não edita; `resolvido` bloqueado sem critério/evidência; histórico após fechamento); desvincular preserva `case_link` e gera evento; detector de duplicidade sugere o assunto existente.
- **0014:** oportunidade não aparece ao síndico (API e tela) antes de `aprovada_para_cliente`; mudança após aprovação reabre a revisão; `realizada` exige evidência; nenhum total soma estágios; cálculo de `potencial` reproduzível em teste (FIN-01/02).
