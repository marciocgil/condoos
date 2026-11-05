# CondoOS — guia para o Claude

Agente auditor de despesas de condomínios. Ele lê as despesas do mês, confere cada uma contra contrato, CNPJ, extrato e histórico, e entrega ao síndico **achados** priorizados por valor em risco, com evidência. Uma pessoa sempre decide; o sistema nunca move dinheiro.

Especificação completa: o prompt do MVP (seções 0–15) e o PDF "CondoOS — Arquitetura do Agente Auditor (MVP)". Decisões tomadas: `docs/decisions.md`. Regras de auditoria: `docs/rules.md`. Telas de referência: `docs/mockups.md`. **Visual: `CondoOS_Design_System_v1.0` (tema escuro), auditoria e componentes em `docs/ui-audit.md`.** Acurácia da extração: `docs/extraction_accuracy.md`.

## Regras de trabalho

- Trabalhar marco a marco. Ao fim de cada marco: testes passando, `docker compose up` funcionando, commit, resumo e atualização deste arquivo.
- Perguntar só quando a escolha for difícil de desfazer (modelo de dados, contrato de API). O resto: decidir e registrar em `docs/decisions.md`.
- **Dados sempre fictícios.** CNPJs com dígito verificador válido, gerados ao acaso (`app.core.br.generate_cnpj`). E-mails em subdomínios de `example.com`.
- Segredos só por variável de ambiente (`.env.example`). Nunca commitar `.env`.
- Licenças: só MIT, Apache-2.0, BSD ou equivalentes no produto. Nada de n8n, Dify, GPL, AGPL ou LGPL. Na dúvida, perguntar.
- Idioma: código, nomes e commits em inglês; interface, relatórios e mensagens ao usuário em português do Brasil.
- Linguagem dos achados: "indício", "divergência", "ponto de atenção". Nunca "fraude", "desvio" ou "irregularidade comprovada".
- Prompts de LLM em `api/app/prompts/*.md`; toda chamada passa pelo cliente único que registra `llm_calls` (Marco 2).

## Estrutura

```
api/            FastAPI + SQLAlchemy 2 (async) + Alembic; worker da fila de jobs
  app/auth/       link mágico, sessões, RBAC (rbac.py), dependências (deps.py)
  app/core/       br.py (CNPJ/CPF), money.py (R$, datas), jobs.py (fila SKIP LOCKED), audit.py
  app/ingestion/  documents.py (upload/e-mail → document + job), email.py, filetypes.py,
                  bank/ (OFX, CSV, cnab/ com registro por banco, service.py)
  app/extraction/ pipeline.py (job document.process), convert.py (Docling/pypdfium2),
                  heuristics.py, boleto.py, xml_fiscal.py, llm_extract.py, fields.py
                  (campos por tipo), confidence.py (regra de confiança)
  app/llm/        client.py (cliente único: live/record/replay/off), pricing.py, schema.py
  app/enrichment/ suppliers.py (BrasilAPI, cache 30 dias), indices.py (BCB SGS)
  app/matching/   documents.py (documento → despesa → contrato), bank.py (despesa ↔ extrato),
                  categories.py (categorias e CNAE), text.py
  app/rules/      engine.py (motor), base.py, contracts.py (valor reajustado), judge.py (IA
                  de R04/R07), r01..r12 (uma classe por regra)
  app/chat/       search.py (trechos + busca híbrida), tools.py (9 ferramentas de leitura),
                  agent.py (Claude Agent SDK), service.py (verificações e histórico), warmup.py
  app/reports/    data.py (dados do relatório e pendências do mês), pdf.py, xlsx.py
  app/prompts/    prompts versionados (*.md)
  app/db/         models.py, enums.py, session.py, migrations/
  app/routers/    endpoints
  app/seed/       seed fictício (data.py, com casos plantados por regra; documents.py com
                  convenção, ata e textos dos contratos), carga (run.py),
                  fixtures/bcb_indices.json (séries reais do BCB)
  app/storage/    S3 (chave sempre começa com cond/<condominium_id>/)
  app/worker.py   consumidor da fila; registre handlers em HANDLERS
  tests/          pytest (precisa de PostgreSQL 16 + pgvector)
  tests/fixtures/corpus/  30 documentos fictícios + ground_truth.json
  tests/chat_eval/        avaliação do chat (33 casos; o teste ao vivo é `slow`)
  corpus/         generate.py (gera o corpus) e accuracy.py (relatório de acurácia)
web/            Next.js 15 (App Router) + TypeScript strict + Tailwind 4 + lucide-react
  app/globals.css tokens do Design System (cores, raios, Inter); nunca use cores fixas
  components/ui/       componentes genéricos (Button, Card, KpiCard, Badge, Field, DataTable,
                       FilterChips, SidePanel, Timeline, EmptyState) — sem regra de negócio
  components/condoos/  componentes do domínio (SeverityBadge, InsightCard, EvidenceList,
                       DecisionBar, FindingDetailView, ...)
  components/layout/   Logo, AdminHeader, PageHeader
  app/(sindico)/condominio/[id]/...   telas mobile-first (390 px)
  app/(admin)/admin/...               telas desktop da administradora
  lib/api.ts      chamadas server-side à API, repassando o cookie de sessão
  tests/e2e/      Playwright (roda contra a stack do docker compose)
docs/           decisions.md, rules.md
```

