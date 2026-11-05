# CondoOS — guia para o Claude

Agente auditor de despesas de condomínios. Ele lê as despesas do mês, confere cada uma contra contrato, CNPJ, extrato e histórico, e entrega ao síndico **achados** priorizados por valor em risco, com evidência. Uma pessoa sempre decide; o sistema nunca move dinheiro.

Especificação completa: o prompt do MVP (seções 0–15) e o PDF "CondoOS — Arquitetura do Agente Auditor (MVP)". Decisões tomadas: `docs/decisions.md`. Regras de auditoria: `docs/rules.md`. Telas de referência: `docs/mockups.md`. Acurácia da extração: `docs/extraction_accuracy.md`.

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
  app/prompts/    prompts versionados (*.md)
  app/db/         models.py, enums.py, session.py, migrations/
  app/routers/    endpoints
  app/seed/       seed fictício (data.py) e carga (run.py)
  app/storage/    S3 (chave sempre começa com cond/<condominium_id>/)
  app/worker.py   consumidor da fila; registre handlers em HANDLERS
  tests/          pytest (precisa de PostgreSQL 16 + pgvector)
  tests/fixtures/corpus/  30 documentos fictícios + ground_truth.json
  corpus/         generate.py (gera o corpus) e accuracy.py (relatório de acurácia)
web/            Next.js 15 (App Router) + TypeScript strict + Tailwind 4
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
make lint          # ruff, black, mypy strict, eslint, tsc, prettier
make e2e           # Playwright contra a stack (zera o limite de links por hora antes)
make migrate seed  # migrações e seed no banco de DATABASE_ADMIN_URL
make corpus        # regera o corpus fictício (determinístico)
make accuracy      # relatório de acurácia por campo → docs/extraction_accuracy.md
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

## Status dos marcos

- [x] **Marco 1 — Fundação** (05/11/2026): repositório, docker compose, migrações com RLS, link mágico, sessões, RBAC, fila de jobs, seed (1 administradora, 2 condomínios, 12 meses), telas iniciais do síndico e da administradora, testes de isolamento.
- [x] **Marco 2 — Ingestão e extração** (05/11/2026): upload, e-mail (.eml), OFX, CSV, CNAB 240/400 (Itaú, Bradesco, BB), Docling + LLM com confiança por campo, fila de exceções com tela de correção, corpus de 30 documentos e relatório de acurácia.
- [ ] Marco 3 — Enriquecimento, casamento e regras
- [ ] Marco 4 — Achados, roteamento e telas
- [ ] Marco 5 — Chat e relatório
- [ ] Marco 6 — Prontidão para piloto

### Pendências conhecidas

- **Meta de 90% sem revisão ainda não medida com o LLM**: sem chave, 12/30 (40%) com 0 erro automático. Medir com `LLM_MODE=record make accuracy` quando houver chave.
- Layouts CNAB não validados com arquivo real de banco (D28).
- Documentos extraídos ainda não viram despesas: o casamento documento → despesa → contrato é do Marco 3 (gancho em `routers/queue.py` e no pipeline).
- Casos plantados das regras no seed: Marco 3.
- Botão "Pergunte ao CondoOS" e "Baixar relatório em PDF" aparecem desabilitados até os Marcos 5.
- Telas recebidas e descritas em `docs/mockups.md`; o restyle completo é do Marco 4.
