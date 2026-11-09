# CondoOS — guia para o Claude

Agente auditor de despesas de condomínios. Ele lê as despesas do mês, confere cada uma contra contrato, CNPJ, extrato e histórico, e entrega ao síndico **achados** priorizados por valor em risco, com evidência. Uma pessoa sempre decide; o sistema nunca move dinheiro.

Especificação completa: o prompt do MVP (seções 0–15) e o PDF "CondoOS — Arquitetura do Agente Auditor (MVP)". Decisões tomadas: `docs/decisions.md`. Regras de auditoria: `docs/rules.md`. Telas de referência: `docs/mockups.md`. **Visual: `CondoOS_Design_System_v1.0` (tema escuro), auditoria e componentes em `docs/ui-audit.md`.** Acurácia da extração: `docs/extraction_accuracy.md`.

## Planejamento estratégico (`docs/condoos-planning/`, v1.0 de 06/11/2026)

Referência estratégica e funcional da evolução do produto (de auditor de despesas para assessor do síndico: Core, Advisor, Optimize, Operate, Procurement). **São referências, não ordens:** nunca executar todas as fases, pacotes ou prompts de uma vez.

- `02_Contexto_Produto/…Especificacao_Mestra_v1.0.md`: requisitos CAP-01..12, FR-001..065, fluxos FL-01..12, personas, autonomia (§9), dados (§11), NFR (§16), backlog (§20), testes (§21), instruções para IA (§25).
- `01_Plano_Diretor/…Plano_Diretor…v1.0.docx`: marcos M0–M5, pacotes WP-00..24 e dependências, fatias VS-01..06, gates G0–G5, testes SEC/DOC/FIN/OPT/OPS/AI, DoR/DoD. Ler com `pandoc -t plain --wrap=none <arquivo>`.
- `03_Prompts/Individuais/`: `00_LEIA_PRIMEIRO.md` (ordem e disciplina), `01`–`10` (uma etapa cada) e `11_EXECUTAR_PROXIMA_FATIA.md` (ritual de cada ciclo). O pacote consolidado repete o mesmo conteúdo.

Como usar:

1. **Ler antes de planejar.** Antes de propor mudança de produto, localizar os FR/CAP/WP/VS afetados nesses documentos e inspecionar o código real. Não alegar leitura, teste ou execução que não ocorreu.
2. **Uma fatia vertical por vez**, só com dependências e gate anterior satisfeitos (ordem do Plano Diretor §4 e §9). Escopo excluído explícito; P2/P3 só depois de P0 coberto.
3. **Preservar o que existe.** Arquitetura atual (FastAPI + Next.js, RLS, fila de jobs, cliente LLM único), Design System v1.0 (`web/app/globals.css`, `components/ui`, `components/condoos`, `docs/ui-audit.md`) e todas as regras deste arquivo continuam valendo. Mudança estrutural só com decisão registrada.
4. **Conflitos não se resolvem em silêncio.** Precedência do pacote: requisitos aprovados > decisões aceitas > código real (estado) > plano > sugestão de IA. Se o planejamento divergir deste arquivo, de `docs/decisions.md` ou do produto atual (ex.: público inicial, papel da administradora, revisão interna do Optimize), registrar a divergência e perguntar ao Marcio.
5. **Nomes sem colisão.** "Marco 1–6" abaixo são os marcos do MVP auditor (concluídos); os marcos do planejamento são M0–M5. Decisões do projeto seguem em `docs/decisions.md` (D72 em diante); as decisões abertas do Plano Diretor são citadas como "Plano D-01..D-12".
6. **Registrar entre sessões.** Ao fim de cada fatia: `docs/roadmap-status.md` (estado por requisito: `nao_iniciado` … `validado`, só com evidência) e `docs/traceability.md` (FR ↔ código ↔ teste), além de `docs/decisions.md`. O prompt 01 foi rodado em 07/11/2026 (D72): diagnóstico em `docs/01-repo-audit.md`, FR × produto em `docs/02-gap-matrix.md`, propostas e divergências em `docs/03-decisions-register.md`, além de `docs/product-roadmap.md`, `docs/backlog.md` (histórias CB-xxx) e `docs/pilot-protocol.md`. DV-01..DV-05 respondidas pelo Marcio (D73–D77): condomínio é o cliente e a administradora é colaboradora opcional; revisão humana proporcional ao risco (economia sempre revisada); Assunto independente e N:N com achados; Oportunidade e estágios de economia separados de achado; papéis síndico, CondoOS Admin, CondoOS Reviewer e administradora no piloto. Modelo proposto em `docs/data-model.md`, permissões em `docs/authorization-matrix.md`, fluxos em `docs/flows.md`; as migrações 0011–0014 só são escritas depois de aprovadas.
7. **CondoOS Launch** (D88): implantação guiada e saúde dos dados. Prompt em `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md`; estado e próximos passos em `docs/condoos-planning/launch/00-status-e-proximos-passos.md` (ler antes de mexer no Launch). Nomes próprios: LM1–LM5, LF0–LF8, LG0–LG8, LB-xxx. Marco da jornada nunca é permissão; prontidão é por capacidade e binária.
8. **Limites do produto continuam:** nenhuma ação externa, pagamento, contratação, multa ou envio sem política e aprovação humana (envios existentes: o e-mail do pedido de documentos, D103, e o resumo semanal de vencimentos ao síndico, D113); recomendação do Optimize só sai após revisão interna; dados de piloto reais só com autorização.

