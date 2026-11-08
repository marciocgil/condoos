# Rastreabilidade — FR ↔ tarefa ↔ código ↔ teste ↔ entrega

Data: 07/11/2026. Atualizar ao fim de cada fatia (CLAUDE.md, item 6). "Entrega" = marco do MVP auditor (Marco 1–6, 05/11/2026) ou decisão pós-piloto (D65–D71) em que o código entrou. Testes citados existem no repositório. Última execução local completa: 07/11/2026, 352 passaram (D95); E2E: 29 fluxos passaram contra a stack local (D85); `launch.spec.ts` (D89) passou numa stack local sem Docker.

| FR | Tarefa(s) | Código | Teste(s) | Entrega |
|---|---|---|---|---|
| FR-001 | CB-002 | `models.Condominium` (`timezone`), `core/time.py::local_today`, `routers/registry.py` (`POST /portfolio/condominiums`, perfil), `app/onboarding/`, migração 0011 | `test_registry.py::test_manager_creates_a_condominium`, `test_onboarding.py`, `test_access_model.py::test_condominium_time_zone`, `::test_admin_creates_direct_condominium_and_is_assigned` | Marco 1, Marco 6, D67, D79 |
| FR-002 | CB-004, CB-013, CB-014 | `routers/registry.py` (members), `auth/service.py` (aceite do convite), `auth/deps.py` (acesso ativo), `app/platform/`, `routers/platform.py`, migração 0011 | `test_auth.py`, `test_registry.py`, `test_access_model.py` | Marco 1, D67, D79 |
| FR-003 | CB-001, CB-003 | `db/models.py::RLS_TABLES`, migração `0002_security.py`, `auth/deps.py`, `core/audit.py::record_security_event`, `.github/workflows/ci.yml` | `test_isolation.py` (10), `test_access_revocation.py` (2 de evento) | Marco 1, D78 |
| FR-004 | CB-004 | `auth/rbac.py`, `auth/deps.py::require` | `test_rbac.py`, `test_findings_api.py`, `test_access_revocation.py` (revogação e desativação) | Marco 1, D78 |
| FR-005 | CB-010, CB-012 | `core/audit.py`, `models.AuditLog`, `models.Decision` | `test_isolation.py::test_append_only_tables`, `test_auth.py::test_login_is_audited` | Marco 1, Marco 4 |
| FR-006 | CB-010, CB-012, CB-015 | `condo_settings.py` e `routers/settings.py` (alçadas e parâmetros versionados, D85), `app/review/` e `routers/review_policy.py` (política de revisão versionada), migração 0012 | `test_registry.py` (parcial), `test_review_policy.py` | Marco 4, D79 |
| FR-007 | CB-011 | `app/policy/__init__.py` (`active_pause`, `job_paused`), `core/jobs.py::run_one` (job pausado volta à fila), `routers/actions.py` (pausas), `db/models.py::AutomationPause`, migração 0016; `components/condoos/AutomationPausesCard.tsx` | `test_actions.py::test_kill_switch_stops_requests_and_the_worker`, e2e `actions.spec.ts` | D83 |
| FR-008 | — | `routers/portfolio.py`, filtro `?condominio=` | `test_isolation.py::test_gerente_sees_whole_portfolio` | Marco 1, D69 |
| FR-009 / FR-010 | — | — | — | — |
| FR-011 | — | `ingestion/documents.py`, `ingestion/filetypes.py`, `ingestion/email.py`, `storage/s3.py`, `routers/documents.py` | `test_ingestion.py` | Marco 2 |
| FR-012, FR-016 | CB-030 | `extraction/pipeline.py`, `extraction/provenance.py`, `routers/queue.py`, `components/ReviewForm.tsx`, migração 0017 | `test_extraction.py`, `test_provenance.py`, `test_queue.py`, `make accuracy` | Marco 2, D85 |
| FR-013 | CB-040 | `chat/search.py`, `models.DocumentChunk` | `test_document_search.py` | Marco 5 |
| FR-014 | CB-024 | `models.ExpenseDocument`, `Contract.source_document_id`, `Approval.document_id`, `matching/documents.py` | `test_matching.py` | Marco 3, D59, D65 |
| FR-015 | CB-031 | `Document.sha256`, `Document.version`/`supersedes_id`, `routers/documents.py::upload_new_version`, `chat/search.py` (só a vigente), `models.ContractAmendment`, `DocumentNewVersion.tsx` | `test_document_versions.py`, `test_contract_reading.py`, `test_ingestion.py` | Marco 2, D66, D85 |
| FR-017 | — | `chat/search.py` (job `document.index`), `rules/engine.py` (superado) | `test_supersede.py` | Marco 5, D61 |
| FR-018 | — | `ingestion/documents.py` (hash), `matching/documents.py` (boleto, D63) | `test_ingestion.py`, `test_matching.py` | Marco 2, D63 |
| FR-019 | — | `reports/pdf.py`, `reports/xlsx.py`, `routers/reports.py` | `test_reports.py` | Marco 5 |
| FR-020 | — | `core/retention.py` | `test_retention.py` | Marco 6 |
| FR-021..025 | CB-020..027, CB-023 (filtros, D84) | `app/cases/__init__.py` (regras), `routers/cases.py` (API), `db/models.py` (`CaseRecord`, `CaseEvent`, `CaseLink`, `CaseTask`), migração 0013; telas `web/app/(sindico)/condominio/[id]/assuntos/`, `web/app/(admin)/admin/assuntos/`, `components/condoos/Case*.tsx` | `test_cases.py` (9), `test_isolation.py`, e2e `cases.spec.ts` (2) | D80 |
| FR-026 | CB-023 | `agenda.py` (em atraso, sem alerta) | `test_agenda.py` | D71 |
| FR-027, FR-028 | CB-024, CB-026, CB-028 | `app/cases/__init__.py` (vínculos, duplicidade), `routers/cases.py::link_candidates`, `CaseDetailView.tsx`, `CaseLinkPicker.tsx` | `test_cases.py`, `test_case_queue.py`, e2e `backlog.spec.ts` | D80, D84 |
| FR-029, FR-030 | — | — | — | — |
| FR-031 | CB-040 | `chat/agent.py`, `chat/tools.py`, `chat/service.py`, `prompts/chat_system.md` | `test_chat.py`, `tests/chat_eval/` (ao vivo não rodado) | Marco 5 |
| FR-032 | CB-041, CB-042 | `app/briefing/__init__.py` (montagem por fonte, savepoint por seção, retenção), `routers/briefing.py`, `db/models.py::Briefing`, migração 0015; telas `web/app/(sindico)/condominio/[id]/resumo/page.tsx` (aba Hoje), `web/app/(admin)/admin/hoje/page.tsx`, `components/condoos/BriefingView.tsx` | `test_briefing.py` (7), e2e `briefing.spec.ts` (2) | D82 |
| FR-033 | CB-041 | `findings/explain.py`, `chat/service.py` (ação sugerida) | `test_explain.py` | Marco 4, Marco 5 |
| FR-034 | CB-010, CB-050 | `app/policy/__init__.py` (nega por padrão), `app/actions/__init__.py` (aprovação, outbox, despacho sem envio), `routers/actions.py`, migração 0016; telas `aprovacoes/` (celular e desktop), `ActionDetailView.tsx`, `ActionForm.tsx` | `test_actions.py` (10), `test_isolation.py` (só inclusão em `action_decision`), e2e `actions.spec.ts` (2) | D83 |
| FR-035..040 | — | — | — | — |
| FR-041 | CB-060 | `extraction/fields.py` (contrato), `extraction/clauses.py`, `matching/documents.py`, `routers/registry.py` (contratos), `ContractClauses.tsx` | `test_contract_reading.py`, `test_contract_clauses.py`, `test_onboarding.py`, `test_registry.py` | Marco 6, D59, D66–D68, D70, D85 |
| FR-042 | CB-060 | `agenda.py` (prazo do aviso prévio), `rules/contracts.py` | `test_agenda.py`, `test_contract_clauses.py` | D71, D85 |
| FR-043 | — | `extraction/*`, `ingestion/bank/` (OFX, CSV, CNAB) | `test_extraction.py`, `test_bank_parsers.py` | Marco 2 |
| FR-044 | CB-061 | `rules/r02_above_contract.py`, `r03_adjustment.py`, `r04_scope.py`, `rules/contracts.py`, `enrichment/indices.py` | `test_rules.py`, `test_planted_cases.py` | Marco 3 |
| FR-045 | CB-061, CB-064 | `app/opportunities/__init__.py` (cálculo `excesso_mensal_v1`, estágios), `routers/opportunities.py`, `db/models.py` (`Opportunity`, `SavingsRecord`), migração 0014; telas `web/app/(admin)/admin/oportunidades/`, `web/app/(sindico)/condominio/[id]/oportunidades/`, `components/condoos/SavingsStages.tsx` | `test_opportunities.py::test_potential_savings_are_reproducible` e fluxo, e2e `opportunities.spec.ts` | D81 |
| FR-046 | CB-015, CB-016, CB-062 | `app/review/`, `app/opportunities/__init__.py` (revisão interna, `presented_at`, hash da versão), `routers/opportunities.py` (404 antes da aprovação), `findings/decisions.py`, `auth/rbac.py` | `test_opportunities.py`, `test_review_policy.py`, `test_access_model.py`, e2e `opportunities.spec.ts`, `condoos-staff.spec.ts` | D79, D81 |
| FR-047 | — | — | — | — |
| FR-048 | — | `matching/bank.py`, `models.MatchIssue` | `test_matching.py` | Marco 3 |
| FR-049 | — | — | — | — |
| FR-050 | CB-063 | `app/opportunities/__init__.py` (`record_contracted`, `measure_realized`), `routers/opportunities.py`, `OpportunityFollowUp.tsx` | `test_opportunity_followup.py`, e2e `opportunities.spec.ts` | D84 |
| FR-058 | CB-050 | `app/actions/__init__.py` (escopo, teto, versão e validade congelados) | `test_actions.py` | D83 (parcial: contratar continua fora do sistema) |
| FR-051..065 (exceto 058) | — | — (FR-059: atas indexadas em `chat/search.py`) | — | — |

