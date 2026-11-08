# CondoOS Launch — estado e próximos passos

**Leia isto primeiro ao retomar o Launch.** Prompt de origem: `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md` (v1.0). Decisão de abertura: D88 em `docs/decisions.md`.

## Estado (07/11/2026)

| Fase | Estado | Evidência |
|---|---|---|
| LF0 Diagnóstico | ✅ concluída (gate LG0 verificado) | `01-diagnostico-as-is.md` |
| LF1 Blueprint | ✅ aprovada pelo Marcio (gate LG1, D89) | `02`–`06` deste diretório |
| LF2 Primeiro valor | **validado** — LG2 no docker em 08/11/2026 (D96) | ver abaixo |
| LF3 Dados e reconciliação | **validado** — LG3 no docker em 08/11/2026 (D96) | `07-lf3-proposta-conflitos.md` |
| LF4 Colaborativo | **validado** — LG4 no docker em 08/11/2026 (D96); sobras entregues e validadas no docker (D100) | `08-lf4-proposta-delegacao.md` |
| LF5–LF8 | nao_iniciado | `05-backlog.md` |

**LF2-a entregue (D89):** LB-001 (`launch_state`, migração 0018), LB-002 (marcos por fatos), LB-003 (próximos passos), LB-004 (rotas), LB-005 (cartão de jornada no Hoje), LB-006/007 (cartão de primeiro valor no envio), LB-008 ("o que já fiz por você"), LB-010 (prontidão C1–C3), LB-021 (SEC-02), LB-090 parcial (eventos `launch.*`). Verificação: 322 testes do backend, lint backend e frontend, migração ida e volta, E2E `launch.spec.ts` passando numa stack local sem Docker (API e worker num processo, armazenamento em memória, `next dev`, substituto do Mailpit). Na suíte E2E inteira nessa stack, só `correction.spec.ts` falhou, e falha igual sem as mudanças desta fatia (efeito da stack local); **rodar `make e2e` na stack do docker** para confirmar.

**LF2-b entregue (D90):** LB-009 (alçada opcional no cadastro), C7 na prontidão, LB-011 (prontidão em Ajustes e Configurações), LB-012 (implantações na Carteira, `GET /portfolio/launch`), LB-022 (orientação nas bordas do envio), LB-090 (tempo até o primeiro valor em Métricas). Verificação: 324 testes do backend, lint, E2E `launch.spec.ts` (2 fluxos), `registry.spec.ts` e `backlog.spec.ts` passando na stack local sem Docker.

Código: `api/app/launch/` (`journey`, `readiness`, `first_value`, `steps`, `state`), `api/app/routers/launch.py`, `web/components/condoos/JourneyCard.tsx`, `FirstValueCard.tsx`.

**Última rodada E2E completa na stack local sem Docker (07/11/2026, depois da D95):** 30 passaram, 33 pulados por projeto (celular/desktop), 3 falharam: `correction.spec.ts` e `opportunities.spec.ts` esperam a navegação depois de salvar em 5 s e, no `next dev`, a página de destino compila na primeira visita (a operação foi gravada no banco); `backlog.spec.ts:50` (filtro rápido da fila de assuntos) passou ao repetir. Nenhuma falha ligada ao Launch. O `make e2e` no docker (build de produção) continua sendo a prova dos gates.

**`make e2e` na stack do docker (MacBook do Marcio, 08/11/2026):** 33 passaram, 32 pulados por projeto, 1 falhou: `correction.spec.ts`. O recibo do teste foi lido por completo sozinho (Docling no worker do docker, ou chave de IA no ambiente) e por isso nunca entrou na fila; o teste partia da premissa "sem IA, recibo vai para a fila". Corrigido: o teste pula com aviso quando a leitura dispensa correção (D96). Todos os fluxos do Launch passaram no docker: `launch.spec.ts`, `validation.spec.ts`, `delegation.spec.ts`. **Gates LG2, LG3 e LG4 validados.**

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
| `07-lf3-proposta-conflitos.md` | Proposta da LF3-b: conflitos de dados, Central de Validação, migração 0020 |
| `08-lf4-proposta-delegacao.md` | Proposta da LF4: pedido delegado com link de envio, migração 0021, triagem de arquivos |

## Perguntas para o Marcio — respondidas em 07/11/2026 (D89)

Q-L01 assistida pelo Admin · Q-L02 síndico envia o link/texto · Q-L03 LF2 antes da VS-06 · Q-L04 migração 0018 e alçadas opcionais aprovadas. Tabela original mantida abaixo como histórico.

| # | Pergunta | Bloqueia | Hipótese se não houver resposta |
|---|---|---|---|
| Q-L01 | Auto-cadastro do síndico ou implantação assistida (Admin CondoOS cria e convida) no piloto? | LB-009, DL-01 | Assistida no piloto; auto-cadastro P2 com verificação de autoridade |
| Q-L02 | Pedidos a terceiros: o sistema gera link e texto e o síndico envia (nada sai), ou o CondoOS envia e-mail como ação aprovada? | LF4, LB-053 | Primeiro corte manual (coerente com D83 e Plano D-04) |
| Q-L03 | Ordem: Launch LF2 antes da VS-06 (Operate controlado, aguardando decisão)? | Sequência | LF2 primeiro: não depende de piloto real e alimenta a VS-06 |
| Q-L04 | Aprovar migração 0018 (`launch_state`, ADR-L01) e a mudança de API de LB-009 (alçadas opcionais no cadastro)? | LF2 | Sem aprovação, LF2 começa pelas partes sem migração (LB-021, LB-002, LB-010, LB-006) |

## Próximo incremento recomendado

1. ~~Gates LG2, LG3 e LG4~~ **validados no docker (D96).**
2. ~~Sobras da LF4~~ **entregues e validadas no docker (D100):** pedidos no desktop da equipe, "com você × com outros" no Hoje, limite por endereço na rota pública; `make e2e` 33 passaram, nenhuma falha.
3. **LF5 (captura recorrente e canais):** provedor de e-mail de entrada real e saúde do canal; depende de escolher o provedor (custo e conta) — trazer proposta. WhatsApp segue só especificado (⛓).

## Ritual de cada incremento

1. Ler este arquivo e o item do backlog. 2. Conferir o código real. 3. Implementar só o incremento. 4. Testes, lint, E2E quando houver tela. 5. Atualizar esta tabela, `docs/roadmap-status.md`, `docs/traceability.md`, `docs/decisions.md`. 6. Commit e push na branch da sessão.