## Comandos

```bash
make up            # sobe tudo: postgres, s3 (SeaweedFS), mailpit, api, worker, web
make test          # pytest do backend
make coverage      # testes + cobertura mínima de 80% em rules, matching, extraction
make lint          # ruff, black, mypy strict, eslint, tsc, prettier
make e2e           # Playwright contra a stack (zera o limite de links por hora antes)
make migrate seed  # migrações e seed no banco de DATABASE_ADMIN_URL
make corpus        # regera o corpus fictício (determinístico)
make accuracy      # relatório de acurácia por campo → docs/extraction_accuracy.md
make chat-eval     # avaliação do chat ao vivo (exige ANTHROPIC_API_KEY) → docs/chat_eval.md
```

- Web: http://localhost:3000 · API: http://localhost:8000/docs · E-mails: http://localhost:8025
- Usuários do seed: `ana.sindica@acacias.example.com` (síndica), `bruno.conselho@acacias.example.com` (conselheiro), `carla.sindica@mirante.example.com` (síndica), `diego.gerente@atlantida.example.com` (gerente), `elisa.analista@atlantida.example.com` (analista).
- Testes do backend: `TEST_DATABASE_ADMIN_URL` (padrão `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`). A suíte recria o banco `condoos_test`, aplica as migrações e carrega o seed.
- E2E com um Chromium do sistema: `PW_CHROMIUM_PATH=/caminho/do/chrome make e2e`.
- LLM: sem `ANTHROPIC_API_KEY`, o modo é `replay` (só respostas gravadas; o resto vai para a fila). Para gravar respostas reais: `LLM_MODE=record`. A suíte de testes nunca chama a API.
- E-mail de entrada local: coloque `.eml` em `data/inbound-email/` (para `<slug>@ingest.condoos.local`); o worker lê a cada 30 s.

## Convenções importantes

