# CondoOS Launch — estado e próximos passos

**Leia isto primeiro ao retomar o Launch.** Prompt de origem: `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md` (v1.0). Decisão de abertura: D88 em `docs/decisions.md`.

## Estado (07/11/2026)

| Fase | Estado | Evidência |
|---|---|---|
| LF0 Diagnóstico | ✅ concluída (gate LG0 verificado) | `01-diagnostico-as-is.md` |
| LF1 Blueprint | **pronto_para_validar** — aguarda revisão do Marcio (gate LG1) | `02`–`06` deste diretório |
| LF2–LF8 | nao_iniciado | `05-backlog.md` |

Nenhum código, migração ou teste foi alterado no Launch até aqui.

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

## Perguntas para o Marcio (bloqueiam partes específicas)

| # | Pergunta | Bloqueia | Hipótese se não houver resposta |
|---|---|---|---|
| Q-L01 | Auto-cadastro do síndico ou implantação assistida (Admin CondoOS cria e convida) no piloto? | LB-009, DL-01 | Assistida no piloto; auto-cadastro P2 com verificação de autoridade |
| Q-L02 | Pedidos a terceiros: o sistema gera link e texto e o síndico envia (nada sai), ou o CondoOS envia e-mail como ação aprovada? | LF4, LB-053 | Primeiro corte manual (coerente com D83 e Plano D-04) |
| Q-L03 | Ordem: Launch LF2 antes da VS-06 (Operate controlado, aguardando decisão)? | Sequência | LF2 primeiro: não depende de piloto real e alimenta a VS-06 |
| Q-L04 | Aprovar migração 0018 (`launch_state`, ADR-L01) e a mudança de API de LB-009 (alçadas opcionais no cadastro)? | LF2 | Sem aprovação, LF2 começa pelas partes sem migração (LB-021, LB-002, LB-010, LB-006) |

## Próximo incremento recomendado (após LG1)

**LF2-a — primeiro valor sem migração:** LB-021 (teste de injeção), LB-002 (marcos derivados), LB-010 (prontidão C1–C3), LB-006 (cartão de primeiro valor) e LB-004 (rota de leitura).
- Arquivos: `api/app/launch/{__init__,journey,readiness,first_value}.py`, `api/app/routers/launch.py`, `api/app/main.py` (registrar rota), `api/tests/test_launch_*.py`, `web/components/condoos/FirstValueCard.tsx`, `web/app/(sindico)/condominio/[id]/resumo/page.tsx`, `web/lib/types.ts`.
- Aceite: testes positivos/negativos de cada marco e capacidade; cartão de primeiro valor sem número fora de `extracted`; isolamento; `make lint` e `make test` verdes; E2E do F01 com contrato do corpus.
- Evidência: saída de testes, E2E, atualização deste arquivo, `docs/roadmap-status.md`, `docs/traceability.md` e `docs/decisions.md`.

## Ritual de cada incremento

1. Ler este arquivo e o item do backlog. 2. Conferir o código real. 3. Implementar só o incremento. 4. Testes, lint, E2E quando houver tela. 5. Atualizar esta tabela, `docs/roadmap-status.md`, `docs/traceability.md`, `docs/decisions.md`. 6. Commit e push na branch da sessão.
