# Rastreabilidade — FR ↔ tarefa ↔ código ↔ teste ↔ entrega

Data: 07/11/2026. Atualizar ao fim de cada fatia (CLAUDE.md, item 6). "Entrega" = marco do MVP auditor (Marco 1–6, 05/11/2026) ou decisão pós-piloto (D65–D71) em que o código entrou. Testes citados existem no repositório. Última execução local completa: 07/11/2026, 292 passaram (D83); E2E: 25 fluxos passaram contra a stack local.

| FR | Tarefa(s) | Código | Teste(s) | Entrega |
|---|---|---|---|---|
| FR-001 | CB-002 | `models.Condominium` (`timezone`), `core/time.py::local_today`, `routers/registry.py` (`POST /portfolio/condominiums`, perfil), `app/onboarding/`, migração 0011 | `test_registry.py::test_manager_creates_a_condominium`, `test_onboarding.py`, `test_access_model.py::test_condominium_time_zone`, `::test_admin_creates_direct_condominium_and_is_assigned` | Marco 1, Marco 6, D67, D79 |
| FR-002 | CB-004, CB-013, CB-014 | `routers/registry.py` (members), `auth/service.py` (aceite do convite), `auth/deps.py` (acesso ativo), `app/platform/`, `routers/platform.py`, migração 0011 | `test_auth.py`, `test_registry.py`, `test_access_model.py` | Marco 1, D67, D79 |
| FR-003 | CB-001, CB-003 | `db/models.py::RLS_TABLES`, migração `0002_security.py`, `auth/deps.py`, `core/audit.py::record_security_event`, `.github/workflows/ci.yml` | `test_isolation.py` (10), `test_access_revocation.py` (2 de evento) | Marco 1, D78 |
| FR-004 | CB-004 | `auth/rbac.py`, `auth/deps.py::require` | `test_rbac.py`, `test_findings_api.py`, `test_access_revocation.py` (revogação e desativação) | Marco 1, D78 |
| FR-005 | CB-010, CB-012 | `core/audit.py`, `models.AuditLog`, `models.Decision` | `test_isolation.py::test_append_only_tables`, `test_auth.py::test_login_is_audited` | Marco 1, Marco 4 |
| FR-006 | CB-010, CB-012, CB-015 | `routers/settings.py` (alçadas, parâmetros), `app/review/` e `routers/review_policy.py` (política de revisão versionada), migração 0012 | `test_registry.py` (parcial), `test_review_policy.py` | Marco 4, D79 |
| FR-007 | CB-011 | `app/policy/__init__.py` (`active_pause`, `job_paused`), `core/jobs.py::run_one` (job pausado volta à fila), `routers/actions.py` (pausas), `db/models.py::AutomationPause`, migração 0016; `components/condoos/AutomationPausesCard.tsx` | `test_actions.py::test_kill_switch_stops_requests_and_the_worker`, e2e `actions.spec.ts` | D83 |
| FR-008 | — | `routers/portfolio.py`, filtro `?condominio=` | `test_isolation.py::test_gerente_sees_whole_portfolio` | Marco 1, D69 |
| FR-009 / FR-010 | — | — | — | — |
| FR-011 | — | `ingestion/documents.py`, `ingestion/filetypes.py`, `ingestion/email.py`, `storage/s3.py`, `routers/documents.py` | `test_ingestion.py` | Marco 2 |
| FR-012 | CB-030 | `extraction/pipeline.py`, `fields.py`, `confidence.py`, `llm_extract.py`, `heuristics.py` | `test_extraction.py` (20), `make accuracy` | Marco 2 |
| FR-013 | CB-040 | `chat/search.py`, `models.DocumentChunk` | `test_document_search.py` | Marco 5 |
| FR-014 | CB-024 | `models.ExpenseDocument`, `Contract.source_document_id`, `Approval.document_id`, `matching/documents.py` | `test_matching.py` | Marco 3, D59, D65 |
| FR-015 | CB-031 | `Document.sha256`, `models.ContractAmendment` | `test_contract_reading.py`, `test_ingestion.py` | Marco 2, D66 |
| FR-016 | CB-030 | `extraction/confidence.py`, `routers/queue.py` | `test_extraction.py`, `test_queue.py` | Marco 2 |
| FR-017 | — | `chat/search.py` (job `document.index`), `rules/engine.py` (superado) | `test_supersede.py` | Marco 5, D61 |
| FR-018 | — | `ingestion/documents.py` (hash), `matching/documents.py` (boleto, D63) | `test_ingestion.py`, `test_matching.py` | Marco 2, D63 |
| FR-019 | — | `reports/pdf.py`, `reports/xlsx.py`, `routers/reports.py` | `test_reports.py` | Marco 5 |
| FR-020 | — | `core/retention.py` | `test_retention.py` | Marco 6 |
| FR-021..025 | CB-020..027 | `app/cases/__init__.py` (regras), `routers/cases.py` (API), `db/models.py` (`CaseRecord`, `CaseEvent`, `CaseLink`, `CaseTask`), migração 0013; telas `web/app/(sindico)/condominio/[id]/assuntos/`, `web/app/(admin)/admin/assuntos/`, `components/condoos/Case*.tsx` | `test_cases.py` (9), `test_isolation.py`, e2e `cases.spec.ts` (2) | D80 |
| FR-026 | CB-023 | `agenda.py` (em atraso, sem alerta) | `test_agenda.py` | D71 |
| FR-027, FR-028 | CB-024, CB-026 | `app/cases/__init__.py` (vínculos, duplicidade), `CaseDetailView.tsx` | `test_cases.py` | D80 (parcial) |
| FR-029, FR-030 | — | — | — | — |
| FR-031 | CB-040 | `chat/agent.py`, `chat/tools.py`, `chat/service.py`, `prompts/chat_system.md` | `test_chat.py`, `tests/chat_eval/` (ao vivo não rodado) | Marco 5 |
| FR-032 | CB-041, CB-042 | `app/briefing/__init__.py` (montagem por fonte, savepoint por seção, retenção), `routers/briefing.py`, `db/models.py::Briefing`, migração 0015; telas `web/app/(sindico)/condominio/[id]/resumo/page.tsx` (aba Hoje), `web/app/(admin)/admin/hoje/page.tsx`, `components/condoos/BriefingView.tsx` | `test_briefing.py` (7), e2e `briefing.spec.ts` (2) | D82 |
| FR-033 | CB-041 | `findings/explain.py`, `chat/service.py` (ação sugerida) | `test_explain.py` | Marco 4, Marco 5 |
| FR-034 | CB-010, CB-050 | `app/policy/__init__.py` (nega por padrão), `app/actions/__init__.py` (aprovação, outbox, despacho sem envio), `routers/actions.py`, migração 0016; telas `aprovacoes/` (celular e desktop), `ActionDetailView.tsx`, `ActionForm.tsx` | `test_actions.py` (10), `test_isolation.py` (só inclusão em `action_decision`), e2e `actions.spec.ts` (2) | D83 |
| FR-035..040 | — | — | — | — |
| FR-041 | CB-060 | `extraction/fields.py` (contrato), `matching/documents.py`, `routers/registry.py` (contratos) | `test_contract_reading.py`, `test_onboarding.py`, `test_registry.py` | Marco 6, D59, D66–D68, D70 |
| FR-042 | CB-060 | `agenda.py`, `rules/contracts.py` | `test_agenda.py` | D71 |
| FR-043 | — | `extraction/*`, `ingestion/bank/` (OFX, CSV, CNAB) | `test_extraction.py`, `test_bank_parsers.py` | Marco 2 |
| FR-044 | CB-061 | `rules/r02_above_contract.py`, `r03_adjustment.py`, `r04_scope.py`, `rules/contracts.py`, `enrichment/indices.py` | `test_rules.py`, `test_planted_cases.py` | Marco 3 |
| FR-045 | CB-061, CB-064 | `app/opportunities/__init__.py` (cálculo `excesso_mensal_v1`, estágios), `routers/opportunities.py`, `db/models.py` (`Opportunity`, `SavingsRecord`), migração 0014; telas `web/app/(admin)/admin/oportunidades/`, `web/app/(sindico)/condominio/[id]/oportunidades/`, `components/condoos/SavingsStages.tsx` | `test_opportunities.py::test_potential_savings_are_reproducible` e fluxo, e2e `opportunities.spec.ts` | D81 |
| FR-046 | CB-015, CB-016, CB-062 | `app/review/`, `app/opportunities/__init__.py` (revisão interna, `presented_at`, hash da versão), `routers/opportunities.py` (404 antes da aprovação), `findings/decisions.py`, `auth/rbac.py` | `test_opportunities.py`, `test_review_policy.py`, `test_access_model.py`, e2e `opportunities.spec.ts`, `condoos-staff.spec.ts` | D79, D81 |
| FR-047 | — | — | — | — |
| FR-048 | — | `matching/bank.py`, `models.MatchIssue` | `test_matching.py` | Marco 3 |
| FR-049 / FR-050 | CB-063 (050) | — | — | — |
| FR-058 | CB-050 | `app/actions/__init__.py` (escopo, teto, versão e validade congelados) | `test_actions.py` | D83 (parcial: contratar continua fora do sistema) |
| FR-051..065 (exceto 058) | — | — (FR-059: atas indexadas em `chat/search.py`) | — | — |

