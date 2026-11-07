# Launch — arquitetura, modelo de dados e ADRs propostas

Data: 07/11/2026. **Proposta para revisão.** Nenhuma migração é escrita antes da aprovação do Marcio (regra do projeto, CLAUDE.md §6 do planejamento). Próxima migração livre: **0018**.

## 1. Quatro capacidades lógicas, um backend

Nenhum serviço novo: tudo dentro de `api/app` (FastAPI + SQLAlchemy async + fila de jobs `SKIP LOCKED`) e `web/` (Next.js). ✔

| Capacidade (prompt §4) | Onde mora | Reaproveita | Novo |
|---|---|---|---|
| **Journey Engine** | `api/app/launch/journey.py` | Fatos de `condominium`, `membership`, `document`, `competence`, `finding`, `action_request`; `audit_log` para eventos | Tabela `launch_state` (preferências) — ADR-L01 |
| **Conversational Guide** | `web/components/condoos/Journey*.tsx` + roteiro em `api/app/launch/script.py` | `ChatPanel`, `InsightCard`, `EvidenceList`, `FilterChips`; cliente LLM único quando houver chave | Roteiro determinístico de cartões (sem LLM obrigatório) — ADR-L02 |
| **Onboarding Automation** | já existe: `ingestion/`, `extraction/`, `matching/`, `enrichment/` | Tudo | Pedido delegado com link (LF4) — ADR-L04 |
| **Readiness & Trust Engine** | `api/app/launch/readiness.py` | `field_provenance`, `needs_review`, `pending.py`, `match_issue`, `condo_assignment`, `app/policy/` | Função de prontidão calculada na leitura — ADR-L03; conflito de dados — ADR-L05 |

Nova rota: `api/app/routers/launch.py` com `GET /condominiums/{id}/launch` (marcos, próximo passo, prontidão), `PUT /condominiums/{id}/launch/goal`, `POST /condominiums/{id}/launch/postpone`, `GET /condominiums/{id}/documents/{doc}/first-value`. Todas com `require(Permission.VIEW)` (leitura) ou `MANAGE_CASES` (síndico) para escrita, herdando 404 e evento de segurança (D78).

## 2. Entidades do prompt × o que existe

| Entidade do prompt | Decisão | Justificativa |
|---|---|---|
| Condominium, User, Role, Membership, PermissionGrant | **Reusar** | `condominium`, `app_user`, `membership`, `platform_role`, `condo_assignment`, `auth/rbac.py` (D79) |
| OnboardingSession, JourneyDefinition, Milestone, Dependency | **Código, não tabela** | Definições versionadas em Python (como `policy/`, D83); marcos derivados de fatos. Tabela só para o que é escolha humana: `launch_state` |
| OnboardingTask | **Reusar `case_task`/`case_record`** quando houver responsável; senão é só um "próximo passo" calculado | Evita segundo sistema de tarefas (D80) |
| ActivationEvent | **Reusar `audit_log`** com ações `launch.*` | Já é só inclusão, com ator e condomínio |
| DataSource, Connection, ConnectionHealth, SyncRun | **Adiar (LF5)** | Hoje só há upload, e-mail por pasta e arquivos bancários. Saúde do canal derivável de `document.origin` + `created_at` até haver conector real |
| ExpectedDocument | **Derivar de `contract.billing_frequency`** (`pending.py`) em LF3/LF5; tabela só se surgir documento esperado sem contrato | Evita duplicar D70 |
| Document, DocumentVersion, Classification | **Reusar** (`document`, `supersedes_id`, `classification_source`) | D85 |
| ExtractedFact, FactEvidence, FactValidation | **Reusar** `document.extracted` + `field_confidence` + `field_provenance` + `extraction_correction` + `reviewed_at` | D85; uma tabela de fatos seria migração grande sem ganho no LF2 |
| DataIssue | **Novo em LF3** (`data_issue`) — ADR-L05 | `match_issue` cobre só casamento ambíguo; conflito entre documentos não tem lugar |
| Person/Contact, Invitation | **Invitation = `membership` com `invited_at`** (D79). Contact sem login: **adiar (LF4)** | Não coletar contatos antes de haver uso |
| DelegationRequest, ExternalSubmission | **Novo em LF4** (`delegation_request`, `delegation_upload_token`) — ADR-L04 | Não há objeto de pedido externo |
| Supplier, Contract, ContractAmendment, Invoice, FinancialEntry | **Reusar** (`supplier`, `contract`, `contract_amendment`, `document`+`expense`, `bank_transaction`) | — |
| Asset | **Fora** (FR-051, P1 do Operate) | — |
| CapabilityReadiness, CapabilityGate | **Código** (`launch/readiness.py`), calculado na leitura; transições gravadas em `audit_log` | Igual a `pending.py` e `agenda.py`: sem tabela nova |
| PolicyDecision, ActionAttempt, DeliveryReceipt | **Reusar** `app/policy`, `action_request`, `action_decision`, `outbox_event` (D83) | Recibo de entrega só quando houver envio real (LF5) |

## 3. ADRs propostas

