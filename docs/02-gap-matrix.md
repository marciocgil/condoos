# 02 — Matriz de lacunas: FR-001..065 × produto atual

Data: 07/11/2026 (FR-046 revisto após D74). Fonte dos requisitos: Especificação Mestra v1.0 §15. Fonte do estado: código inspecionado (`docs/01-repo-audit.md`).

**Colunas.** *Repo*: real / parcial / inexistente, contra o **critério verificável da Especificação** (não contra o escopo do MVP auditor). *Status*: vocabulário do pacote (`nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`). Nenhum FR está `validado`: isso exige aceite contra a Especificação, que ainda não ocorreu. `pronto_para_validar` = o critério parece atendido e há teste no repositório, mas os testes não foram executados nesta sessão. `em_analise` = existe código parcial e a lacuna está descrita. P2/P3 sem código ficam `adiado` (regra do Plano Diretor §4.4).

## 1. Plataforma e identidade (CAP transversal / Core)

| FR | P | WP | Repo | O que existe | Lacuna para o critério | Evidência | Status |
|---|---|---|---|---|---|---|---|
| FR-001 | P0 | WP-02 | real | `condominium` com fuso IANA (D79), Carteira "Novo condomínio" (gerente ou Admin CondoOS), `app.onboarding` | — | `test_registry.py`, `test_onboarding.py`, `test_access_model.py::test_condominium_time_zone` | pronto_para_validar |
| FR-002 | P0 | WP-02 | parcial | Acesso por e-mail com papel, convite aceito no 1º login, acesso com prazo, revogação com histórico, papéis da equipe CondoOS e reservados (D79) | Convite pendente sem prazo próprio; tela de atribuição da equipe CondoOS | `test_registry.py`, `test_auth.py`, `test_access_model.py` | em_analise |
| FR-003 | P0 | WP-02 | real | RLS em 17 tabelas, filtro duplo, 404 com evento de segurança (D78), CI | Falta teste de storage cruzado | `test_isolation.py` (10), `test_access_revocation.py` | pronto_para_validar |
| FR-004 | P0 | WP-02 | real | `rbac.py` (5 papéis × 11 permissões), `require()` no backend | Papéis futuros (zelador, fornecedor…) | `test_rbac.py`, `test_findings_api.py` | pronto_para_validar |
| FR-005 | P0 | WP-03 | parcial | `audit_log` e `decision` append-only (D14) | Versão de política/aplicação e motivo em todas as mudanças críticas; estado anterior/novo | `test_isolation.py::test_append_only_tables` | em_analise |
| FR-006 | P0 | WP-03 | parcial | Alçadas e parâmetros de regra por condomínio (`settings.py`) | Política versionada, com responsável e vigência; níveis L1–L5 | `test_registry.py` (parcial) | em_analise |
| FR-007 | P0 | WP-03 | real (D83) | Pausa por condomínio e tipo (`automation_pause`); o worker não roda job pausado; pedidos novos recusados | Pausa global da plataforma | `test_actions.py::test_kill_switch_stops_requests_and_the_worker`, e2e `actions.spec.ts` | pronto_para_validar |
| FR-008 | P1 | WP-02 | parcial | Carteira multi-condomínio do gerente, filtro `?condominio=` (D69) | Síndico profissional com vários condomínios sem administradora (D3 cobre via `gerente`) | `test_isolation.py::test_gerente_sees_whole_portfolio` | em_analise |
| FR-009 | P1 | WP-19 | inexistente | — | Preferências de canal/horário | — | nao_iniciado |
| FR-010 | P1 | WP-03 | inexistente | — | MFA para ação sensível | — | nao_iniciado |

## 2. Documentos e memória

