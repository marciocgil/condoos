# Rastreabilidade — FR ↔ tarefa ↔ código ↔ teste ↔ entrega

Data: 07/11/2026. Atualizar ao fim de cada fatia (CLAUDE.md, item 6). "Entrega" = marco do MVP auditor (Marco 1–6, 05/11/2026) ou decisão pós-piloto (D65–D71) em que o código entrou. Testes citados existem no repositório; **não foram executados nesta sessão**.

| FR | Tarefa(s) | Código | Teste(s) | Entrega |
|---|---|---|---|---|
| FR-001 | CB-002 | `models.Condominium`, `routers/registry.py` (`POST /portfolio/condominiums`), `app/onboarding/` | `test_registry.py::test_manager_creates_a_condominium`, `test_onboarding.py` | Marco 1, Marco 6, D67 |
| FR-002 | CB-004, CB-005 | `routers/registry.py` (members), `auth/service.py`, `auth/tokens.py` | `test_auth.py`, `test_registry.py` | Marco 1, D67 |
| FR-003 | CB-001, CB-003 | `db/models.py::RLS_TABLES`, migração `0002_security.py`, `auth/deps.py` | `test_isolation.py` (10) | Marco 1 |
| FR-004 | CB-004 | `auth/rbac.py`, `auth/deps.py::require` | `test_rbac.py`, `test_findings_api.py` | Marco 1 |
| FR-005 | CB-010, CB-012 | `core/audit.py`, `models.AuditLog`, `models.Decision` | `test_isolation.py::test_append_only_tables`, `test_auth.py::test_login_is_audited` | Marco 1, Marco 4 |
| FR-006 | CB-010, CB-012 | `routers/settings.py` (alçadas, parâmetros) | `test_registry.py` (parcial) | Marco 4 |
| FR-007 | CB-011 | — | — | — |
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
| FR-021..025 | CB-020..025 | — (achado: `findings/decisions.py`, `routers/findings.py`, `routers/queue.py`, `pending.py`) | — (`test_findings_api.py`, `test_pending.py` cobrem os análogos) | — |
| FR-026 | CB-023 | `agenda.py` (em atraso, sem alerta) | `test_agenda.py` | D71 |
| FR-027..030 | — | — | — | — |
| FR-031 | CB-040 | `chat/agent.py`, `chat/tools.py`, `chat/service.py`, `prompts/chat_system.md` | `test_chat.py`, `tests/chat_eval/` (ao vivo não rodado) | Marco 5 |
| FR-032 | CB-041, CB-042 | `routers/findings.py::/summary`, `components/condoos/AgendaPreview.tsx` | — | Marco 4, D71 |
| FR-033 | CB-041 | `findings/explain.py`, `chat/service.py` (ação sugerida) | `test_explain.py` | Marco 4, Marco 5 |
| FR-034 | CB-010, CB-050 | (ausência de efeitos externos) | — | — |
| FR-035..040 | — | — | — | — |
| FR-041 | CB-060 | `extraction/fields.py` (contrato), `matching/documents.py`, `routers/registry.py` (contratos) | `test_contract_reading.py`, `test_onboarding.py`, `test_registry.py` | Marco 6, D59, D66–D68, D70 |
| FR-042 | CB-060 | `agenda.py`, `rules/contracts.py` | `test_agenda.py` | D71 |
| FR-043 | — | `extraction/*`, `ingestion/bank/` (OFX, CSV, CNAB) | `test_extraction.py`, `test_bank_parsers.py` | Marco 2 |
| FR-044 | CB-061 | `rules/r02_above_contract.py`, `r03_adjustment.py`, `r04_scope.py`, `rules/contracts.py`, `enrichment/indices.py` | `test_rules.py`, `test_planted_cases.py` | Marco 3 |
| FR-045 | CB-061 | (valor em risco em `models.Finding`) | — | — |
| FR-046 | CB-062 | (validação de graves em `findings/decisions.py`) | `test_rbac.py::test_pending_findings_visibility` | Marco 4 (divergente, DV-02) |
| FR-047 | — | — | — | — |
| FR-048 | — | `matching/bank.py`, `models.MatchIssue` | `test_matching.py` | Marco 3 |
| FR-049 / FR-050 | CB-063 (050) | — | — | — |
| FR-051..065 | — | — (FR-059: atas indexadas em `chat/search.py`) | — | — |

## Testes da Especificação §21 e do Plano §11.2

| Caso | Situação | Onde |
|---|---|---|
| SEC-01 (tenant A × B) | Coberto | `test_isolation.py` |
| SEC-02/AI (PDF adversarial) | Parcial: ferramentas só de leitura; sem teste explícito de injeção | CB-010 |
| SEC-02 Plano (busca entre tenants) | Coberto | `test_isolation.py`, RLS em `document_chunk` |
| SEC-04/05 (valor/expiração da aprovação) | Não há aprovação de ação | CB-050 |
| SEC-08 (kill switch) | Inexistente | CB-011 |
| SEC-10 (revogado com sessão antiga) | Sem teste dedicado | CB-004 |
| DOC-01 (campo ausente) | Parcial: obrigatório < 0,9 vai para fila | `test_extraction.py`; CB-030 |
| DOC-02 (versão vigente) | Parcial (aditivos) | CB-031 |
| FIN-01 (reajuste reproduzível) | Coberto | `test_rules.py` (R03) |
| FIN-02 (escopo não comparável) | Parcial (R04 com IA) | `test_rules.py`; CB-061 |
| OPT-01 (sem revisão, não publica) | Parcial: só graves | CB-062 |
| OPS-01/02, WF-01..10 | Inexistentes (sem assunto/OS) | CB-020..022 |
| AI-01 (sem fonte suficiente) | Gabarito existe; ao vivo não rodado | `tests/chat_eval/`; CB-040 |
