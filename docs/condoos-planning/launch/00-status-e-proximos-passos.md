# CondoOS Launch — estado e próximos passos

**Leia isto primeiro ao retomar o Launch.** Prompt de origem: `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md` (v1.0). Decisão de abertura: D88; respostas do Marcio e gate LG1: D89 (`docs/decisions.md`).

## Estado (07/11/2026)

| Fase | Estado | Evidência |
|---|---|---|
| LF0 Diagnóstico | ✅ concluída (gate LG0 verificado) | `01-diagnostico-as-is.md` |
| LF1 Blueprint | ✅ aprovado pelo Marcio (gate LG1, D89) | `02`–`06` deste diretório |
| LF2 Primeiro valor | **pronto_para_validar**: LF2-a..d entregues (D90–D93); gate **LG2** atendido no código e no E2E local, aguarda validação do Marcio | `05-backlog.md`, D90–D93, `web/tests/e2e/launch.spec.ts` |
| LF3 Dados e reconciliação | **pronto_para_validar**: LF3-a (D94), LF3-b (D95, migração 0020) e LF3-c (D96) entregues; gate **LG3** atendido no código e no E2E local, aguarda validação do Marcio | `05-backlog.md`, D94, ADR-L05 em `03-arquitetura-e-dados.md` |
| LF4 Colaborativo | **em_desenvolvimento**: LF4-a entregue (D97, migração 0021); gate **LG4** atendido no código e no E2E local, aguarda validação; LF4-b (painel do que está delegado, contato sem login) a fazer | `05-backlog.md`, D97 |
| LF5–LF8 | nao_iniciado | `05-backlog.md` |

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

LF2-a entregue em 07/11/2026 (D90; escolhas registradas lá, entre elas LM1 sem exigir objetivo e C1 dependente do assistente). LF2-b entregue em 07/11/2026 (D91): cartão da jornada em "Hoje", leitura do contrato e envio com retorno, com E2E do F01. LF2-c entregue em 07/11/2026 (D92): medição do Launch, prontidão em Ajustes e Configurações, implantações em andamento na Carteira e bordas do envio. LF2-d entregue em 07/11/2026 (D93): alçada opcional no cadastro, C7 e política v2, cinco tipos de documento (migração 0019). Próximo: validar o LG2 e decidir entre **LF3** (precisa aprovar a migração `data_issue`, ADR-L05) e a VS-06.

| Incremento | Itens | Migração | Aceite principal |
|---|---|---|---|
| ~~LF2-a — fundação da jornada~~ **entregue (D90)** | LB-021 (teste SEC-02, PDF com instrução maliciosa), LB-001 (`launch_state`, rotas de objetivo e "fazer depois"), LB-002 (marcos LM1–LM5 derivados), LB-010 (prontidão C1–C3), LB-003 (próximo passo), LB-004 (`GET /condominiums/{id}/launch`) | 0018 (aprovada) | Positivo e negativo por marco e capacidade; seed Acácias com LM1–LM3, condomínio novo só LM1; conselheiro 403 na escrita, outro condomínio 404 + evento; migração ida e volta; `make lint` e `make test` verdes |
| ~~LF2-b — primeiro valor na tela~~ **entregue (D91)** | LB-006 (cartão de primeiro valor), LB-007 (upload com retorno), LB-005 (cartão da jornada em "Hoje"), LB-008 ("o que o CondoOS já fez") | — | Nenhum número fora de `extracted`; campo < 0,9 rotulado "a confirmar"; 390 px; E2E do F01 com contrato do corpus |
| ~~LF2-c — medição e visão da equipe~~ **entregue (D92)** | LB-090 (eventos `launch.*` e métricas), LB-011 (prontidão em Ajustes e Configurações), LB-012 (implantações na Carteira), LB-022 (bordas do upload) | — | Tempo até primeiro valor medido; mensagens de borda em PT-BR sem documento fantasma |
| ~~LF2-d — cadastro assistido e tipos~~ **entregue (D93)** | LB-009 (alçadas opcionais, D89), LB-020 (tipos documentais) | LB-020: **pedir aprovação** | Condomínio sem alçada: política nega pedido de ação com motivo; gate **LG2** (E2E completo do síndico novo) |

