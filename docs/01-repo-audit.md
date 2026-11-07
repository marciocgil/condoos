# 01 — Auditoria do repositório (diagnóstico factual)

Data: 07/11/2026. Execução do prompt `01_PLANEJADOR_MESTRE.md` (planejamento; nenhum código alterado).
Referências lidas integralmente: Especificação Mestra v1.0 (`docs/condoos-planning/02_Contexto_Produto/`), Plano Diretor v1.0 (`docs/condoos-planning/01_Plano_Diretor/`, lido por `pandoc -t plain`), `CLAUDE.md`, `docs/decisions.md` (D1–D71), `docs/ui-audit.md`.

**Como ler:** "real" = código executável com teste no repositório; "parcial" = existe, mas não atende o critério da Especificação Mestra; "inexistente" = não há código. Nada aqui é mock: o produto atual não tem telas de demonstração sem backend.

## 1. Limites desta auditoria

- **Testes não executados nesta sessão.** O contêiner não tem as dependências Python instaladas, nem a extensão pgvector, nem a stack do `docker compose`. Os resultados citados vêm de evidências versionadas (`docs/pilot/run.md`, `docs/extraction_accuracy.md`, `docs/ui-audit.md` §6) e da contagem dos testes no código, não de execução hoje.
- **Arquivos realmente abertos:** `api/app/db/models.py` (tabelas e `RLS_TABLES`), `api/app/db/enums.py`, `api/app/auth/rbac.py`, `api/app/auth/deps.py` (assinaturas), `api/app/core/audit.py`, `api/app/core/jobs.py` (assinaturas), `api/app/core/time.py`, `api/app/worker.py` (`HANDLERS`), `api/app/routers/*.py` (todas as rotas, por busca), `api/app/routers/settings.py` (alçadas), `api/tests/*` (nomes e contagem de testes), `web/app/**/page.tsx` (lista), `web/components/**` (lista), `docs/pilot/run.md`. O conteúdo das regras R01–R12, do chat e da extração foi conferido por `docs/decisions.md` e `docs/rules.md`, não linha a linha.
- O Design System v1.0 original (`CondoOS_Design_System_v1.0.md`) **não está no repositório**; sua aplicação está documentada em `docs/ui-audit.md` e nos tokens de `web/app/globals.css`.

## 2. O que é o produto hoje

Um **auditor de despesas de condomínio** (Marcos 1–6 concluídos em 05/11/2026; Pós-piloto D65–D71): lê as despesas do mês, cruza com contrato, CNPJ, extrato e histórico pelas 12 regras e entrega **achados** priorizados por valor em risco. A administradora (gerente/analista) opera a fila e valida achados graves; o corpo diretivo (síndico, subsíndico, conselheiro) vê, decide e comenta. O sistema não move dinheiro e não envia nada para fora, exceto o e-mail do link mágico.

Na taxonomia da Especificação Mestra, o produto atual cobre **parte do CondoOS Optimize (CAP-03.04, CAP-04.01–04.05)**, parte do **Core** (identidade, tenant, documentos, auditoria) e um **Advisor** de perguntas (chat). Não há Operate, Procurement nem o objeto central "Assunto/Case".

## 3. Arquitetura (verificada)

| Camada | Estado | Onde |
|---|---|---|
| Monólito modular Python | Real | `api/` FastAPI + SQLAlchemy 2 async + Alembic (10 migrações, `0001`–`0010`) |
| Worker e fila de jobs | Real | `app/core/jobs.py` (`SKIP LOCKED`, `dedupe_key`, backoff), `app/worker.py` (10 handlers: `document.process`, `document.match`, `bank.match`, `supplier.enrich`, `indices.refresh`, `rules.evaluate`, `finding.explain`, `document.index`, `retention.purge`, `ping`) |
| Front-end | Real | `web/` Next.js 15, TS strict, Tailwind 4, `lucide-react`; 16 telas da administradora e 8 do corpo diretivo |
| Banco | Real | PostgreSQL 16 + pgvector; 27 tabelas |
| Arquivos | Real | S3 (SeaweedFS local); chave sempre `cond/<condominium_id>/…` |
| LLM | Real | Cliente único `app/llm/client.py` (live/record/replay/off), `llm_calls`, orçamento mensal por condomínio, prompts em `app/prompts/*.md` |
| Busca | Real | Híbrida (pgvector 384 dim local + full-text pt), `document_chunk` com RLS (D52, D53) |
| Chat | Real (não avaliado ao vivo) | Claude Agent SDK com 9 ferramentas só de leitura; números, citações e ação sugerida conferidos por código (D54, D55) |
| CI | **Criado em D78** (era inexistente na auditoria) | `.github/workflows/ci.yml`: lint + pytest com pgvector + frontend; E2E só local |
| Deploy | Documentado, sem staging | `docs/deploy.md`; nenhum ambiente versionado no repositório |

