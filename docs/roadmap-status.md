# Estado do roadmap

Atualizado em 07/11/2026: prompt 01, decisões DV-01..DV-05 (D73–D77), plano de migração 0011–0014 aprovado, incremento 1 (fechar G1, D78), incremento 2 (acesso e revisão proporcional, D79), VS-01 (Assunto, D80), VS-03 (Oportunidade, D81), VS-04 (Briefing e Hoje, D82) VS-05 (pedido de ação com aprovação, política mínima e kill switch, D83) e itens do backlog (D84, D85) entregues.

Estados: `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`. `validado` só com link a teste, PR, demo ou aceite contra a Especificação.

## 1. Situação geral

- **Marco atual:** M1 — Core confiável (M0 concluído em 07/11/2026: inventário, decisões D73–D77 e plano de migração aprovado). MVP auditor (Marcos 1–6) concluído em 05/11/2026; base reaproveitada integralmente.
- **Cobertura dos 65 FR** (`docs/02-gap-matrix.md`): 26 real, 14 parcial, 25 inexistentes. P0: 23 real, 6 parcial, nenhum inexistente (FR-007 entrou com a VS-05; FR-025 com D84; FR-006, 012, 015, 041 e 042 com D85).
- **Gates:** G0 aberto · **G1 fechado** (CI, SEC-10 e evento de segurança, D78; CI verde no GitHub: https://github.com/marciocgil/marcio-linkedin-skills/actions/runs/42322097954) · G2 parcial · G3 atendido no código: cálculo reproduzível e revisão interna obrigatória antes do condomínio (D81); falta validação com dados de piloto · G4: pré-requisitos no código (política que nega por padrão, aprovação com escopo congelado, outbox idempotente, kill switch, D83); nenhuma automação externa habilitada · G5 não iniciado.

## 2. Estado por requisito (resumo)

| Estado | FRs |
|---|---|
| validado | — |
| pronto_para_validar | 016 (D93, D94), 001, 003, 004, 006, 007, 011, 012, 013, 015, 020, 021, 022, 023, 024, 025, 027, 032, 034, 041, 042, 043, 044, 045, 046, 048, 050 |
| em_desenvolvimento | 058 (aprovação com escopo congelado; a contratação em si segue fora do sistema) |
| em_analise | 002, 005, 008, 014, 017, 018, 019, 026, 028, 033 |
| bloqueado | 031 (avaliação ao vivo: falta `ANTHROPIC_API_KEY`) |
| nao_iniciado | 009, 010, 029, 030, 035, 036, 037, 038, 047, 049, 051–057 |
| adiado (P2/P3) | 039, 040, 059–065 |

Detalhe e evidências: `docs/02-gap-matrix.md` e `docs/traceability.md`.

## 3. Em andamento

| Item | Estado | Evidência |
|---|---|---|
| WP-00 Inventário e ADRs | em_desenvolvimento | `docs/01-repo-audit.md`, `docs/02-gap-matrix.md`, `docs/03-decisions-register.md` |
| Modelo de dados pós-decisões (D73–D77) | 0011–0014 entregues (D79–D81); 0015 (briefing, D82), 0016 (ações e kill switch, D83) e 0017 (versões, proveniência e cláusulas, D85) aprovadas e entregues | `docs/data-model.md`, `docs/authorization-matrix.md`, `docs/flows.md` |

## 4. Bloqueios

| # | Bloqueio | Bloqueia | Quem destrava |
|---|---|---|---|
| B4 | Sem chave de API | FR-031 (avaliação ao vivo), acurácia com LLM, R04/R07 reais | Marcio (chave em ambiente de teste) |
| B5 | Sem piloto real nem autorização de dados | G0, baseline | Marcio / pilotos |

## 5. Próxima fatia e incrementos seguintes

**Decisão:** com VS-01, VS-03, VS-04 e VS-05 entregues, o caminho crítico do Plano leva à **VS-06 (Operate controlado)**, que depende do gate G4 e de dados reais de piloto (B5): **não começar sem decisão do Marcio.** Sobras pequenas, CB-063 e CB-070 entregues (D84). CB-012, CB-030, CB-031 e CB-060 entregues com a migração 0017 (D85). Resta só CB-040 (bloqueado pela chave de API). O próximo passo do Plano é a VS-06, que depende de G4 e de dados de piloto: decisão do Marcio.

| Ordem | Incremento | Pacotes / histórias | Critério de conclusão | Depende de |
|---|---|---|---|---|
| 1 | ~~Fechar G1~~ **entregue** (D78) | WP-01, WP-02: CB-001, CB-003, CB-004 | 230 testes e lint passando localmente e no CI (execução nº 1, verde) | — |
| 2 | ~~Acesso e revisão proporcional~~ **entregue** (D79) | EP-09: CB-002, CB-013..017 (migrações 0011, 0012) | 252 testes do backend (22 novos) e 18 fluxos E2E (2 novos) passando; casos plantados exatos; migração ida e volta verificada | — |
| 3 | ~~VS-01~~ **entregue** (D80) | WP-04, WP-07: CB-020..027 (migração 0013) | 263 testes do backend (11 novos), 20 fluxos E2E (2 novos), aceite VS-01 | — |
| 4 | ~~VS-03~~ **entregue** (D81) | CB-061, CB-062, CB-064 (migração 0014) | 271 testes do backend (8 novos), 21 fluxos E2E (1 novo); revisão interna antes do condomínio | — |
| 5 | ~~VS-04~~ **entregue** (D82) | CB-041, CB-042 (migração 0015) | 278 testes, 23 fluxos E2E | — |
| 6 | ~~VS-05~~ **entregue** (D83) | CB-010, CB-011, CB-050 (migração 0016) | 292 testes do backend (14 novos), 25 fluxos E2E (2 novos); SEC-04, SEC-05, WF-06, kill switch, outbox idempotente | — |

Política mínima e kill switch entregues com a VS-05 (D83); o produto continua sem enviar nada para fora.

**Escopo excluído:** envio externo (e-mail, WhatsApp) além do link mágico; interfaces de zelador, fornecedor e morador (papéis só reservados); MFA; P2/P3; dados reais.

## 6. Histórico desta página

- 07/11/2026 — criação (prompt 01). Documentos vivos criados: `01-repo-audit.md`, `02-gap-matrix.md`, `03-decisions-register.md`, `product-roadmap.md`, `backlog.md`, `traceability.md`, `pilot-protocol.md`, esta página.
- 07/11/2026 — DV-01..DV-05 respondidas pelo Marcio; registradas como D73–D77. Criados `data-model.md`, `authorization-matrix.md` e `flows.md`; backlog com EP-09 e CB-013..017, CB-026/027, CB-064; FR-046 sai de bloqueado.
- 07/11/2026 — Plano de migração 0011–0014 aprovado. Incremento 1 entregue (D78): CI, evento de segurança em 404/403, prova de revogação (SEC-10). Execução local: 230 testes, lint backend e frontend limpos. CB-002 (fuso) movido para o incremento 2 (migração 0011).
- 07/11/2026 — Primeira execução do CI no GitHub: backend e frontend verdes (run 42322097954).
- 07/11/2026 — Incremento 2 entregue (D79): papéis CondoOS Admin/Reviewer com atribuição por condomínio, acesso temporário e revogação com histórico, papéis reservados, fuso por condomínio, política de revisão versionada, "pendente de evidência", revisão interna exclusiva da equipe CondoOS. Verificação local: 252 testes, lint, migração ida e volta, 18 fluxos E2E contra a stack local. FR-001 passa a `pronto_para_validar`; FR-046 a `em_desenvolvimento`. Pendências deste incremento: tela de atribuição da equipe CondoOS e tela do síndico para a política (API pronta).
- 07/11/2026 — VS-01 entregue (D80): assunto com responsável, próxima ação e prazo, máquina de estados, tarefas, evidência, vínculos N:N com histórico, duplicidade antes de criar; telas no celular e no desktop. Verificação local: 263 testes do backend, lint, 20 fluxos E2E contra a stack local. O E2E encontrou e corrigiu um defeito de fuso na exibição de datas. FR-021..024 passam a `pronto_para_validar`.
- 07/11/2026 — VS-03 entregue (D81): oportunidade a partir de R02/R03 com economia calculada por código, revisão interna CondoOS antes do condomínio, decisão do síndico, estágios de economia lado a lado. Verificação local: 271 testes, lint, 21 fluxos E2E. FR-045 e FR-046 passam a `pronto_para_validar`. Plano de migração 0011–0014 completo.
- 07/11/2026 — VS-04 entregue (D82): briefing do dia por pessoa e condomínio, versionado, com período, fontes parciais e leitura registrada; aba "Hoje" no celular e item "Hoje" no desktop. Verificação local: 278 testes do backend, lint, 23 fluxos E2E. FR-032 passa a `pronto_para_validar`.
- 07/11/2026 — VS-05 entregue (D83): pedido de ação com escopo congelado por hash, aprovação do síndico com validade, outbox idempotente e despacho que confere tudo de novo e não envia nada (a ação espera uma pessoa executar e registrar); motor de política tipado que nega por padrão; kill switch por condomínio e tipo. Migração 0016 com ida e volta verificada. Verificação local: 292 testes do backend, lint, 25 fluxos E2E. FR-007 e FR-034 passam a `pronto_para_validar`; FR-058 a `em_desenvolvimento`.
- 07/11/2026 — Sobras do backlog (D84), sem migração: equipe CondoOS em Configurações (CB-018), "Ajustes" no celular do síndico (CB-019), filtros da fila de assuntos (CB-023), vínculo pela tela do assunto (CB-028), economia contratada e realizada (CB-063), base do piloto nas métricas (CB-070). Verificação local: 296 testes, lint, 28 fluxos E2E; o E2E achou e corrigiu a perda de filtro em mudanças rápidas. FR-025, FR-027 e FR-050 passam a `pronto_para_validar`.
- 07/11/2026 — Itens do backlog com migração (D85, migração 0017 aprovada): alçadas e parâmetros versionados (CB-012), proveniência por campo (CB-030), versão de documento (CB-031), aviso prévio, renovação e multa com o trecho e o prazo na agenda (CB-060). Verificação local: 307 testes, lint, migração ida e volta, 29 fluxos E2E. FR-006, 012, 015, 041 e 042 passam a `pronto_para_validar`; FR-016 a `em_desenvolvimento`.
- 07/11/2026 — CondoOS Launch (D88): prompt mestre salvo; Fase 0 (diagnóstico) concluída e Fase 1 (blueprint, arquitetura, prontidão por capacidade, backlog LB-xxx, testes) proposta em `docs/condoos-planning/launch/`. Nenhum código alterado; aguarda revisão do Marcio (gate LG1) e respostas Q-L01..Q-L04.
- 07/11/2026 — Launch LF2-a entregue (D89; respostas Q-L01..Q-L04): marcos LM1–LM5 calculados de fatos, prontidão C1–C3, cartão de primeiro valor do contrato, próximos passos por objetivo, `launch_state` (migração 0018 com RLS, ida e volta verificada), permissão `MANAGE_LAUNCH`, regra de conteúdo não confiável nos prompts (SEC-02). Verificação local: 322 testes do backend, lint backend e frontend, E2E `launch.spec.ts` em stack local sem Docker. Falta `make e2e` na stack do docker.
- 07/11/2026 — Launch LF2-b entregue (D90): alçada opcional no cadastro com prontidão C7, "O que já funciona" em Ajustes e Configurações, implantações em andamento na Carteira, tempo até o primeiro valor em Métricas, orientação nas bordas do envio. Verificação local: 324 testes, lint, E2E do Launch, cadastros e ajustes. Próximo: `make e2e` no docker (gate LG2) e LB-020 (migração a aprovar).
- 07/11/2026 — LB-020 entregue (D91, migração 0019 aprovada, ida e volta verificada): regimento, apólice, balancete, laudo e plano de manutenção classificados, guardados como texto e pesquisáveis. 331 testes, lint. Launch LF2 completo no código; falta o gate LG2 (`make e2e` no docker).
- 07/11/2026 — Launch LF3-a entregue (D92), sem migração: prontidão C4 (recomendações), C8 (documentos esperados), C9 (fechamento) e cobertura no relatório PDF/XLSX. 332 testes, lint. Proposta da LF3-b (conflitos de dados, Central de Validação, migração 0020) em `docs/condoos-planning/launch/07-lf3-proposta-conflitos.md`, aguardando aprovação.
- 07/11/2026 — Launch LF3-b entregue (D93, migração 0020 aprovada, ida e volta verificada): conflitos de dados com três detectores, ciclo com motivo e trilha só de inclusão, Central de Validação, política nega ações com fornecedor em conflito, prontidão e cartão marcam o campo conflitante. Verificação local: 336 testes, lint, E2E `validation.spec.ts`, `launch.spec.ts` e `actions.spec.ts` em stack local sem Docker.
- 07/11/2026 — Launch LF3 fechada no código (D94): campo "inferido" na proveniência e no cartão, envio em lote com acompanhamento, teste do gate LG3. 339 testes, lint, E2E do Launch e da Central em stack local sem Docker. Próximo: `make e2e` no docker (LG2/LG3) e proposta da LF4 aguardando aprovação.
- 07/11/2026 — Launch LF4 entregue (D95, migração 0021 aprovada, ida e volta verificada): triagem de arquivos em todo envio, pedido de documentos com link só de envio e texto pronto (nada sai do sistema), página pública sem login, atendimento automático de nota fiscal, kill switch dos links. Verificação local: 352 testes, lint, E2E `delegation.spec.ts`. Corrigida regressão de seletor em `login.spec.ts` e `condoos-staff.spec.ts` (Carteira com duas tabelas desde D90).
- 08/11/2026 — Gates LG2, LG3 e LG4 do Launch validados com `make e2e` na stack do docker (D96): 33 fluxos passaram; a única falha (`correction.spec.ts`) era premissa do teste, corrigida.
- 08/11/2026 — Medições com o modelo real (D98): R04 aprovada; acurácia 87% sem revisão (meta 90%); chat 85% e zero vazamento. Corrigidos a soma de `search_expenses` e o verificador de números de trechos; repetir `make chat-eval`.