| FR | P | WP | Repo | O que existe | Lacuna | Evidência | Status |
|---|---|---|---|---|---|---|---|
| FR-011 | P0 | WP-05 | real | Upload/e-mail privado, `cond/<id>/`, tipo e MIME (`filetypes.py`), permissão `upload_document` | Antivírus (NFR-006) | `test_ingestion.py` | pronto_para_validar |
| FR-012 | P0 | WP-05 | parcial | Classificação, extração por tipo, confiança por campo, `extraction_source` | Página/trecho de origem por campo | `test_extraction.py` (20), `docs/extraction_accuracy.md` | em_analise |
| FR-013 | P0 | WP-06 | real | Busca híbrida com RLS (contratos, convenção, atas) | Visibilidade por papel em documentos restritos (SEC-07) quando houver | `test_document_search.py` (3) | pronto_para_validar |
| FR-014 | P0 | WP-04 | parcial | `expense_document`, `contract.source_document_id`, `approval.document_id` | Vínculo genérico documento ↔ caso/ativo (`EntityLink`) | `test_matching.py` | em_analise |
| FR-015 | P0 | WP-05 | parcial | Hash SHA-256; aditivo não substitui o original (D66) | Cadeia de versões de documento e "versão vigente" | `test_contract_reading.py` | em_analise |
| FR-016 | P0 | WP-05 | parcial | Campo < 0,9 vai para fila; documento revisado não é reprocessado | Rótulo explícito CONFIRMADO/EXTRAÍDO/INFERIDO/NÃO DISPONÍVEL/CONFLITANTE nas telas e na API | `test_extraction.py`, `test_queue.py` | em_analise |
| FR-017 | P1 | WP-06 | parcial | `document.index` idempotente; reavaliação de meses e superação de achados (D61) | Invalidação de respostas/recomendações dependentes | `test_supersede.py` | em_analise |
| FR-018 | P1 | WP-05 | parcial | Hash, boleto pela linha digitável (D63), nota pelo número | Decisão revisável de duplicata | `test_ingestion.py` | em_analise |
| FR-019 | P1 | WP-15 | parcial | Relatório PDF/XLSX, trilha PDF (D57) | Dossiê por assunto/recomendação (PDF/CSV/ZIP) | `test_reports.py` | em_analise |
| FR-020 | P2 | — | real | `retention.purge` diário (`core/retention.py`) | Confirmar desindexação de `document_chunk` | `test_retention.py` | pronto_para_validar |

## 3. Assuntos, tarefas e workflow

| FR | P | WP | Repo | O que existe | Lacuna | Evidência | Status |
|---|---|---|---|---|---|---|---|
| FR-021 | P0 | WP-07 | real | `case_record` com número, categoria, criticidade, estado, responsável, próxima ação e prazo (D80) | — | `test_cases.py` | pronto_para_validar |
| FR-022 | P0 | WP-07 | real | `case_task` com responsável (ou nome), prazo, estado, evidência exigida (D80) | — | `test_cases.py` | pronto_para_validar |
| FR-023 | P0 | WP-07 | real | `case_event` só inclusão, com autor, momento e motivo; linha do tempo no Assunto 360° (D80) | — | `test_cases.py`, `test_isolation.py::test_append_only_tables`, e2e `cases.spec.ts` | pronto_para_validar |
| FR-024 | P0 | WP-07 | real | Máquina de estados §8.2; resolver exige tarefas fechadas e evidência quando pedida (D80) | — | `test_cases.py` | pronto_para_validar |
| FR-025 | P0 | WP-07 | real (D84) | Fila de assuntos com filtros por pessoa, categoria, criticidade e prazo, na tela e na API; alerta de assunto sem dono ou atrasado (D80) | Notificação fora do app | `test_cases.py`, `test_case_queue.py`, e2e `backlog.spec.ts` | pronto_para_validar |
| FR-026 | P0 | WP-07/19 | parcial | Agenda mostra "em atraso" (D71) | Alerta registrado com envio e status | `test_agenda.py` | em_analise |
| FR-027 | P1 | WP-07 | real (D84) | Assunto 360° com vínculos clicáveis, "citado por" e vínculo pela tela (contrato, documento, fornecedor, despesa, achado, assunto) | Visão 360° do fornecedor e do contrato | `test_cases.py`, `test_case_queue.py`, e2e `backlog.spec.ts` | pronto_para_validar |
| FR-028 | P1 | WP-07 | parcial | Duplicidade oferecida antes de criar; vínculo entre assuntos reversível com histórico (D80) | Agrupamento explícito de relatos | `test_cases.py` | em_analise |
| FR-029 | P1 | WP-19 | inexistente | Jobs idempotentes (base) | Workflow condicionado à política | `test_jobs.py` (base) | nao_iniciado |
| FR-030 | P1 | WP-19 | inexistente | — | Escalonamento | — | nao_iniciado |

## 4. Assessor de IA e comunicação

