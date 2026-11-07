# Estado do roadmap

Atualizado em 07/11/2026 (execução do prompt 01 — Planejador mestre; nenhum código alterado).

Estados: `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`. `validado` só com link a teste, PR, demo ou aceite contra a Especificação.

## 1. Situação geral

- **Marco atual:** M0 — Diagnóstico (em andamento). MVP auditor (Marcos 1–6) concluído em 05/11/2026; base reaproveitada integralmente.
- **Cobertura dos 65 FR** (`docs/02-gap-matrix.md`): 9 real, 24 parcial, 32 inexistentes. P0: 7 real, 19 parcial, 3 inexistentes.
- **Gates:** G0 aberto · G1 quase (faltam CI, SEC-10, evento de segurança) · G2 parcial · G3 bloqueado (DV-02) · G4 e G5 não iniciados.

## 2. Estado por requisito (resumo)

| Estado | FRs |
|---|---|
| validado | — |
| pronto_para_validar | 003, 004, 011, 013, 020, 043, 044, 048 |
| em_analise | 001, 002, 005, 006, 008, 012, 014, 015, 016, 017, 018, 019, 023, 024, 025, 026, 032, 033, 034, 041, 042, 045 |
| bloqueado | 031 (avaliação ao vivo: falta `ANTHROPIC_API_KEY`), 046 (decisão DV-02) |
| nao_iniciado | 007, 009, 010, 021, 022, 027, 028, 029, 030, 035, 036, 037, 038, 047, 049, 050, 051–058 |
| adiado (P2/P3) | 039, 040, 059–065 |

Detalhe e evidências: `docs/02-gap-matrix.md` e `docs/traceability.md`.

## 3. Em andamento

| Item | Estado | Evidência |
|---|---|---|
| WP-00 Inventário e ADRs | em_desenvolvimento | `docs/01-repo-audit.md`, `docs/02-gap-matrix.md`, `docs/03-decisions-register.md` |

## 4. Bloqueios

| # | Bloqueio | Bloqueia | Quem destrava |
|---|---|---|---|
| B1 | DV-01 público inicial / quem opera a fila | ADR-P02, protocolo de piloto, CB-005 | Marcio |
| B2 | DV-02 revisão interna CondoOS | FR-046, G3, VS-03 | Marcio |
| B3 | DV-03 Assunto × Achado | ADR-P01, VS-01 | Marcio |
| B4 | Sem chave de API | FR-031 (avaliação ao vivo), acurácia com LLM, R04/R07 reais | Marcio (chave em ambiente de teste) |
| B5 | Sem piloto real nem autorização de dados | G0, baseline | Marcio / pilotos |
| B6 | Testes não executados nesta sessão (contêiner sem deps/pgvector) | Confirmação de `pronto_para_validar` | CI (CB-001) |

## 5. Próxima fatia e incrementos seguintes

**Decisão:** a próxima fatia vertical é **VS-01 (primeiro tenant → primeiro assunto completo)**, porque é a primeira do caminho crítico (Plano §4.2 e §9, ciclo C2) e todo o restante (Hoje, briefing, aprovações, Operate) escreve no objeto Assunto. Antes dela, pelo gate G1, vêm dois incrementos curtos de plataforma que não mudam produto.

| Ordem | Incremento | Pacotes / histórias | Critério de conclusão | Depende de |
|---|---|---|---|---|
| 1 | **Fechar G1** | WP-01, WP-02: CB-001, CB-003, CB-004, CB-002 | CI verde rodando lint + pytest com pgvector; SEC-10 e evento de segurança automatizados; fuso por condomínio; `docs/decisions.md` com D7x | Nada (pode começar já) |
| 2 | **Política mínima e kill switch** | WP-03: CB-011, CB-010, CB-012 | Ação desconhecida → DENY com auditoria; pausa por tipo impede jobs pendentes (SEC-08); teste de PDF adversarial | Incremento 1 |
| 3 | **VS-01** | WP-04, WP-07: CB-020..025 | Aceite VS-01: outro tenant não lê; edição sem permissão negada; fechamento sem evidência bloqueado; histórico preservado; Playwright | ADR-P01 aceita (DV-03) |

**Alternativa a decidir pelo Marcio:** se o Optimize for prioridade comercial imediata (Espec. §1.5), trocar o incremento 3 por **VS-03** (CB-060, CB-061, CB-062), que depende de DV-01, DV-02 e DV-04. Em ambos os casos, os incrementos 1 e 2 vêm antes.

**Escopo excluído dos próximos incrementos:** qualquer envio externo (e-mail, WhatsApp) além do link mágico; OS, fornecedor, zelador, morador; MFA; P2/P3; dados reais.

## 6. Histórico desta página

- 07/11/2026 — criação (prompt 01). Documentos vivos criados: `01-repo-audit.md`, `02-gap-matrix.md`, `03-decisions-register.md`, `product-roadmap.md`, `backlog.md`, `traceability.md`, `pilot-protocol.md`, esta página.