## 4. Segurança e multi-tenant (verificado)

- **RLS** em 17 tabelas (`RLS_TABLES`), papel da API sem `BYPASSRLS`, escopo por `set_config('app.condominium_ids')` (D13). Worker com `BYPASSRLS` (jobs atravessam condomínios).
- **Filtro duplo**: código filtra por `condominium_id` e o RLS filtra de novo. Outro condomínio = 404 (D15).
- **Append-only**: `decision` e `audit_log` sem UPDATE/DELETE para a API (D14).
- **Auth**: link mágico (hash, 15 min, uso único, 5/h), sessões no servidor revogáveis no logout (D16, D17). **Sem MFA.**
- **RBAC**: 5 papéis (`sindico`, `subsindico`, `conselheiro`, `gerente`, `analista`) × 11 permissões (`app/auth/rbac.py`). Papéis por condomínio e por administradora.
- **Testes de isolamento**: `tests/test_isolation.py` (10 testes: síndica só vê o seu, 404, carteira do gerente, isolamento entre administradoras, RLS sem escopo, RLS sem WHERE, escrita em outro condomínio, append-only, toda tabela de tenant com RLS).
- **Lacunas**: nenhum evento de segurança dedicado em acesso negado (a resposta é 404 sem registro específico); sem antivírus no upload; sem teste dedicado de "usuário com acesso removido usa sessão antiga" (o acesso é recalculado a cada requisição em `auth/deps.py`, o que deve bastar, mas falta a prova); fuso horário não é configurável por condomínio (`core/time.py` usa UTC e datas; `America/Sao_Paulo` implícito).

## 5. Inventário funcional: real / parcial / inexistente

| Área | Real | Parcial | Inexistente |
|---|---|---|---|
| Tenant e acesso | Condomínio novo (Carteira e `app.onboarding`), acessos por e-mail com papel, RBAC, RLS, 404 | Convite sem prazo próprio (o link mágico expira); fuso não configurável | MFA, preferências de canal, papéis zelador/morador/fornecedor/revisor CondoOS/suporte/auditor |
| Auditoria e política | `audit_log` e `decision` append-only; alçadas por categoria (`approval_limits`) | Alçadas sem versão/vigência; auditoria sem versão de política/aplicação | Motor de políticas, kill switch, autonomia L1–L5, outbox |
| Documentos | Upload/e-mail com hash, Docling + LLM, confiança por campo, fila de correção, `extraction_correction`, retenção | Proveniência por campo sem página/trecho; aditivos preservam o original, mas não há cadeia de versões de documento | Classes CONFIRMADO/EXTRAÍDO/INFERIDO/NÃO DISPONÍVEL/CONFLITANTE explícitas; antivírus |
| Busca e chat | Busca híbrida com RLS; chat com citações verificadas e 33 casos de avaliação | Avaliação ao vivo não rodada (sem chave) | Briefing diário, digest |
| Contratos | Contrato a partir do documento (D59), aditivos (D66), periodicidade (D70), índices BCB reais, agenda de reajuste e fim (D71) | Cláusulas de aviso prévio, multa, SLA, garantia não extraídas | Alertas enviados antes do aviso prévio |
| Financeiro | NFS-e, NF-e, boleto, recibo, XML, OFX, CSV, CNAB 240/400; casamento despesa ↔ extrato ↔ contrato com `match_issue` | Comparação fatura × contrato vira **achado** (R02/R03/R04), não **oportunidade** | Orçamento × realizado, caixa, economia realizada, balancete de ERP |
| Regras / achados | 12 regras determinísticas (R04/R07 com IA), casos plantados, explicação validada por código, decisões e trilha, superado (D61) | Valor em risco ≠ economia estimada | Score de oportunidade, revisão interna CondoOS |
| Operação | Pendências (D70) e Agenda (D71), fila de exceções | — | Assuntos, tarefas, OS, ativos, fornecedor/zelador/morador, WhatsApp, notificações |
| Relatórios | PDF/XLSX por competência, trilha em PDF, fechamento com fila vazia (D57, D58) | Relatório mensal ≠ semanal verificável (US-020) | Exportação de dossiê por assunto |
| Métricas | Precisão, extração automática, tempo de revisão, custo de IA (D60) | — | Baseline de horas, North Star, ROI |

