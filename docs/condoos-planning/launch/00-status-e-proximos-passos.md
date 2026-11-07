# CondoOS Launch — estado e próximos passos

**Leia isto primeiro ao retomar o Launch.** Prompt de origem: `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md` (v1.0). Decisão de abertura: D88; respostas do Marcio e gate LG1: D89 (`docs/decisions.md`).

## Estado (07/11/2026)

| Fase | Estado | Evidência |
|---|---|---|
| LF0 Diagnóstico | ✅ concluída (gate LG0 verificado) | `01-diagnostico-as-is.md` |
| LF1 Blueprint | ✅ aprovado pelo Marcio (gate LG1, D89) | `02`–`06` deste diretório |
| LF2 Primeiro valor | **em_desenvolvimento**: LF2-a (D90) e LF2-b (D91) entregues; próxima LF2-c | `05-backlog.md`, D90, D91 |
| LF3–LF8 | nao_iniciado | `05-backlog.md` |

Código do Launch: `api/app/launch/`, `api/app/routers/launch.py`, migração 0018; testes `api/tests/test_launch.py` e `api/tests/test_prompt_injection.py` (D90).

## Nomes (sem colisão, D88)

Marcos do Launch **LM1–LM5** · fases **LF0–LF8** · gates **LG0–LG8** · backlog **LB-xxx** · ADRs **ADR-L01..** · divergências **DL-01..** · perguntas **Q-L01..**. Os marcos do Plano Diretor seguem M0–M5/G0–G5; os do MVP, "Marco 1–6".

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `01-diagnostico-as-is.md` | Inventário, reaproveitamento, lacunas, riscos, divergências DL-01..06 |
| `02-blueprint-jornada-ux.md` | PRD, personas, LM1–LM5, objetivo inicial, três modos, fluxos F01–F06, protótipos e microcopy |
| `03-arquitetura-e-dados.md` | Capacidades lógicas, entidades × existentes, ADR-L01..L06, segurança |
| `04-prontidao-por-capacidade.md` | Matriz C1–C9, estados, grafo de dependências |
| `05-backlog.md` | LB-xxx por fase, gates, ordem de LF2 |
| `06-testes-pilotos-metricas.md` | Cenários, métricas, experimentos |

## Respostas do Marcio (D89, 07/11/2026)

| # | Pergunta | Resposta |
|---|---|---|
| Q-L01 | Auto-cadastro ou implantação assistida? | **Assistida pelo Admin CondoOS** no piloto; auto-cadastro em P2 |
| Q-L02 | Pedidos a terceiros: quem envia? | **Corte manual**: o CondoOS gera link e texto, o síndico envia; nada sai do sistema |
| Q-L03 | LF2 antes da VS-06? | **Sim** |
| Q-L04 | Migração 0018 e alçadas opcionais no cadastro (LB-009)? | **Aprovadas** |

Ainda pedem aprovação própria, quando chegar a vez: migração de tipos documentais (LB-020, CHECK de `document.doc_type`) e migração `data_issue` (LF3, ADR-L05). ADR-L06 (triagem de arquivo malicioso) antes de LF4.

## Próximos incrementos (LF2, nesta ordem)

LF2-a entregue em 07/11/2026 (D90; escolhas registradas lá, entre elas LM1 sem exigir objetivo e C1 dependente do assistente). LF2-b entregue em 07/11/2026 (D91): cartão da jornada em "Hoje", leitura do contrato e envio com retorno, com E2E do F01. Próximo: **LF2-c**.

| Incremento | Itens | Migração | Aceite principal |
|---|---|---|---|
| ~~LF2-a — fundação da jornada~~ **entregue (D90)** | LB-021 (teste SEC-02, PDF com instrução maliciosa), LB-001 (`launch_state`, rotas de objetivo e "fazer depois"), LB-002 (marcos LM1–LM5 derivados), LB-010 (prontidão C1–C3), LB-003 (próximo passo), LB-004 (`GET /condominiums/{id}/launch`) | 0018 (aprovada) | Positivo e negativo por marco e capacidade; seed Acácias com LM1–LM3, condomínio novo só LM1; conselheiro 403 na escrita, outro condomínio 404 + evento; migração ida e volta; `make lint` e `make test` verdes |
| ~~LF2-b — primeiro valor na tela~~ **entregue (D91)** | LB-006 (cartão de primeiro valor), LB-007 (upload com retorno), LB-005 (cartão da jornada em "Hoje"), LB-008 ("o que o CondoOS já fez") | — | Nenhum número fora de `extracted`; campo < 0,9 rotulado "a confirmar"; 390 px; E2E do F01 com contrato do corpus |
| **LF2-c — medição e visão da equipe** | LB-090 (eventos `launch.*` e métricas), LB-011 (prontidão em Ajustes e Configurações), LB-012 (implantações na Carteira), LB-022 (bordas do upload) | — | Tempo até primeiro valor medido; mensagens de borda em PT-BR sem documento fantasma |
| **LF2-d — cadastro assistido e tipos** | LB-009 (alçadas opcionais, D89), LB-020 (tipos documentais) | LB-020: **pedir aprovação** | Condomínio sem alçada: política nega pedido de ação com motivo; gate **LG2** (E2E completo do síndico novo) |

Arquivos do LF2-c: `api/app/metrics.py` (tempo até o primeiro valor a partir de `launch.first_value_shown`, passos adiados, dias sem evento, custo de IA e correções por documento; LB-090), prontidão em `web/app/(sindico)/condominio/[id]/ajustes/` e `web/app/(admin)/admin/configuracoes/` (LB-011, com `GET /condominiums/{id}/launch`), implantações em andamento na Carteira (`api/app/routers/portfolio.py` + `web/app/(admin)/admin/carteira/`, LB-012), bordas do upload (`api/app/ingestion/documents.py`, `tests/test_ingestion.py`, LB-022). Rotas do Launch hoje: `GET /launch`, `PUT /launch/goal`, `POST /launch/postpone`, `POST /launch/dismiss`, `GET /launch/first-value/{document_id}` e `POST .../shown`.

## Ritual de cada incremento

1. Ler este arquivo e o item do backlog. 2. Conferir o código real. 3. Implementar só o incremento. 4. Testes, lint, E2E quando houver tela. 5. Atualizar esta tabela, `docs/roadmap-status.md`, `docs/traceability.md`, `docs/decisions.md`. 6. Commit e push na branch da sessão.