| FR | P | WP | Repo | O que existe | Lacuna | Evidência | Status |
|---|---|---|---|---|---|---|---|
| FR-031 | P0 | WP-06 | real (não medido ao vivo) | Chat com 9 ferramentas de leitura, citações e números conferidos (D55) | Avaliação ao vivo (≥ 90 %, zero vazamento) | `test_chat.py`, `chat_eval/` (gabarito) | bloqueado (falta `ANTHROPIC_API_KEY`) |
| FR-032 | P0 | WP-09 | real | Briefing do dia por pessoa e condomínio: riscos, decisões, andamento, concluído (só com registro), agenda, oportunidades e qualidade dos dados, com fonte, período, fuso, versão, leitura e aviso de dados parciais (D82) | Envio por canal externo; horário configurável (FR-009) | `test_briefing.py`, e2e `briefing.spec.ts` | pronto_para_validar |
| FR-033 | P0 | WP-09 | parcial | Achado com explicação e evidências; ação sugerida do chat (lista fechada) | Próxima ação + estado de autorização | `test_explain.py` | em_analise |
| FR-034 | P0 | WP-10 | real (D83) | Motor de política nega por padrão; ação só com aprovação do síndico; nenhum efeito externo | Conectores reais ainda inexistentes | `test_actions.py` | pronto_para_validar |
| FR-035 | P1 | WP-20 | inexistente | — | WhatsApp oficial | — | nao_iniciado |
| FR-036 | P1 | WP-20 | inexistente | (chat interno responde sobre convenção) | FAQ ao morador | — | nao_iniciado |
| FR-037 | P1 | WP-20 | inexistente | — | Atualização ao morador | — | nao_iniciado |
| FR-038 | P1 | WP-19 | inexistente | — | Digest semanal | — | nao_iniciado |
| FR-039 | P2 | — | inexistente | — | Áudio | — | adiado |
| FR-040 | P2 | — | inexistente | — | Multi-ação | — | adiado |

## 5. Optimize e financeiro

| FR | P | WP | Repo | O que existe | Lacuna | Evidência | Status |
|---|---|---|---|---|---|---|---|
| FR-041 | P0 | WP-11 | parcial | Contrato a partir do documento: fornecedor, valor, índice, mês-base, vigência, escopo, periodicidade, aditivos (D59, D66, D68, D70) | Aviso prévio, multa, SLA, garantia; trecho de origem | `test_contract_reading.py` (5), `test_onboarding.py` | em_analise |
| FR-042 | P0 | WP-11 | parcial | Agenda com reajustes e fim de contrato (D71) | Alerta antes do aviso prévio (campo inexistente) | `test_agenda.py` | em_analise |
| FR-043 | P0 | WP-12 | real | NFS-e, NF-e, boleto, recibo, XML, OFX, CSV, CNAB; competência normalizada | Planilha/balancete de ERP | `test_extraction.py`, `test_bank_parsers.py` (12) | pronto_para_validar |
| FR-044 | P0 | WP-13 | real | R02 (acima do contrato), R03 (reajuste), R04 (escopo) com cálculo determinístico e índices BCB reais | Rótulo "divergência aparente" até validação (já é "indício") | `test_rules.py` (23), `test_planted_cases.py` | pronto_para_validar |
| FR-045 | P0 | WP-13 | real | `opportunity` com tipo, risco, prontidão, status e fonte; economia em `savings_record` por estágio, calculada por código (D81) | Métodos além de R02/R03 | `test_opportunities.py` | pronto_para_validar |
| FR-046 | P0 | WP-14 | real | Política de revisão (D79); oportunidade invisível ao condomínio até aprovação da revisora CondoOS; mudança após a aprovação exige nova revisão (D81) | — | `test_opportunities.py`, `test_review_policy.py`, e2e `opportunities.spec.ts` | pronto_para_validar |
| FR-047 | P1 | WP-22 | inexistente | (R11 compara com histórico, não com orçamento) | Orçamento × realizado | — | nao_iniciado |
| FR-048 | P1 | WP-22 | real | Casamento despesa ↔ extrato com `match_issue` (D41) | — | `test_matching.py` (9) | pronto_para_validar |
| FR-049 | P1 | WP-22 | inexistente | — | Caixa por cenários | — | nao_iniciado |
| FR-050 | P1 | WP-15 | parcial (D84) | Contratada com documento do acordo; realizada medida pelas faturas posteriores contra o baseline, com custo da mudança | Sazonalidade e ajuste de escopo na medição | `test_opportunity_followup.py`, e2e `opportunities.spec.ts` | pronto_para_validar |

## 6. Operate, Procurement e governança