## 6. Testes no repositório (contados, não executados hoje)

- Backend: **185 funções de teste** em 31 arquivos (`api/tests/`), com destaque para `test_rules.py` (23), `test_extraction.py` (20), `test_bank_parsers.py` (12), `test_isolation.py` (10), `test_jobs.py` (9), `test_llm_client.py` (9), `test_matching.py` (9). O último registro de execução completa citado é "179 testes do backend" (`docs/ui-audit.md` §6, Marco 4); depois disso entraram os testes de D65–D71.
- E2E Playwright: 7 specs (`login`, `correction`, `findings`, `chat-reports`, `registry`, `pending`, `agenda`).
- Aceite do Marco 6: `docs/pilot/run.md` (05/11/2026), 1 min 52 s do upload ao relatório, 0 job com falha.
- Acurácia de extração sem chave: 12/30 sem revisão, 0 erro automático (`docs/extraction_accuracy.md`).

## 7. Riscos e dívidas técnicas

| # | Risco/dívida | Severidade | Evidência |
|---|---|---|---|
| R1 | Sem CI: regressão de isolamento ou regra só aparece se alguém rodar `make test` | Alta | Ausência de `.github/` |
| R2 | Modelo de domínio centrado em "achado"; a Especificação centra em "Assunto/Case". Sem ADR, a evolução pode criar dois sistemas paralelos | Alta | `models.py` sem `case`/`task` |
| R3 | Público e papéis divergem: produto opera pela administradora; Especificação prevê condomínio individual e revisor interno CondoOS | Alta (produto) | D3, D48 × Espec. §1.5, FR-046 |
| R4 | Nenhum motor de políticas: hoje é seguro por ausência de efeitos externos; qualquer envio futuro sem WP-03 viola o G4 | Crítica quando houver ação externa | Não há `policy` |
| R5 | LLM avaliado só com respostas gravadas: R04/R07, explicações e chat sem medição ao vivo | Média | Pendências conhecidas em `CLAUDE.md` |
| R6 | Proveniência sem página/trecho por campo extraído (FR-012) | Média | `document.extracted` + `field_confidence` |
| R7 | Executável do Claude Code no `claude-agent-sdk` sob termos comerciais (D54) | Média (jurídico) | D54 |
| R8 | CNAB não validado com arquivo real (D28) | Média | D28 |
| R9 | Imagem da API com 1,81 GB (D52) | Baixa | D52 |
| R10 | Fuso fixo implícito; prazos "úteis" não modelados (WF-05) | Baixa agora, Média com tarefas | `core/time.py` |

## 8. Reuso recomendado

Preservar integralmente: arquitetura (FastAPI + Next.js, monólito modular), RLS e filtro duplo, fila de jobs, cliente único de LLM, busca híbrida, pipeline de extração com confiança, motor de regras, trilha append-only, Design System v1.0 (`globals.css`, `components/ui`, `components/condoos`). As novas capacidades (Assunto, Tarefa, Política, Oportunidade) entram como **módulos novos no mesmo monólito**, reaproveitando `Timeline`, `SidePanel`, `DataTable`, `InsightCard`, `EvidenceList`, `DecisionBar`. Nada a descartar.