**Gate LG2 (critérios do `05-backlog.md`) × evidência:** síndico novo de condomínio criado pelo Admin escolhe "Economizar", envia o contrato do corpus e vê a leitura com trechos e limites e o próximo passo (`launch.spec.ts`); campo incerto sempre rotulado (`test_first_value_never_shows_a_doubtful_field_as_fact`); isolamento (`test_other_condominium_is_404_and_recorded`, `test_launch_state_is_isolated_by_rls`, 404 do primeiro valor de outro condomínio); nenhum cadastro monolítico (alçada opcional, D93). Pendente: validação humana do Marcio e leitura com a IA real (B4: sem chave, o contrato do corpus sai parcial).

**LF3 — dados e reconciliação.** LF3-a entregue em 07/11/2026 (D94): cobertura por mês sem nunca dizer "completo" no relatório, no briefing e nas pendências (LB-037), reconciliação nos dois sentidos (LB-031) e prontidão C4, C8 e C9 (LB-034). **LF3-b** depende da migração 0020 (`data_issue`, desenho em ADR-L05): LB-030 (conflito contrato × aditivo com versão prevalente), LB-035 (política nega ação sobre contrato com conflito aberto) e LB-036 (classes "inferido" e "conflitante" na proveniência). Ficam para LF3-c: LB-032 (Central de Validação) e LB-033 (envio em lote). LF3-b entregue em 07/11/2026 (D95). LF3-c entregue em 07/11/2026 (D96): a fila de exceções virou a Central de Validação (conflitos de dados incluídos, cada item com o valor envolvido, do maior para o menor) e o envio em lote acompanha cada arquivo.

**Gate LG3 (critérios do `05-backlog.md`) × evidência:** documentos **contraditórios** (`test_data_issues.py`, e2e `data-issues.spec.ts`); **ausentes** (C8 e cobertura: `test_launch.py::test_expected_documents_capability`, `::test_reconciliation_in_both_directions`); **duplicados** (mesmo arquivo pelo hash: `test_launch.py::test_upload_edges_leave_no_phantom_document`; mesma nota paga duas vezes: R01 com caso plantado); **ilegíveis** (`nao_identificado` no cartão, "para revisão" no envio em lote: `test_upload_edges_leave_no_phantom_document`, `test_validation_center.py::test_batch_upload_follow_up`); **nenhum relatório parcial descrito como completo** (`test_launch.py::test_coverage_label_never_says_complete`, `::test_report_says_its_coverage`, `test_briefing.py::test_stale_data_is_reported`). Pendente: validação do Marcio; o tipo `duplicidade_suspeita` da `data_issue` ainda não é detectado (a R01 cobre o caso de pagamento).

**LF4 — colaborativo.** LF4-a entregue em 07/11/2026 (D97, migração 0021 e ADR-L06 aprovadas): pedido de documentos com link só de envio, autorizado pelo síndico, texto pronto (nada sai do sistema), estados separados, triagem por formato e limites, e tudo o que chega passa por uma pessoa. **Gate LG4 × evidência:** síndico e administradora simulados (`test_delegation.py::test_sindica_delegates_and_the_administradora_sends`, e2e `delegation.spec.ts`); revogação imediata (`::test_revocation_is_immediate_and_a_new_link_replaces_the_old`, e2e); link de A não grava em B (`::test_a_link_of_a_never_writes_in_b`). Pendente: validação do Marcio.

**Próximo: LF4-b** — LB-044 (painel "o que você decide × o que está delegado": decisões, aprovações e pedidos abertos num só lugar) e LB-046 (contato sem login de fornecedor ou zelador, mínimo: nome, papel e telefone/e-mail para reaproveitar em pedidos). LB-046 guarda dado pessoal novo: pedir aprovação do modelo antes.

## Ritual de cada incremento

1. Ler este arquivo e o item do backlog. 2. Conferir o código real. 3. Implementar só o incremento. 4. Testes, lint, E2E quando houver tela. 5. Atualizar esta tabela, `docs/roadmap-status.md`, `docs/traceability.md`, `docs/decisions.md`. 6. Commit e push na branch da sessão.