| FR | P | WP | Repo | Lacuna principal | Status |
|---|---|---|---|---|---|
| FR-051 | P1 | WP-17 | inexistente | Ativos e plano de manutenção | nao_iniciado |
| FR-052 | P1 | WP-17 | inexistente | OS com estados distintos | nao_iniciado |
| FR-053 | P1 | WP-18 | inexistente | Portal do zelador | nao_iniciado |
| FR-054 | P1 | WP-18 | inexistente | Portal do fornecedor | nao_iniciado |
| FR-055 | P1 | WP-21 | inexistente | RFQ | nao_iniciado |
| FR-056 | P1 | WP-21 | inexistente | Comparador de propostas | nao_iniciado |
| FR-057 | P1 | WP-16 | inexistente | Conformidade e vencimentos | nao_iniciado |
| FR-058 | P1 | WP-21/10 | parcial (D83) | Aprovação com escopo, valor e versão congelados (hash), validade e alçada | Contratação em si continua proibida pelo sistema; aprovação pelo conselho | em_desenvolvimento |
| FR-059 | P2 | WP-23 | parcial (ata indexada e ligada a aprovação) | Deliberação → tarefas | adiado |
| FR-060 | P2 | WP-23 | inexistente | Obras e medição | adiado |
| FR-061 | P2 | WP-23 | inexistente | Reservas | adiado |
| FR-062 | P2 | WP-23 | inexistente | Escalas | adiado |
| FR-063 | P2 | WP-23 | inexistente | Incidentes | adiado |
| FR-064 | P3 | WP-24 | inexistente | Sensores | adiado |
| FR-065 | P3 | WP-24 | inexistente | Preditivo | adiado |

## 7. Resumo de cobertura

| Grupo | FRs | real | parcial | inexistente |
|---|---|---|---|---|
| Plataforma (001–010) | 10 | 3 | 4 | 3 |
| Documentos (011–020) | 10 | 3 | 7 | 0 |
| Workflow (021–030) | 10 | 4 | 4 | 2 |
| Advisor (031–040) | 10 | 2 | 2 | 6 |
| Optimize (041–050) | 10 | 5 | 2 | 3 |
| Operate etc. (051–065) | 15 | 0 | 1 | 14 |
| **Total** | **65** | **17** | **20** | **28** |

P0 (29 FRs): 18 real, 11 parcial, 0 inexistente (FR-007 e FR-034 entraram com a VS-05, D83; FR-025 com D84). FR-021 e FR-022 entraram com a VS-01 (D80). FR-045 (oportunidade) e FR-046 (revisão interna) são parciais, mas centrais ao Optimize, e FR-046 foi decidido em D74 (revisão proporcional ao risco).

## 8. Cobertura por CAP

| CAP | Cobertura atual | Comentário |
|---|---|---|
| CAP-01 Atendimento | Nenhuma | Não há canal de morador |
| CAP-02 Manutenção | Nenhuma | Sem ativos/OS |
| CAP-03 Contratos | Parcial forte (03.01, 03.03, 03.04) | Falta 03.05–03.08 (desempenho, cotações, Optimize, negociação) |
| CAP-04 Financeiro | Parcial forte (04.01–04.03, 04.05, 04.07) | Falta 04.04 orçamento, 04.06 caixa |
| CAP-05 Equipes | Nenhuma | — |
| CAP-06 Conflitos | Nenhuma | — |
| CAP-07 Segurança | Nenhuma | — |
| CAP-08 Conformidade | Mínima (agenda de contratos) | — |
| CAP-09 Governança | Mínima (atas indexadas, aprovações R12, relatório ao conselho) | — |
| CAP-10 Obras | Nenhuma | — |
| CAP-11 Lazer | Nenhuma | — |
| CAP-12 Planejamento | Mínima (valor em risco, métricas internas) | — |

## 9. NFR (§16) — leitura rápida

| NFR | Estado |
|---|---|
| 001 Identidade | parcial (sem MFA) |
| 002 Autorização | real (tenant + RBAC no backend) |
| 003 Criptografia | depende do deploy (`docs/deploy.md`) — não verificado |
| 004 Segredos | real (variáveis de ambiente, `.env.example`) |
| 005 Auditoria | parcial |
| 006 Upload | parcial (tipo/limite; sem antivírus) |
| 007 Backups | documentado em `docs/deploy.md`; restauração não testada |
| 008 Privacidade | parcial (`docs/lgpd.md`, retenção, CPF mascarado) |
| 009 IA | parcial forte (documento como dado, ferramentas só de leitura, checagem por código) |
| 010 Resiliência | parcial (jobs idempotentes; sem outbox) |
| 011 Observabilidade | parcial (logs só com ids; sem traces/métricas) |
| 012 Exportabilidade | parcial (relatórios) |