## Testes da Especificação §21 e do Plano §11.2

| Caso | Situação | Onde |
|---|---|---|
| SEC-01 (tenant A × B) | Coberto; tentativa registrada como evento de segurança (D78) | `test_isolation.py`, `test_access_revocation.py` |
| SEC-02/AI (PDF adversarial) | Coberto (D89, LB-021): todo prompt que recebe documento diz que o conteúdo é dado; texto vai delimitado em `<documento>`; a política não lê texto; instrução injetada não muda campo nem confiança | `test_prompt_injection.py` |
| SEC-02 Plano (busca entre tenants) | Coberto | `test_isolation.py`, RLS em `document_chunk` |
| SEC-04/05 (valor/expiração da aprovação) | Coberto (D83): aprovação de outra versão é recusada; custo acima do teto e aprovação vencida devolvem para nova aprovação | `test_actions.py` |
| SEC-08 Plano (kill switch) | Coberto (D83) | `test_actions.py`, e2e `actions.spec.ts` |
| WF-06 (rejeitada não dispara) | Coberto (D83): recusa não cria evento no outbox | `test_actions.py::test_rejected_action_is_never_dispatched` |
| Outbox idempotente | Coberto (D83): despacho repetido da mesma aprovação não duplica | `test_actions.py` |
| SEC-10 (revogado com sessão antiga) | Coberto (D78) | `test_access_revocation.py` |
| DOC-01 (campo ausente) | Coberto (D85): campo sem valor é "não disponível", nunca inventado; obrigatório < 0,9 vai para fila | `test_provenance.py`, `test_extraction.py` |
| DOC-02 (versão vigente) | Coberto (D85): versão nova preservando a anterior; busca e contrato usam a vigente | `test_document_versions.py` |
| FIN-01 (reajuste reproduzível) | Coberto, também na economia estimada (D81) | `test_rules.py` (R03), `test_opportunities.py` |
| FIN-02 (escopo não comparável) | Parcial (R04 com IA) | `test_rules.py`; CB-061 |
| OPT-01 (sem revisão, não publica) | Coberto: oportunidade 404 para o condomínio antes da revisão (D81) | `test_opportunities.py` |
| OPS-02, WF-04, WF-10 | Cobertos no assunto: fechar sem evidência é negado; "fornecedor disse que fez" não resolve; reabrir preserva histórico (D80) | `test_cases.py` |
| OPS-01, WF-01..03, WF-05, WF-07..09 | Inexistentes (sem OS, webhook ou ERP) | — |
| AI-01 (sem fonte suficiente) | Gabarito existe; ao vivo não rodado | `tests/chat_eval/`; CB-040 |

