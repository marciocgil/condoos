# Estado do roadmap

Atualizado em 07/11/2026: prompt 01 e decisões DV-01..DV-05 (D73–D77). Nenhum código alterado.

Estados: `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`. `validado` só com link a teste, PR, demo ou aceite contra a Especificação.

## 1. Situação geral

- **Marco atual:** M0 — Diagnóstico (em andamento; decisões de produto tomadas, falta aprovar o plano de migração). MVP auditor (Marcos 1–6) concluído em 05/11/2026; base reaproveitada integralmente.
- **Cobertura dos 65 FR** (`docs/02-gap-matrix.md`): 9 real, 24 parcial, 32 inexistentes. P0: 7 real, 19 parcial, 3 inexistentes.
- **Gates:** G0 aberto · G1 quase (faltam CI, SEC-10, evento de segurança) · G2 parcial · G3 desbloqueado por D74, depende do EP-09 e da VS-03 · G4 e G5 não iniciados.

## 2. Estado por requisito (resumo)

| Estado | FRs |
|---|---|
| validado | — |
| pronto_para_validar | 003, 004, 011, 013, 020, 043, 044, 048 |
| em_analise | 001, 002, 005, 006, 008, 012, 014, 015, 016, 017, 018, 019, 023, 024, 025, 026, 032, 033, 034, 041, 042, 045, 046 |
| bloqueado | 031 (avaliação ao vivo: falta `ANTHROPIC_API_KEY`) |
| nao_iniciado | 007, 009, 010, 021, 022, 027, 028, 029, 030, 035, 036, 037, 038, 047, 049, 050, 051–058 |
| adiado (P2/P3) | 039, 040, 059–065 |

Detalhe e evidências: `docs/02-gap-matrix.md` e `docs/traceability.md`.

## 3. Em andamento

| Item | Estado | Evidência |
|---|---|---|
| WP-00 Inventário e ADRs | em_desenvolvimento | `docs/01-repo-audit.md`, `docs/02-gap-matrix.md`, `docs/03-decisions-register.md` |
| Modelo de dados pós-decisões (D73–D77) | em_analise — aguarda aprovação | `docs/data-model.md`, `docs/authorization-matrix.md`, `docs/flows.md` |

## 4. Bloqueios

| # | Bloqueio | Bloqueia | Quem destrava |
|---|---|---|---|
| B0 | Aprovação do plano de migração 0011–0014 (`docs/data-model.md` §7) | EP-09, VS-01, VS-03 (tudo que muda o banco) | Marcio |
| B4 | Sem chave de API | FR-031 (avaliação ao vivo), acurácia com LLM, R04/R07 reais | Marcio (chave em ambiente de teste) |
| B5 | Sem piloto real nem autorização de dados | G0, baseline | Marcio / pilotos |
| B6 | Testes não executados nesta sessão (contêiner sem deps/pgvector) | Confirmação de `pronto_para_validar` | CI (CB-001) |

## 5. Próxima fatia e incrementos seguintes

**Decisão:** a próxima fatia vertical continua sendo **VS-01 (primeiro tenant → primeiro assunto completo)**, agora com o modelo aceito em D75. Antes dela, pelo gate G1 e pelas decisões D73/D74/D77, vêm dois incrementos de plataforma.

| Ordem | Incremento | Pacotes / histórias | Critério de conclusão | Depende de |
|---|---|---|---|---|
| 1 | **Fechar G1** | WP-01, WP-02: CB-001, CB-003, CB-004, CB-002 | CI verde (lint + pytest com pgvector); SEC-10 e evento de segurança automatizados; fuso por condomínio | Nada (sem mudança de modelo além da coluna de fuso, que entra na 0011 se o plano for aprovado) |
| 2 | **Acesso e revisão proporcional** | EP-09: CB-013..017 (migrações 0011, 0012) | Critérios 0011 e 0012 de `docs/data-model.md` §8; `test_planted_cases.py` exato; reviewer opera um condomínio sem administradora de ponta a ponta no seed | B0 |
| 3 | **VS-01** | WP-04, WP-07: CB-020..027 (migração 0013) | Aceite VS-01 + critérios 0013; Playwright | Incremento 2, B0 |
| 4 | **VS-03** | CB-060..064 (migração 0014) | G3 + critérios 0014 | Incremento 2, B0 |

Política mínima e kill switch (CB-010..012) entram entre os incrementos 2 e 3 se houver automação nova com efeito; hoje o produto não envia nada para fora.

**Escopo excluído:** envio externo (e-mail, WhatsApp) além do link mágico; interfaces de zelador, fornecedor e morador (papéis só reservados); MFA; P2/P3; dados reais.

## 6. Histórico desta página

- 07/11/2026 — criação (prompt 01). Documentos vivos criados: `01-repo-audit.md`, `02-gap-matrix.md`, `03-decisions-register.md`, `product-roadmap.md`, `backlog.md`, `traceability.md`, `pilot-protocol.md`, esta página.
- 07/11/2026 — DV-01..DV-05 respondidas pelo Marcio; registradas como D73–D77. Criados `data-model.md`, `authorization-matrix.md` e `flows.md`; backlog com EP-09 e CB-013..017, CB-026/027, CB-064; FR-046 sai de bloqueado.