## Regras de trabalho

- Trabalhar marco a marco. Ao fim de cada marco: testes passando, `docker compose up` funcionando, commit, resumo e atualização deste arquivo.
- Perguntar só quando a escolha for difícil de desfazer (modelo de dados, contrato de API). O resto: decidir e registrar em `docs/decisions.md`.
- **Dados sempre fictícios.** CNPJs com dígito verificador válido, gerados ao acaso (`app.core.br.generate_cnpj`). E-mails em subdomínios de `example.com`. Testes que rodam contra a stack (E2E) não cadastram fornecedor com CNPJ aleatório: um CNPJ válido pode ser de empresa real e a consulta à BrasilAPI traria dados reais. Use os fornecedores do seed (já enriquecidos, sem consulta).
- Segredos só por variável de ambiente (`.env.example`). Nunca commitar `.env`.
- Licenças: só MIT, Apache-2.0, BSD ou equivalentes no produto. Nada de n8n, Dify, GPL, AGPL ou LGPL. Na dúvida, perguntar. Única exceção: o executável do Claude Code dentro do `claude-agent-sdk` (D107).
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
  app/onboarding/ cadastro de condomínio novo (python -m app.onboarding <arquivo.json>)
  app/routers/registry.py   telas de cadastro (dados, corpo diretivo, acessos, contratos, novo condomínio)
  app/routers/approvals.py  aprovações de despesa (R12)
  app/metrics.py  métricas internas do piloto (precisão, extração automática, revisão, custo)
  app/pending.py  cockpit de pendências: faturamento dos contratos e aprovação dos avulsos (D70)
  app/agenda.py   agenda: vencimentos, NF prevista, reajustes e fim de contrato (D71)
  app/core/retention.py  política de retenção (job diário retention.purge)
  app/policy/     motor de política das ações (nega por padrão) e kill switch (D83)
  app/actions/    pedido de ação com aprovação, outbox e despacho sem envio (D83)
  app/launch/     implantação guiada (D89): marcos por fatos, prontidão por capacidade,
                  cartão de primeiro valor, próximos passos, launch_state
  app/data_issues/ conflitos entre documentos (D93): detectores, ciclo, Central de Validação
  app/delegation/ pedido de documentos a terceiros com link só de envio (D95)
  app/ingestion/triage.py  triagem de arquivos em todo envio (D95)
  app/delegation/email.py  e-mail do pedido enviado pelo CondoOS com aprovação do síndico (D103)
  app/ingestion/email.py   e-mail de entrada: pasta local ou SES → S3, endereço com parte aleatória (D101)
  app/compliance/ conformidade e vencimentos (D112): catálogo de candidatas, situação calculada,
                  leitura da validade pela IA (job compliance.read_validity); perfil do prédio
                  e resumo semanal por e-mail (D113, job compliance.reminders)
  scripts/pilot_run.py   aceite do Marco 6: condomínio fictício do upload ao relatório
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
docs/           decisions.md, rules.md, deploy.md (implantação), lgpd.md (checklist),
                pilot/ (cadastro de exemplo e resultado do aceite)
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
make accuracy-docling  # o mesmo no worker do docker, com Docling → docs/extraction_accuracy_docling.md
make rules-eval    # casos plantados com o modelo real para R04/R07 (exige chave) → docs/rules_eval.md
make chat-eval     # avaliação do chat ao vivo (exige ANTHROPIC_API_KEY) → docs/chat_eval.md
make pilot         # aceite do Marco 6 (após reset + up) → docs/pilot/run.md
```

- Web: http://localhost:3000 · API: http://localhost:8000/docs · E-mails: http://localhost:8025
- Usuários do seed: `ana.sindica@acacias.example.com` (síndica), `bruno.conselho@acacias.example.com` (conselheiro), `carla.sindica@mirante.example.com` (síndica), `diego.gerente@atlantida.example.com` (gerente), `elisa.analista@atlantida.example.com` (analista), `fabio.admin@condoos.example.com` (Admin CondoOS, nos dois condomínios), `gabriela.revisora@condoos.example.com` (Reviewer CondoOS, só Mirante).
- Equipe CondoOS (D79): `python -m app.platform grant-role|revoke-role|assign|unassign ...` (papel dono do banco) cria o primeiro Admin; depois o Admin atribui pela API `/condominiums/{id}/assignments`.
- Testes do backend: `TEST_DATABASE_ADMIN_URL` (padrão `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`). A suíte recria o banco `condoos_test`, aplica as migrações e carrega o seed.
- E2E com um Chromium do sistema: `PW_CHROMIUM_PATH=/caminho/do/chrome make e2e`.
- LLM: sem `ANTHROPIC_API_KEY`, o modo é `replay` (só respostas gravadas; o resto vai para a fila). Para gravar respostas reais: `LLM_MODE=record`. A suíte de testes nunca chama a API.
- **Produção (D106):** VPS da Hostinger, `https://app.condoos.ia.br`, `docker-compose.prod.yml` com Caddy; documentos e backup diário cifrado no S3 de São Paulo. Passo a passo, atualização, backup e restauração em `docs/deploy.md` seção 9. Primeiro Admin num banco vazio: `python -m app.platform add-person` e depois `grant-role`.
- E-mail de entrada local: coloque `.eml` em `data/inbound-email/` (para `<slug>-<parte aleatória>@ingest.condoos.local`, mostrado em Ajustes; fora de produção `<slug>@` também vale); o worker lê a cada 30 s. Produção: Amazon SES em São Paulo → S3 (`docs/deploy.md` seção 7, D101).