## CondoOS Launch (D88, D89)

| Item | Código | Teste(s) | Entrega |
|---|---|---|---|
| LB-001 estado da jornada | `models.LaunchState`, migração 0018, `launch/state.py`, `routers/launch.py` (`PUT …/launch/goal`, `POST …/launch/postpone`, `PUT …/launch/dismissed`) | `test_launch.py::test_launch_api_permissions_and_isolation`, `test_isolation.py::test_every_tenant_table_has_rls` | D89 |
| LB-002 marcos LM1–LM5 por fatos | `launch/journey.py` | `test_launch.py::test_new_condominium_journey_from_facts` | D89 |
| LB-003 próximos passos | `launch/steps.py` | `test_launch.py::test_next_steps_follow_the_goal_and_postponement` | D89 |
| LB-004 rota de leitura | `routers/launch.py` (`GET …/launch`), permissão `MANAGE_LAUNCH` | `test_launch.py::test_launch_api_permissions_and_isolation` | D89 |
| LB-005 cartão de jornada | `components/condoos/JourneyCard.tsx`, tela Hoje do síndico | e2e `launch.spec.ts` | D89 |
| LB-006/007 primeiro valor | `launch/first_value.py`, `GET …/documents/{id}/first-value`, `components/condoos/FirstValueCard.tsx`, `UploadForm.tsx` | `test_launch.py::test_uncertain_contract_field_is_never_a_fact`, `::test_first_value_route_is_scoped_and_recorded_once`, e2e `launch.spec.ts` | D89 |
| LB-008 "o que já fiz por você" | `launch/journey.py::done_for_you` | `test_launch.py` (via API) | D89 |
| LB-010 prontidão C1–C3 | `launch/readiness.py` | `test_launch.py::test_new_condominium_journey_from_facts`, `::test_uncertain_contract_field_is_never_a_fact` | D89 |
| LB-021 SEC-02 | `prompts/*.md` (regra de conteúdo não confiável) | `test_prompt_injection.py` | D89 |
| LB-090 (parcial) | evento `launch.first_value_shown` (uma vez por documento), `launch.goal_selected`, `launch.step_postponed` em `audit_log` | `test_launch.py` | D89 |
| LB-009 alçada opcional | `onboarding/__init__.py` (`approval_limits` opcional), `NewCondoForm.tsx`, `policy/__init__.py` (sem alçada, ação com custo → `require_review`) | `test_launch.py::test_condominium_without_limits_waits_for_them` | D90 |
| C7 prontidão de ações | `launch/readiness.py::actions_capability` | `test_launch.py::test_condominium_without_limits_waits_for_them` | D90 |
| LB-011 prontidão nas telas | `components/condoos/CapabilityReadiness.tsx`, Ajustes do síndico, Configurações | e2e `launch.spec.ts` (desktop) | D90 |
| LB-012 implantações na Carteira | `launch/state.py::portfolio_row`, `GET /portfolio/launch`, Carteira | `test_launch.py::test_portfolio_launch_and_time_to_first_value`, e2e `launch.spec.ts` | D90 |
| LB-090 tempo até o primeiro valor | `launch/state.py::portfolio_row` (`hours_to_first_value`, `steps_postponed`), Métricas | `test_launch.py::test_portfolio_launch_and_time_to_first_value`, e2e `launch.spec.ts` | D90 |
| LB-022 bordas do envio | `ingestion/documents.py` (já existia), `UploadForm.tsx` (orientação), `FirstValueCard.tsx` (repetido) | `test_ingestion.py::test_upload_rejects_unsupported_files` | D90 |
| LB-020 tipos documentais | `db/enums.py::DocumentType`, migração 0019, `extraction/heuristics.py::classify_text`, `prompts/classify_document.md`, `extraction/fields.py::TEXT_ONLY_TYPES`, `chat/search.py::INDEXED_TYPES`, `launch/first_value.py`, `web/lib/labels.ts` | `test_document_types.py` | D91 |
| LB-034 prontidão C4, C8, C9 | `launch/readiness.py` (`savings_capability`, `expected_documents_capability`, `closing_capability`) | `test_launch.py::test_savings_expected_documents_and_closing_readiness` | D92 |
| LB-037 cobertura do relatório | `reports/data.py::month_coverage`, `reports/pdf.py`, `reports/xlsx.py` (aba "Cobertura") | `test_reports.py::test_report_for_each_seeded_condominium` | D92 |
| LB-030 conflitos de dados | `app/data_issues/` (detectores v1, ciclo), `db/models.py::DataIssue/DataIssueEvent`, migração 0020, `matching/documents.py` e `routers/registry.py` (detecção) | `test_data_issues.py` (4), `test_isolation.py` (RLS e só inclusão) | D93 |
| LB-032 Central de Validação | `routers/data_issues.py`, `web/app/(admin)/admin/validacao`, `components/condoos/DataIssueCard.tsx` | `test_data_issues.py::test_api_permissions_and_isolation`, e2e `validation.spec.ts` | D93 |
| LB-035 política consulta conflitos | `policy/__init__.py::evaluate(supplier_id=...)`, `actions/__init__.py` | `test_data_issues.py`, `test_prompt_injection.py::test_policy_never_reads_text` | D93 |
| LB-036 (parcial) campo conflitante | `launch/first_value.py`, `launch/readiness.py::_with_conflicts`, `rules/engine.py::_conflict_evidence` | `test_data_issues.py::test_amendment_outside_the_term` | D93 |
| LB-036 "inferido" | `extraction/confidence.py` (`Assessment.inferred`), `extraction/provenance.py::build`, `extraction/pipeline.py`, `launch/first_value.py`, `ReviewForm.tsx`, `FirstValueCard.tsx` | `test_provenance.py::test_values_filled_by_a_rule_are_inferred_never_read`, `test_launch.py` | D94 |
| LB-033 envio em lote | `routers/launch.py::batch_status`, `components/condoos/BatchProgress.tsx`, `UploadForm.tsx` | `test_launch.py::test_batch_status_of_an_upload`, e2e `launch.spec.ts` | D94 |
| Gate LG3 | cenário único: conflito, ausência, duplicidade, ilegível, cobertura | `test_lg3_gate.py` | D94 |
| LB-045 triagem de arquivos | `ingestion/triage.py`, `ingestion/documents.py::ingest_file` | `test_triage.py` (9), `test_delegation.py` | D95 |
| LB-053 e-mail do pedido enviado pelo CondoOS | `delegation/email.py`, `policy` (`pedido_documento.enviar_email`, `EmailDraft`), `actions` (aprovação e despacho), `auth/mailer.py` (Reply-To, Message-ID), migração 0023, `RequestEmailCard`, `ActionDetailView` | `test_request_email.py` (4), e2e `delegation.spec.ts` | D103 |
| LB-052 documento esperado em todos os canais, LB-055 cobertura do mês | `pending.py` (`arrivals`, `em_conferencia`), `launch/readiness.py` (C8), `agenda.py`, `routers/agenda.py::month_coverage`, `reports/data.py`, `MonthCoverageCard` | `test_pending.py` (2 novos), e2e `agenda.spec.ts` | D102 |
| LB-050/051 e-mail de entrada e saúde do canal | `ingestion/email.py` (`S3EmailProvider`, `find_condominium`, `process_inbound`), `routers/inbound.py`, migração 0022, `InboundEmailCard` | `test_inbound_email.py` (6), `test_ingestion.py::test_folder_email_provider`, e2e `launch.spec.ts` (troca do endereço) | D101 |
| LB-041 limite por endereço, LB-044 painel e desktop | `core/ratelimit.py`, `routers/delegations.py` (`board`, `portfolio_requests`, `public_rate_limit`), `DelegationBoard`, `/admin/pedidos/*`, `PublicUpload` (429) | `test_delegation.py` (limite, painel, carteira), e2e `delegation.spec.ts` (celular e desktop) | D100 |
| LB-040..043 pedido delegado | `app/delegation/`, `routers/delegations.py`, migração 0021, telas `pedidos/*`, `/enviar/[token]`, `DelegationForm`, `DelegationDetailView`, `PublicUpload` | `test_delegation.py` (3), `test_launch.py::test_ask_for_missing_documents_step`, e2e `delegation.spec.ts` | D95 |