## Testes da Especificação §21 e do Plano §11.2

| Caso | Situação | Onde |
|---|---|---|
| SEC-01 (tenant A × B) | Coberto; tentativa registrada como evento de segurança (D78) | `test_isolation.py`, `test_access_revocation.py` |
| SEC-02/AI (PDF adversarial) | Parcial: ferramentas só de leitura; sem teste explícito de injeção | CB-010 |
| SEC-02 Plano (busca entre tenants) | Coberto | `test_isolation.py`, RLS em `document_chunk` |
| SEC-04/05 (valor/expiração da aprovação) | Coberto (D83): aprovação de outra versão é recusada; custo acima do teto e aprovação vencida devolvem para nova aprovação | `test_actions.py` |
| SEC-08 Plano (kill switch) | Coberto (D83) | `test_actions.py`, e2e `actions.spec.ts` |
| WF-06 (rejeitada não dispara) | Coberto (D83): recusa não cria evento no outbox | `test_actions.py::test_rejected_action_is_never_dispatched` |
| Outbox idempotente | Coberto (D83): despacho repetido da mesma aprovação não duplica | `test_actions.py` |
| SEC-10 (revogado com sessão antiga) | Coberto (D78) | `test_access_revocation.py` |
| DOC-01 (campo ausente) | Parcial: obrigatório < 0,9 vai para fila | `test_extraction.py`; CB-030 |
| DOC-02 (versão vigente) | Parcial (aditivos) | CB-031 |
| FIN-01 (reajuste reproduzível) | Coberto, também na economia estimada (D81) | `test_rules.py` (R03), `test_opportunities.py` |
| FIN-02 (escopo não comparável) | Parcial (R04 com IA) | `test_rules.py`; CB-061 |
| OPT-01 (sem revisão, não publica) | Coberto: oportunidade 404 para o condomínio antes da revisão (D81) | `test_opportunities.py` |
| OPS-02, WF-04, WF-10 | Cobertos no assunto: fechar sem evidência é negado; "fornecedor disse que fez" não resolve; reabrir preserva histórico (D80) | `test_cases.py` |
| OPS-01, WF-01..03, WF-05, WF-07..09 | Inexistentes (sem OS, webhook ou ERP) | — |
| AI-01 (sem fonte suficiente) | Gabarito existe; ao vivo não rodado | `tests/chat_eval/`; CB-040 |
