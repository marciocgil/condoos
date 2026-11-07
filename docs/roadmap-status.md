# Estado do roadmap

Atualizado em 07/11/2026: prompt 01, decisões DV-01..DV-05 (D73–D77), plano de migração 0011–0014 aprovado, incremento 1 (fechar G1, D78), incremento 2 (acesso e revisão proporcional, D79) e VS-01 (Assunto, D80) entregues.

Estados: `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`. `validado` só com link a teste, PR, demo ou aceite contra a Especificação.

## 1. Situação geral

- **Marco atual:** M1 — Core confiável (M0 concluído em 07/11/2026: inventário, decisões D73–D77 e plano de migração aprovado). MVP auditor (Marcos 1–6) concluído em 05/11/2026; base reaproveitada integralmente.
- **Cobertura dos 65 FR** (`docs/02-gap-matrix.md`): 14 real, 23 parcial, 28 inexistentes. P0: 12 real, 16 parcial, 1 inexistente (FR-007).
- **Gates:** G0 aberto · **G1 fechado** (CI, SEC-10 e evento de segurança, D78; CI verde no GitHub: https://github.com/marciocgil/marcio-linkedin-skills/actions/runs/42322097954) · G2 parcial · G3: política de revisão e revisora CondoOS prontas (D79); falta a VS-03 (oportunidades) · G4 e G5 não iniciados.

## 2. Estado por requisito (resumo)

| Estado | FRs |
|---|---|
| validado | — |
| pronto_para_validar | 001, 003, 004, 011, 013, 020, 021, 022, 023, 024, 043, 044, 048 |
| em_desenvolvimento | 025 (fila por pessoa e alertas prontos; faltam filtros de categoria e criticidade na tela), 027 (Assunto 360° com vínculos clicáveis; falta vincular pela tela), 046 (política de revisão e revisão interna prontas; falta a oportunidade, VS-03) |
| em_analise | 002, 005, 006, 008, 012, 014, 015, 016, 017, 018, 019, 026, 028, 032, 033, 034, 041, 042, 045 |
| bloqueado | 031 (avaliação ao vivo: falta `ANTHROPIC_API_KEY`) |
| nao_iniciado | 007, 009, 010, 029, 030, 035, 036, 037, 038, 047, 049, 050, 051–058 |
| adiado (P2/P3) | 039, 040, 059–065 |

Detalhe e evidências: `docs/02-gap-matrix.md` e `docs/traceability.md`.

## 3. Em andamento

| Item | Estado | Evidência |
|---|---|---|
| WP-00 Inventário e ADRs | em_desenvolvimento | `docs/01-repo-audit.md`, `docs/02-gap-matrix.md`, `docs/03-decisions-register.md` |
| Modelo de dados pós-decisões (D73–D77) | 0011, 0012 (D79) e 0013 (D80) entregues; 0014 na VS-03 | `docs/data-model.md`, `docs/authorization-matrix.md`, `docs/flows.md` |

## 4. Bloqueios

| # | Bloqueio | Bloqueia | Quem destrava |
|---|---|---|---|
| B4 | Sem chave de API | FR-031 (avaliação ao vivo), acurácia com LLM, R04/R07 reais | Marcio (chave em ambiente de teste) |
| B5 | Sem piloto real nem autorização de dados | G0, baseline | Marcio / pilotos |

## 5. Próxima fatia e incrementos seguintes

**Decisão:** com a VS-01 entregue, a próxima fatia é a **VS-03 (contrato + fatura → oportunidade com revisão interna)**: o Optimize é o produto de entrada (Espec. §1.5), as bases (acesso, política de revisão, assunto) estão prontas, e a oportunidade pode virar assunto. As sobras CB-018, CB-019, CB-023 e CB-028 são pequenas e podem entrar junto ou antes, se o Marcio preferir.

| Ordem | Incremento | Pacotes / histórias | Critério de conclusão | Depende de |
|---|---|---|---|---|
| 1 | ~~Fechar G1~~ **entregue** (D78) | WP-01, WP-02: CB-001, CB-003, CB-004 | 230 testes e lint passando localmente e no CI (execução nº 1, verde) | — |
| 2 | ~~Acesso e revisão proporcional~~ **entregue** (D79) | EP-09: CB-002, CB-013..017 (migrações 0011, 0012) | 252 testes do backend (22 novos) e 18 fluxos E2E (2 novos) passando; casos plantados exatos; migração ida e volta verificada | — |
| 3 | ~~VS-01~~ **entregue** (D80) | WP-04, WP-07: CB-020..027 (migração 0013) | 263 testes do backend (11 novos), 20 fluxos E2E (2 novos), aceite VS-01 | — |
| 4 | **VS-03** ← próximo | CB-060..064 (migração 0014) | G3 + critérios 0014 | — |

Política mínima e kill switch (CB-010..012) entram entre os incrementos 2 e 3 se houver automação nova com efeito; hoje o produto não envia nada para fora.

**Escopo excluído:** envio externo (e-mail, WhatsApp) além do link mágico; interfaces de zelador, fornecedor e morador (papéis só reservados); MFA; P2/P3; dados reais.

## 6. Histórico desta página

- 07/11/2026 — criação (prompt 01). Documentos vivos criados: `01-repo-audit.md`, `02-gap-matrix.md`, `03-decisions-register.md`, `product-roadmap.md`, `backlog.md`, `traceability.md`, `pilot-protocol.md`, esta página.
- 07/11/2026 — DV-01..DV-05 respondidas pelo Marcio; registradas como D73–D77. Criados `data-model.md`, `authorization-matrix.md` e `flows.md`; backlog com EP-09 e CB-013..017, CB-026/027, CB-064; FR-046 sai de bloqueado.
- 07/11/2026 — Plano de migração 0011–0014 aprovado. Incremento 1 entregue (D78): CI, evento de segurança em 404/403, prova de revogação (SEC-10). Execução local: 230 testes, lint backend e frontend limpos. CB-002 (fuso) movido para o incremento 2 (migração 0011).
- 07/11/2026 — Primeira execução do CI no GitHub: backend e frontend verdes (run 42322097954).
- 07/11/2026 — Incremento 2 entregue (D79): papéis CondoOS Admin/Reviewer com atribuição por condomínio, acesso temporário e revogação com histórico, papéis reservados, fuso por condomínio, política de revisão versionada, "pendente de evidência", revisão interna exclusiva da equipe CondoOS. Verificação local: 252 testes, lint, migração ida e volta, 18 fluxos E2E contra a stack local. FR-001 passa a `pronto_para_validar`; FR-046 a `em_desenvolvimento`. Pendências deste incremento: tela de atribuição da equipe CondoOS e tela do síndico para a política (API pronta).
- 07/11/2026 — VS-01 entregue (D80): assunto com responsável, próxima ação e prazo, máquina de estados, tarefas, evidência, vínculos N:N com histórico, duplicidade antes de criar; telas no celular e no desktop. Verificação local: 263 testes do backend, lint, 20 fluxos E2E contra a stack local. O E2E encontrou e corrigiu um defeito de fuso na exibição de datas. FR-021..024 passam a `pronto_para_validar`.