- **Multi-tenant:** toda tabela com dados de condomínio tem `condominium_id`. Toda consulta filtra por ele **e** o RLS do PostgreSQL filtra de novo. Ao criar uma tabela nova com dados de condomínio, acrescente-a em `RLS_TABLES` (`app/db/models.py`) e crie uma migração com a política. Teste o isolamento.
- **Banco nas rotas:** use sempre o alias `DbSession` (commit antes da resposta, D18). Rotas de um condomínio recebem `access = Depends(require(Permission.X))`.
- **Outro condomínio = 404**, nunca 403.
- **`decision` e `audit_log` só aceitam inclusão.** Nunca apagar nem alterar.
- **Jobs** são idempotentes: use `dedupe_key` ao enfileirar e o hash do arquivo para documentos.
- **Logs** só com ids, nunca dados de cliente.
- **CPF** sempre mascarado (`app.core.br.mask_cpf`).
- **Migrações** nunca importam listas do código da aplicação (congele os valores na migração).
- **Extração:** nada de valor "chutado". Campo obrigatório abaixo de 0,9 → fila. A IA recebe só o texto quando há texto; o arquivo só quando não há.
- **Documento revisado por pessoa** (`reviewed_at`) nunca é reprocessado.
- **Regras** são determinísticas; R04 e R07 usam IA só onde a parte determinística não decide, e sem IA ficam "não avaliadas". Toda mudança de regra exige teste positivo e negativo em `tests/test_rules.py` e manter `tests/test_planted_cases.py` exato (todos os positivos, nenhum extra).
- **Achados** nunca usam "fraude", "desvio" ou "irregularidade comprovada" (o motor recusa).
- **Explicações por IA** só citam números dos dados da regra e das evidências; `findings/explain.py` confere por código.
- **Decisões** seguem `findings/decisions.py` (quem pode o quê); a interface mostra só `allowed_actions`.
- **Interface:** use os tokens e os componentes de `components/ui` e `components/condoos`; status sempre com texto e ícone, nunca só cor; verde-lima só em ação primária e item ativo.
- **Casamento ambíguo** vai para `match_issue`, nunca é escolhido ao acaso.
- **Chat:** só ferramentas de leitura em `app/chat/tools.py`, nenhuma recebe o condomínio (vem da sessão; o RLS da pergunta fica restrito a ele). Ferramenta nova: devolva `ref` em cada registro, respeite a visibilidade do papel e acrescente um caso em `tests/chat_eval/cases.py`. Números, citações e ação sugerida são conferidos por código (`service.py`).
- **Relatórios** são a visão do corpo diretivo (sem achados aguardando validação). Rodapé de IA em toda página; competência só fecha com a fila daquele mês vazia.

## Status dos marcos

- [x] **Marco 1 — Fundação** (05/11/2026): repositório, docker compose, migrações com RLS, link mágico, sessões, RBAC, fila de jobs, seed (1 administradora, 2 condomínios, 12 meses), telas iniciais do síndico e da administradora, testes de isolamento.
- [x] **Marco 2 — Ingestão e extração** (05/11/2026): upload, e-mail (.eml), OFX, CSV, CNAB 240/400 (Itaú, Bradesco, BB), Docling + LLM com confiança por campo, fila de exceções com tela de correção, corpus de 30 documentos e relatório de acurácia.
- [x] **Marco 3 — Enriquecimento, casamento e regras** (05/11/2026): BrasilAPI com cache, índices reais do BCB, casamento documento ↔ despesa ↔ extrato ↔ contrato com fila para ambiguidades, as 12 regras com testes positivo/negativo, casos plantados no seed e teste de aceite exato.
- [x] **Marco 4 — Achados, roteamento e telas** (05/11/2026): explicações por IA com validação numérica, decisões e trilha, telas do síndico e da administradora no Design System v1.0 (tema escuro), Playwright dos 4 fluxos.
- [x] **Marco 5 — Chat e relatório** (05/11/2026): busca híbrida (embeddings locais + texto completo) em contratos, convenção e atas; chat com Claude Agent SDK e 9 ferramentas de leitura, citações e ação sugerida conferidas por código; avaliação com 33 casos; relatório PDF/XLSX, trilha em PDF e fechamento de competência com fila vazia.
- [ ] Marco 6 — Prontidão para piloto

### Pendências conhecidas

- **Meta de 90% sem revisão ainda não medida com o LLM**: sem chave, 12/30 (40%) com 0 erro automático. Medir com `LLM_MODE=record make accuracy` quando houver chave.
- Layouts CNAB não validados com arquivo real de banco (D28).
- R04 e R07 (parte por IA) só são avaliadas de verdade com chave de API; hoje são testadas com respostas de modelo simuladas.
- Sem chave de API, as explicações ficam no texto determinístico da regra (a reescrita por IA roda quando há chave).
- **Avaliação do chat ao vivo não rodada**: sem chave de API, o chat responde 503 e só o gabarito da avaliação é testado. Rodar `make chat-eval` quando houver chave (aceite: ≥ 90%, zero vazamento).
- O executável do Claude Code embutido no `claude-agent-sdk` segue termos comerciais da Anthropic (D54): revisar antes do piloto.