## Convenções importantes

- **Multi-tenant:** toda tabela com dados de condomínio tem `condominium_id`. Toda consulta filtra por ele **e** o RLS do PostgreSQL filtra de novo. Ao criar uma tabela nova com dados de condomínio, acrescente-a em `RLS_TABLES` (`app/db/models.py`) e crie uma migração com a política. Teste o isolamento.
- **Banco nas rotas:** use sempre o alias `DbSession` (commit antes da resposta, D18). Rotas de um condomínio recebem `access = Depends(require(Permission.X))`.
- **Outro condomínio = 404**, nunca 403. A tentativa é gravada como `security.access_denied` (e o 403 por papel como `security.permission_denied`) por `auth/deps.py`, em transação própria (D78). Rotas de condomínio devem passar por `require()`/`get_condo_access` para herdar isso.
- **CI** (`.github/workflows/ci.yml`) roda `make lint` e `pytest` com pgvector a cada push; mantenha-o verde.
- **`decision` e `audit_log` só aceitam inclusão.** Nunca apagar nem alterar.
- **Jobs** são idempotentes: use `dedupe_key` ao enfileirar e o hash do arquivo para documentos.
- **Logs** só com ids, nunca dados de cliente.
- **CPF** sempre mascarado (`app.core.br.mask_cpf`).
- **Migrações** nunca importam listas do código da aplicação (congele os valores na migração).
- **Extração:** nada de valor "chutado". Campo obrigatório abaixo de 0,9 → fila. A IA recebe só o texto quando há texto; o arquivo só quando não há. Foto ou imagem vai sempre como imagem, mesmo com texto do OCR (D99).
- **Documento revisado por pessoa** (`reviewed_at`) nunca é reprocessado.
- **Regras** são determinísticas; R04 e R07 usam IA só onde a parte determinística não decide, e sem IA ficam "não avaliadas". Toda mudança de regra exige teste positivo e negativo em `tests/test_rules.py` e manter `tests/test_planted_cases.py` exato (todos os positivos, nenhum extra).
- **Achados** nunca usam "fraude", "desvio" ou "irregularidade comprovada" (o motor recusa).
- **Explicações por IA** só citam números dos dados da regra e das evidências; `findings/explain.py` confere por código.
- **Decisões** seguem `findings/decisions.py` (quem pode o quê); a interface mostra só `allowed_actions`.
- **Acesso** (D79): papéis vêm de `membership` ativa (sem `revoked_at`, dentro de `expires_at`) e, para a equipe CondoOS, de `platform_role` + `condo_assignment` vigentes. Monte permissões sempre com `auth/deps.py::access_for` (aplica `management_company_reviews`). Nenhum papel recebe `frozenset(Permission)`; validar e aprovar ficam em papéis separados (`tests/test_access_model.py`). Remover acesso revoga, não apaga.
- **Assuntos** (D80): regras em `app/cases/` (estados, "sem próxima ação, sem controle", resolução com tarefas fechadas e evidência, vínculos que nunca se apagam, duplicidade antes de criar). `case_event` só aceita inclusão. Evidência enviada pelo assunto não vai para a extração (`ingest_file(process=False)`). Datas na tela em horário de Brasília (`lib/format.ts`); prazo só com a data vale até 23h59 do fuso do condomínio.
- **Oportunidades** (D81): economia só calculada por código (`app/opportunities/`, método versionado), uma linha por estágio em `savings_record` (só inclusão), estágios nunca somados e sempre com o nome próprio. Antes da aprovação da revisora CondoOS a oportunidade responde 404 para o condomínio; o corpo diretivo vê só a estimativa validada. Revisar e aprovar pelo condomínio são papéis diferentes.
- **Briefing** (D82): montado por código em `app/briefing/` só a partir de registros; cada seção roda num savepoint e, se falhar, vira "dados parciais" (o teste exige que em uso normal só dados desatualizados sejam parciais). Um por pessoa, condomínio e dia; "atualizar" cria versão nova. Só dentro do app, sem e-mail. Na tela do síndico a aba "Resumo" se chama "Hoje" (rota `/resumo`).
- **Ações e kill switch** (D83): só `app/policy/` autoriza (código tipado, versionado, nega por padrão; pagamento, contratação, multa e dados bancários negados sempre; nenhuma regra responde "permite"). Pedido em `app/actions/`: conteúdo congelado por hash, o síndico aprova a versão que viu, a aprovação vale 7 dias, mudança depois de aprovada anula. O despacho (`action.dispatch`) confere tudo de novo e **não envia nada**: a ação espera uma pessoa executar e registrar. Única exceção: `pedido_documento.enviar_email` (D103), que envia o e-mail aprovado. Custo acima do teto ou aprovação vencida voltam para aprovação. `action_decision` só aceita inclusão; outbox com chave única. Tipo de job novo que tenha efeito entra em `PAUSABLE_JOBS` (o worker não roda job pausado).
- **Economia contratada e realizada** (D84): "contratada" só com o documento do acordo (`record_contracted`, `acordo_v1`); "realizada" só a revisora CondoOS mede, pelas faturas com nota emitidas depois do acordo (`measure_realized`, `medicao_faturas_v1`). Cada estágio é linha nova em `savings_record`; nada paga nem envia.
- **Versões e proveniência** (D85): alçadas e parâmetros mudam por `app/condo_settings.py` (versão nova com autor e motivo; regras usam `ctx.limits`/`ctx.rule_params`, a versão vigente no mês, nunca `condominium.approval_limits` direto). Extração grava `field_provenance` (origem, página, trecho; trecho só se o texto mostrar o valor). Documento novo do mesmo documento lógico entra por `.../documents/{id}/versions`; a busca usa só a versão vigente. Cláusulas de rescisão em `app/extraction/clauses.py` (por regra, com trecho; valor posto por pessoa fica).
- **Launch** (D89): marcos (LM1–LM5) e prontidão (C1–C3) são calculados dos dados a cada leitura, nunca gravados, e não liberam nada; só objetivo, adiados e cartão oculto ficam em `launch_state`. O cartão de primeiro valor só mostra valores de `document.extracted` (abaixo de 0,9 = "a confirmar") e sempre diz o que a leitura não cobre. Prompt que recebe documento traz a regra de conteúdo não confiável (`tests/test_prompt_injection.py`).
- **Conflitos de dados** (D93): só `app/data_issues/` detecta (determinístico, detector versionado, idempotente por `dedupe_key`); conflito sem ação de pessoa que some vira "superado", o que uma pessoa decidiu fica. Resolver exige um dos lados e motivo e não altera o contrato. Enquanto aberto: C2/C3 parciais, campo "conflitante" no cartão, linha na evidência dos achados e a política nega ação com o fornecedor. `data_issue_event` só aceita inclusão. Detector novo: teste positivo e negativo em `tests/test_data_issues.py` e conferir que o seed não gera falso positivo.
- **Pedidos a terceiros e triagem** (D95): o CondoOS gera o link e o texto, **o síndico envia**; "já enviei" é declaração. **Exceção única (D103):** o CondoOS envia o e-mail do pedido depois que o síndico aprova a versão exata (`app/delegation/email.py`, tipo interno `pedido_documento.enviar_email`): link gerado no envio (o token nunca é guardado), "aceito pelo servidor" nunca é "entregue", endereço mascarado depois, 1 por pedido a cada 24 h e 3 no total, 20 por condomínio por dia, 3 tentativas. Nenhum outro envio sem decisão nova. Token guardado só como hash; a rota pública acha o condomínio por `app_delegation_link_condominium` e roda com o papel da aplicação (RLS), só grava e responde o mesmo 404 para link inválido, vencido, revogado, fechado ou pausado. Destinatário só com nome e papel. `delegation_event` só aceita inclusão. Rotas públicas do link têm limite por endereço em memória (`core/ratelimit.py`, último item de `X-Forwarded-For`, nenhum IP gravado; D100). Todo arquivo passa por `ingestion/triage.py` (PDF com conteúdo ativo ou senha de abertura recusado; imagem regravada); em teste, use arquivos reais (`tests/helpers.py::jpeg_bytes`, `web/tests/e2e/files.ts::uniquePng`), não só a assinatura.
- **E-mail de entrada** (D101): endereço `<slug>-<inbound_token>@<domínio>`, os dois pedaços precisam bater; trocar o endereço invalida o antigo. Cada mensagem deixa uma linha em `inbound_message` (só inclusão; domínio do remetente e contagens, nunca assunto, corpo ou endereço completo); `Message-ID` em hash evita duplicar. Pausa `email.inbound` deixa a mensagem esperando. Nada é respondido ao remetente.
- **Conformidade** (D112): só uma pessoa decide se uma obrigação se aplica e a periodicidade (`validate_compliance`, com motivo); o catálogo só sugere e entra "a validar", sem citar norma. Situação calculada a cada leitura (`app/compliance/status.py`), nunca gravada; textos sem "irregular", "conforme" ou "em conformidade", e ausência de registro nunca é "não cumprida". Data lida pela IA só fica se estiver escrita no documento e é sempre "a confirmar" até uma pessoa confirmar. `compliance_evidence` e `compliance_event` só aceitam inclusão. Avisos dentro do app (Agenda, Hoje, chat). **D113:** perfil do prédio (`compliance/profile.py`) só sugere ("provavelmente se aplica/não se aplica"), nunca valida; dossiê em PDF por obrigação (EXPORT, auditado); resumo semanal por e-mail só ao síndico do condomínio, desligado até ele ligar (`configure_compliance_email`), segunda a partir das 8h no fuso do condomínio, só com vencido ou vencendo em até 30 dias, nome e data (sem valores), no máximo 1 por semana (`compliance_reminder`, só inclusão), pausa `conformidade.lembrete_email`; "enviado" = aceito pelo servidor.
- **Revisão** (D74, D79): o status inicial de um achado vem da política (`app/review/`), não da severidade direto. Status novo precisa entrar em `NOT_AT_RISK`/`UNDER_REVIEW` (`db/enums.py`) quando couber.
- **Telas da administradora** aceitam `?condominio=<id>` (filtro por condomínio, D69); o menu lateral mantém a escolha.
- **Interface:** use os tokens e os componentes de `components/ui` e `components/condoos`; status sempre com texto e ícone, nunca só cor; verde-lima só em ação primária e item ativo.
- **Casamento ambíguo** vai para `match_issue`, nunca é escolhido ao acaso.
- **Chat:** só ferramentas de leitura em `app/chat/tools.py`, nenhuma recebe o condomínio (vem da sessão; o RLS da pergunta fica restrito a ele). Ferramenta nova: devolva `ref` em cada registro, respeite a visibilidade do papel e acrescente um caso em `tests/chat_eval/cases.py`. Números, citações e ação sugerida são conferidos por código (`service.py`).
- **Relatórios** são a visão do corpo diretivo (sem achados aguardando validação). Rodapé de IA em toda página; competência só fecha com a fila daquele mês vazia.
- **Condomínio novo** entra pela Carteira ("Novo condomínio") ou por `app.onboarding` (nunca sobrescreve). Contratos chegam como documentos (D59) ou pelo formulário de Contratos (D67); termo aditivo vira `contract_amendment` ligado ao contrato (D66). Corpo diretivo e acessos são editados em Configurações. Achado não mais detectado e sem ação de pessoa vira `superado` (D61).
- **Aprovações (R12)** são registradas pela administradora no detalhe do achado (D65) ou no cockpit de Pendências, ligadas ao documento (proposta, ata, contrato).
- **Pendências** (D70) não são achados: contrato vigente sem NF no mês (pela periodicidade do contrato) e serviço avulso sem aprovação. Só a administradora vê. Antes de dizer "não recebida", `pending.py::arrivals` confere documentos de qualquer canal ainda não lançados (CNPJ e mês lidos): o contrato fica "em_conferencia" (D102). A cobertura do mês aparece na Agenda (`/coverage`).
- **Agenda** (D71) é só acompanhamento: datas previstas aparecem como "previsto", nunca geram achado, e não há ação de pagamento (o sistema não move dinheiro). Síndico e administradora veem.