### ADR-L01 — Estado da jornada: fatos derivados + tabela mínima de preferências
- **Contexto:** marcos precisam ser verificáveis e não podem virar permissão; mas objetivo, modo e "fazer depois" são escolhas humanas que precisam sobreviver à troca de dispositivo.
- **Proposta:** tabela `launch_state` (RLS): `condominium_id` (único), `goal` (`economizar|pendencias|fornecedores|panorama|null`), `postponed` (JSON: chave do passo → data), `started_at`, `dismissed_at`, `updated_by_user_id`. Marcos e próximo passo são **sempre** recalculados a partir do banco. Eventos em `audit_log` (`launch.goal_selected`, `launch.first_value_shown`, `launch.step_postponed`, `launch.milestone_reached`).
- **Alternativas:** (a) sem tabela, guardar em `condominium_settings_version` — mistura parâmetros de regra com preferência de UX; (b) tabela de marcos com status — permite marcar concluído sem o fato (contraria R-L06).
- **Migração:** 0018, aditiva, reversível. **Risco:** baixo.

### ADR-L02 — Guia conversacional determinístico, IA opcional
- **Contexto:** sem chave de API (B4) o chat responde 503; o Launch não pode depender disso. Prompt pede "conversation-first, not chat-only".
- **Proposta:** roteiro de cartões em código (pergunta, porquê, benefício, respostas rápidas, ação). Texto livre do síndico vai ao chat existente **só** quando há chave, e qualquer dado crítico inferido volta como cartão de confirmação. Nenhuma escrita pelo chat (regra atual de `chat_system.md`).
- **Alternativa:** agente LLM conduzindo a jornada — custo por condomínio, não testável em replay, risco de injeção.

### ADR-L03 — Prontidão calculada por capacidade, consumida pela política
- **Proposta:** `readiness(condo, capability) -> Readiness(state, missing: list[Requirement], stale: list[...], evidence: list[ref])` com estados `nao_configurado | analise_parcial | supervisionada | autorizada`. Requisitos são **binários** (score nunca substitui requisito, prompt §4). `app/policy.evaluate` passa a recusar ação cujo tipo dependa de capacidade abaixo de `supervisionada` (decisão `DENY` com motivo). Transições de estado gravadas em `audit_log` quando observadas (no briefing diário), para downgrade auditável.
- **Alternativa:** tabela `capability_readiness` materializada — desatualiza; só se o cálculo ficar caro.

### ADR-L04 — Pedido delegado com link de envio sem conta (LF4)
- **Proposta:** `delegation_request` (RLS: condomínio, solicitante, destinatário nome+e-mail, escopo em texto e lista de itens esperados, prazo, estado, `case_id` opcional) e `delegation_upload_token` (hash SHA-256 do token, validade, `revoked_at`, contador de uso, limite de arquivos). Rota pública `POST /submit/{token}` **só grava arquivo** no condomínio do pedido (`ingest_file`), nunca lê nada; 404 genérico para token inválido/expirado; rate limit; auditoria por arquivo. Envio do link: primeiro corte manual (DL-02).
- **Riscos:** token vazado permite enviar arquivos (não ler). Mitigação: validade curta, revogação, revisão humana do que chegou antes de virar contrato.
- **Depende de:** Q-L02.

### ADR-L05 — Conflito de dados como objeto (LF3)
- **Proposta:** `data_issue` (RLS): tipo (`conflito_documentos`, `documento_esperado_ausente`, `dado_vencido`, `duplicidade_suspeita`), objetos envolvidos, trechos, capacidade afetada, estado (`aberto`, `resolvido`, `descartado`), resolução com versão prevalente, motivo e autor; eventos só inclusão. Não é achado (não acusa ninguém) e não é assunto (pode virar um, por vínculo, D75).
- **Alternativa:** reutilizar `match_issue` — semântica diferente (casamento ambíguo de um documento).

### ADR-L06 — Triagem de arquivo malicioso (adiada)
- ClamAV é GPL (proibido no produto). Opções: só formatos permitidos + conversão (já há `sniff`), serviço externo com licença compatível, ou sandbox de conversão. Decidir antes do primeiro piloto real com upload por terceiros (LF4).

## 4. Integrações e contratos

- **BrasilAPI** (existente, cache 30 dias) e **BCB SGS** (existente): sem mudança.
- **E-mail de entrada:** `InboundEmailProvider` (existente); provedor real (IMAP/SES) em LF5 com contrato documentado e mock nos testes.
- **E-mail de saída para terceiros:** não existe; entra como tipo de ação `pedido_documento.enviar` (L3) na política em LF4/LF5 se Q-L02 autorizar.
- **WhatsApp:** nenhum contrato até decisão comercial (⛓).

## 5. Segurança

- Rotas do Launch passam por `require()`; nenhuma rota recebe outro condomínio (404 + `security.access_denied`).
- Link de envio (LF4) é a única rota sem sessão: escopo de escrita mínima, testada por isolamento (token do condomínio A nunca grava em B).
- Texto de documento nunca é entrada de autorização (teste SEC-02 com PDF adversarial, LB-021).
- Logs só com ids; nada de nome de pessoa ou valor em log.
