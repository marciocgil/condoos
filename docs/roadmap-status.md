# Estado do roadmap

Atualizado em 07/11/2026: prompt 01, decisões DV-01..DV-05 (D73–D77), plano de migração 0011–0014 aprovado, incremento 1 (fechar G1, D78), incremento 2 (acesso e revisão proporcional, D79), VS-01 (Assunto, D80), VS-03 (Oportunidade, D81), VS-04 (Briefing e Hoje, D82) VS-05 (pedido de ação com aprovação, política mínima e kill switch, D83) e itens do backlog (D84, D85) entregues.

Estados: `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`. `validado` só com link a teste, PR, demo ou aceite contra a Especificação.

## 1. Situação geral

- **Marco atual:** M1 — Core confiável (M0 concluído em 07/11/2026: inventário, decisões D73–D77 e plano de migração aprovado). MVP auditor (Marcos 1–6) concluído em 05/11/2026; base reaproveitada integralmente.
- **Cobertura dos 65 FR** (`docs/02-gap-matrix.md`): 26 real, 14 parcial, 25 inexistentes. P0: 23 real, 6 parcial, nenhum inexistente (FR-007 entrou com a VS-05; FR-025 com D84; FR-006, 012, 015, 041 e 042 com D85).
- **Gates:** G0 aberto · **G1 fechado** (CI, SEC-10 e evento de segurança, D78; CI verde no GitHub: https://github.com/marciocgil/marcio-linkedin-skills/actions/runs/42322097954) · G2 parcial · G3 atendido no código: cálculo reproduzível e revisão interna obrigatória antes do condomínio (D81); falta validação com dados de piloto · G4: pré-requisitos no código (política que nega por padrão, aprovação com escopo congelado, outbox idempotente, kill switch, D83); nenhuma automação externa habilitada · G5 não iniciado.

## 1a. Prontidão para o piloto (revisão de 09/11/2026)

Pré-condições do gate G0 (`docs/pilot-protocol.md` §1):

| # | Pré-condição | Estado |
|---|---|---|
| 1 | DV-01 e DV-02 respondidas | ✅ D73, D74 |
| 2 | Termo do piloto e base legal | ⏳ minuta pronta (D107); revisão jurídica e assinatura da síndica |
| 3 | Revisão do Agent SDK (D54) e do processamento pela IA | ✅ exceção aceita (D107); transferência internacional no termo |
| 4 | Chave de API e medições (acurácia, chat) | ✅ D98: chat 97% e zero vazamento; acurácia 87% (meta 90% conferida no piloto) |
| 5 | CI ativo e G1 fechado | ✅ CI verde a cada push |
| 6 | Ambiente de piloto separado, backup e restauração testados | ✅ D106 (Hostinger, backup diário cifrado, restauração testada) |

Antes do primeiro documento real: teste de fumaça em produção (leitura com Docling e IA, chat, e-mail de entrada) com dados fictícios e restauração do backup depois; monitor externo de `/health`; Marcio fora da leitura da entrada de e-mail do docker local (um só leitor por bucket). O piloto começa em **shadow mode (V2)**: competências passadas, sem contato externo.

Planejado e não construído, nenhum item bloqueia o V2: LF6 (saúde contínua, LB-060..065), LF7 (instrumentos do piloto, LB-070..073), VS-06 (Operate controlado; depende de G4 e de dados reais), P0 parciais fechados em 12/11/2026 (D126) e P1 sem início (FR-009, 010, 029, 030, 035–038, 047, 049, 051–056; FR-057 entregue em primeiro corte, D112). P2/P3 adiados.

## 2. Estado por requisito (resumo)

| Estado | FRs |
|---|---|
| validado | — |
| pronto_para_validar | 002, 005, 014, 026, 033 (D126), 057 (D112, primeiro corte), 016 (D93, D94), 001, 003, 004, 006, 007, 011, 012, 013, 015, 020, 021, 022, 023, 024, 025, 027, 032, 034, 041, 042, 043, 044, 045, 046, 048, 050 |
| em_desenvolvimento | 058 (aprovação com escopo congelado; a contratação em si segue fora do sistema) |
| em_analise | 008, 017, 018, 019, 028 |
| bloqueado | — (031 medido ao vivo em 08/11/2026: 97%, zero vazamento, D98; passa a pronto_para_validar) |
| nao_iniciado | 009, 010, 029, 030, 035, 036, 037, 038, 047, 049, 051–056 |
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
| ~~B4~~ | ~~Sem chave de API~~ resolvido em 08/11/2026 (D98) | — | — |
| B5 | Sem autorização de dados do piloto | G0, baseline, LF7, VS-06 | Termo do piloto assinado pela síndica (D107) |

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

**Escopo excluído:** envio externo além do link mágico e do e-mail do pedido de documentos aprovado pelo síndico (D103); WhatsApp; interfaces de zelador, fornecedor e morador (papéis só reservados); MFA; P2/P3; dados reais.

## 6. Histórico desta página

- 12/11/2026 — Síndico guiado, fatia 3 (D129, sem migração): o síndico encerra a própria saída de um condomínio (hoje, até 90 dias ou no fim do mandato, com desfazer até a data); acesso termina, aprovações voltam, automações pausam sem síndico ativo, nada é apagado; dossiê do período em PDF. As três fatias do síndico guiado estão entregues.
- 12/11/2026 — Síndico guiado, fatia 2 (D128, migração 0033): o síndico implanta um condomínio por conversa (CNPJ na Receita, dados, mandato, termo de adesão), acompanha o percentual dos 8 itens até "apto a operar" e resolve mandato, termo e alçada no lugar. Próxima: encerrar (fatia 3).
- 12/11/2026 — Síndico guiado, fatia 1 (D127, sem migração): entrada "O que vamos fazer hoje?" para quem tem vários condomínios, entrada direta no dia a dia para quem tem um, tela do dia a dia com envio único, o que já chegou, farol e pontos de atenção. Próximas: implantar e continuar (fatia 2, com migração a aprovar) e encerrar (fatia 3).
- 12/11/2026 — P0 parciais fechados (D126, migração 0032): convite que vence em 14 dias (FR-002), antes/depois, motivo e versão nas mudanças críticas (FR-005), relações de documento, contrato e fornecedor (FR-014), alertas de prazo dentro do app com estado (FR-026) e próxima ação do achado com estado de autorização (FR-033). Todos os 29 P0 cobertos no código. Verificação: 496 testes do backend, lint, e2e (47 passaram; o de correção da fila segue falhando só neste ambiente).
- 12/11/2026 — CondoOS Audit, ciclo 4 (D125, sem migração): reprocessamento por evento só de meses já auditados (pausável), SLA e escalonamento das pendências e do envio ao síndico, histórico e tendência do farol, PDF e planilha (interno e aprovado), ligações com Assuntos e Oportunidades, testes de custo, desempenho e rollback de prompt. Verificação: 490 testes do backend, lint e tipos, tela na stack local. Os quatro ciclos do Prompt Mestre estão concluídos.
- 11/11/2026 — CondoOS Audit, ciclo 3 (D124, migração 0031): os 25 controles avaliados; contratos (preço com aditivo e reajuste, serviço extraordinário com autorização e aceite, parcelas), fundos e lastro, aplicações, orçado × realizado com projeção, seguros e laudos pela Conformidade, aprovação formal das contas, revalidação histórica e o farol aprovado pelo síndico (aba Auditoria). Verificação: 480 testes do backend, lint e tipos, migração ida e volta. Próximo: ciclo 4 (operação contínua).
- 11/11/2026 — CondoOS Audit, ciclo 2 (D123, migração 0030): 17 dos 25 controles avaliados; unidades, títulos e leituras sem nomes (só equipe interna), perfil de auditoria, alocação N:N de pagamentos, tributos retidos e periódicos, parcelamento, pendências persistentes e memória de cálculo. Verificação: 464 testes do backend, lint, migração ida e volta, telas na stack local. Próximo: ciclo 3 (contratos, fundos, orçamento, aprovação formal).

- 11/11/2026 — CondoOS Audit, ciclo 1 (D122, migração 0029): farol de 25 controles (9 avaliados por regra, 16 "não avaliado" com o ciclo previsto), conciliação por conta com saldos do extrato, agentes A0–A9 com prompts versionados e governança, "Como este resultado foi produzido?". Verificação: 448 testes do backend, lint, migração ida e volta, telas na stack local. Falta `make e2e` no docker. Próximo: ciclo 2 (decisão sobre dados por unidade antes).

- 10/11/2026 — Tela "Regras e prompts" para a equipe CondoOS (D121, migração 0028 aprovada): regras de auditoria, prompts por propósito com texto, versão, custo e histórico de versões, regras de leitura, verificações automáticas e política das ações, só leitura. Verificação: 430 testes do backend, lint, migração ida e volta e a tela conferida na stack local. Falta `make e2e` no docker.

- 10/11/2026 — Correções na leitura (D120, migração 0027 aprovada): confiança por evidência (valor escrito no texto, razão social da Receita, CNPJ do condomínio), CNPJ procurado no texto, tela de correção com pendentes e opcionais separados, cópia da mesma nota sem despesa nova, alertas de contrato (assinatura depois do início, contratante que não é o condomínio, CNPJ do condomínio errado, sem CNPJ da contratada), contrato sem CNPJ pela razão social com assunto "Ajustar contrato" quando essencial ou acima da alçada, contrato pontual, comprovante de pagamento, guia de tributo, relatório da administradora, extrato de rendimento e recusa da relação de devedores. Verificação: 425 testes do backend, lint e tipos. Falta `make e2e` no docker e refazer as gravações da IA (`LLM_MODE=record make accuracy`).

- 09/11/2026 — FR-057, segundo corte (D113, migração 0026 aprovada): perfil do prédio que só sugere, dossiê em PDF por obrigação e resumo semanal por e-mail ao síndico (segundo envio do sistema, aprovado pelo Marcio). Verificação local: 381 testes do backend, lint, migração ida e volta, E2E `compliance.spec.ts` e `launch.spec.ts`.

- 09/11/2026 — FR-057 conformidade e vencimentos, primeiro corte (D112, migração 0025 aprovada): obrigações com aplicabilidade decidida por pessoa, catálogo de 14 candidatas, documento e validade com leitura pela IA confirmada por pessoa, situação calculada, avisos na Agenda, no Hoje e no chat. Verificação local: 378 testes do backend, lint, migração ida e volta, E2E `compliance.spec.ts` e os fluxos de agenda, pedidos, assuntos e Hoje.

- 09/11/2026 — Roteiro do teste de ponta a ponta (`docs/pilot/teste-ponta-a-ponta.md`), ensaiado na stack local. O ensaio revelou o resumo do dia desatualizado depois da chegada de documentos; corrigido (D111). Verificação: 389 testes do backend e lint.
- 09/11/2026 — LF6-b entregue (D110, migração 0024 aprovada): monitores diários com alertas internos em `data_issue` (audiência equipe ou condomínio), Central de Validação com "Alertas de saúde", coluna na Carteira, Centro de Evolução em Ajustes e Configurações. Alertas nunca mudam permissão. Verificação local: 388 testes do backend, lint, migração ida e volta, E2E 37 passaram e 1 falhou (`correction.spec.ts`, a mesma falha da stack local). Falta `make e2e` no docker. LF6 completa (D109, D110); a próxima fase do Launch, a LF7, depende do piloto real autorizado (B5).
- 09/11/2026 — LF6-a entregue (D109), sem migração: troca de síndico (aprovações de quem saiu voltam para aprovação; despacho confere quem aprovou; C7 espera o síndico ativo), histórico das capacidades no `audit_log` com verificação diária e no primeiro acesso, rollback testado. Verificação local: 381 testes do backend, lint, E2E 37 passaram e 1 falhou (`correction.spec.ts`, a mesma falha da stack local). FR-007 e FR-034 seguem `pronto_para_validar`, agora com a revalidação na troca de síndico. Falta `make e2e` no docker.
- 09/11/2026 — Experiência do síndico no piloto entregue (D108, LB-080..LB-086), sem migração: guia em passos com progresso calculado dos dados, documentos em conferência visíveis, "Seu mês" no Hoje depois do LM3, Hoje sem mensagens que se contradizem, severidade em texto, "Pergunte" só quando o chat responde e próximo ponto de atenção depois de decidir. Verificação local (stack sem Docker: PostgreSQL local, API e worker num processo, armazenamento em memória, substituto do Mailpit, build de produção do web): 378 testes do backend, lint backend e frontend, E2E 36 passaram e 1 falhou (`correction.spec.ts`, tela da gerente não alterada: o salvar não chega à API na leitura local sem Docling, a mesma falha já registrada para esta stack). FR-032 e FR-033 seguem `pronto_para_validar`, agora com a próxima ação do síndico. Capturas antes e depois em `docs/screens/piloto-d108/`. Falta `make e2e` no docker.
- 09/11/2026 — Revisão de prontidão para o piloto (seção 1a): G0 com 5 de 6 pré-condições atendidas (falta o termo assinado); B4 resolvido; FR-031 medido; produção no ar (D106); rotação dos logs dos contêineres em produção.

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
- 08/11/2026 — LB-053 (D103, migração 0023 aprovada): o CondoOS envia o e-mail do pedido de documentos depois da aprovação do síndico da versão exata; link novo no envio, "aceito pelo servidor" (nunca "entregue"), endereço mascarado depois, limites, pausa e 3 tentativas. Verificação local: 370 testes, lint, E2E `delegation.spec.ts`.
- 08/11/2026 — LF5 (D102): documento esperado conferido em todos os canais antes de virar "não recebida" ("chegou, em conferência" em C8, Agenda, Pendências e relatório) e cobertura das notas do mês na Agenda. Verificação local: 366 testes, lint, E2E `agenda.spec.ts`.
- 08/11/2026 — LF5 (D101, migração 0022 aprovada): e-mail de entrada pelo Amazon SES em São Paulo gravando no S3 (bucket simulado até haver domínio), endereço com parte aleatória e troca pelo síndico, registro mínimo de cada e-mail e saúde do canal em Ajustes e Configurações, pausa do e-mail no kill switch. `make e2e` no docker: 34 passaram, nenhuma falha.
- 08/11/2026 — Sobras da LF4 (D100): limite por endereço nas rotas públicas do link, pedidos no desktop da equipe e "com você × com outros" no Hoje. Verificação local: 358 testes, lint, E2E `delegation.spec.ts` (celular e desktop); `make e2e` no docker: 33 passaram, nenhuma falha.
- 07/11/2026 — Launch LF4 entregue (D95, migração 0021 aprovada, ida e volta verificada): triagem de arquivos em todo envio, pedido de documentos com link só de envio e texto pronto (nada sai do sistema), página pública sem login, atendimento automático de nota fiscal, kill switch dos links. Verificação local: 352 testes, lint, E2E `delegation.spec.ts`. Corrigida regressão de seletor em `login.spec.ts` e `condoos-staff.spec.ts` (Carteira com duas tabelas desde D90).
- 08/11/2026 — Gates LG2, LG3 e LG4 do Launch validados com `make e2e` na stack do docker (D96): 33 fluxos passaram; a única falha (`correction.spec.ts`) era premissa do teste, corrigida.
- 08/11/2026 — Medições com o modelo real (D98): R04 aprovada; acurácia 87% sem revisão (meta 90%); chat 85% e zero vazamento. Corrigidos a soma de `search_expenses` e o verificador de números de trechos; na segunda rodada o chat chegou a 97% (aprovado) e o `objeto` divergente era só redação (0 automático divergente).