## Status dos marcos

- [x] **Marco 1 — Fundação** (05/11/2026): repositório, docker compose, migrações com RLS, link mágico, sessões, RBAC, fila de jobs, seed (1 administradora, 2 condomínios, 12 meses), telas iniciais do síndico e da administradora, testes de isolamento.
- [x] **Marco 2 — Ingestão e extração** (05/11/2026): upload, e-mail (.eml), OFX, CSV, CNAB 240/400 (Itaú, Bradesco, BB), Docling + LLM com confiança por campo, fila de exceções com tela de correção, corpus de 30 documentos e relatório de acurácia.
- [x] **Marco 3 — Enriquecimento, casamento e regras** (05/11/2026): BrasilAPI com cache, índices reais do BCB, casamento documento ↔ despesa ↔ extrato ↔ contrato com fila para ambiguidades, as 12 regras com testes positivo/negativo, casos plantados no seed e teste de aceite exato.
- [x] **Marco 4 — Achados, roteamento e telas** (05/11/2026): explicações por IA com validação numérica, decisões e trilha, telas do síndico e da administradora no Design System v1.0 (tema escuro), Playwright dos 4 fluxos.
- [x] **Marco 5 — Chat e relatório** (05/11/2026): busca híbrida (embeddings locais + texto completo) em contratos, convenção e atas; chat com Claude Agent SDK e 9 ferramentas de leitura, citações e ação sugerida conferidas por código; avaliação com 33 casos; relatório PDF/XLSX, trilha em PDF e fechamento de competência com fila vazia.
- [x] **Marco 6 — Prontidão para piloto** (05/11/2026): cadastro de condomínio novo, contrato a partir do documento, métricas internas, retenção e auditoria de exportação, checklist LGPD, guia de implantação; aceite: condomínio fictício do upload ao relatório em 112 s (limite 15 min).

### Pendências conhecidas

- **Acurácia com o LLM** (D98, D99): 26/30 (87%) sem revisão (meta 90%), com ou sem Docling; 0 automático com dado divergente. PDFs e XMLs 25/25; as 4 fotos degradadas do corpus vão para revisão com motivo. Meta conferida no piloto, sem afrouxar a confiança. Repetir sem custo: `LLM_MODE=replay make accuracy` ou `LLM_MODE=replay make accuracy-docling`.
- Layouts CNAB não validados com arquivo real de banco (D28).
- R04 com o modelo real: aprovada (`make rules-eval`, D98). A parte por IA da R07 ainda não tem caso plantado.
- Sem chave de API, as explicações ficam no texto determinístico da regra (a reescrita por IA roda quando há chave).
- **Chat ao vivo** (D98): aprovado, 32/33 (97%) e zero vazamento, depois de corrigir a soma de `search_expenses` e o verificador de números de trechos.
- O executável do Claude Code embutido no `claude-agent-sdk` segue os termos comerciais da Anthropic: exceção à regra de licenças aceita pelo Marcio (D107), só para esse componente.
- Antes de dados reais (D107): termo do piloto assinado pela síndica (minuta pronta, revisão jurídica pendente) e comunicado aos condôminos.
