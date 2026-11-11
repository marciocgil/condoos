# Roadmap do produto — marcos, gates, dependências e trilhos

Data: 07/11/2026. Base: Plano Diretor v1.0 §1.2, §4, §9 e o estado real (`docs/01-repo-audit.md`, `docs/02-gap-matrix.md`). Sequência lógica, **não** prazo. Nenhuma data de entrega é prometida.

> **Aviso (11/11/2026, D92):** o Marcio definiu que a dor central é o controle da despesa. Os marcos de operação (M4 e boa parte de M5) deixaram de ser o caminho previsto, e a sequência a partir do ciclo C7 tem uma proposta de substituição em `docs/reconcepcao/fase-6-mvp-roadmap-validacao.md`, ainda não aprovada. Até a aprovação, este arquivo fica como estava.

"Marco 1–6" são os marcos do MVP auditor (concluídos). Os marcos deste roadmap são **M0–M5**.

## 1. Ponto de partida

O MVP auditor antecipou boa parte de trilhos que o Plano previa para depois: documentos e extração (C3), parsers de contrato e fatura (C6) e comparação determinística (C7, sem a revisão interna). Em compensação, faltam peças que o Plano põe **antes**: CI (WP-01), políticas e kill switch (WP-03) e o núcleo de Assunto/Tarefa (WP-04/07). O roadmap reordena só o necessário para fechar essas bases sem refazer o que existe.

## 2. Marcos

| Marco | Objetivo | Estado | O que falta para o gate |
|---|---|---|---|
| **M0 — Diagnóstico** | Inventário, decisões, baseline | **Em andamento** | DV-01..05 respondidas (D73–D77); falta aprovar o plano de migração e dados/acesso de piloto (G0) |
| **M1 — Core confiável** | Tenant, RBAC, assuntos, tarefas, timeline, documentos, auditoria | Parcial: tenant/RBAC/RLS/documentos/auditoria reais | CI; fuso; convite; evento de segurança; prova SEC-10; política + kill switch; Assunto/Tarefa (VS-01) |
| **M2 — Advisor** | Busca fundamentada, briefing, recomendações, Hoje | Parcial: busca e chat reais | Avaliação ao vivo do chat; briefing (VS-04); tela Hoje; proveniência por campo |
| **M3 — Optimize** | Contratos, faturas, comparação, oportunidades, revisão interna | Parcial forte: contratos, faturas, R02/R03/R04 | Oportunidade e estágios de economia (D76); política de revisão e reviewer (D74, D77); cláusulas de aviso prévio; VS-03 completo |
| **M4 — Operate supervisionado** | OS, manutenção, fornecedores, notificações, aprovações | Não iniciado | Depende de G4 (política, outbox, kill switch) |
| **M5 — Expansão** | Procurement, governança, obras, integrações | Não iniciado | Depende de G5 |

## 3. Gates (Plano §9.1) — situação

| Gate | Critério | Situação | Evidência / bloqueio |
|---|---|---|---|
| G0 Discovery | Piloto, direitos de uso, fluxo real, baseline | **Aberto** | Sem piloto real nem baseline; dados reais só com autorização (CLAUDE.md) |
| G1 Plataforma segura | Isolamento, papéis, auditoria, revogação | **Quase**: isolamento e papéis com testes; faltam CI, teste de revogação (SEC-10) e evento de segurança | `test_isolation.py`, `test_rbac.py`, `test_auth.py` |
| G2 Informação confiável | Versões, origem, citação, incerteza | Parcial: citação e incerteza no chat e na extração; faltam página/trecho por campo e cadeia de versões | D25, D55, `test_extraction.py` |
| G3 Valor Optimize | Cálculo conferível; revisão interna obrigatória | Desbloqueado por D74; depende de CB-015/016/061/062 | R02/R03 reproduzíveis (`test_rules.py`) |
| G4 Execução segura | Política e aprovação no backend, idempotência, kill switch | Não iniciado (e hoje não há execução externa) | — |
| G5 Piloto replicável | Onboarding repetível, suporte, ROI | Parcial: onboarding fictício em 112 s | `docs/pilot/run.md` |

Falhar um gate interrompe a ampliação de autonomia ou de escopo relacionado.

## 4. Mapa de dependências dos pacotes (WP-00..24)

Estado: ✅ coberto (com lacunas menores) · ◐ parcial · ○ não iniciado.

```
WP-00 Inventário/ADRs ◐ ──► WP-01 CI/ambientes ○ ──► WP-02 Tenant/RBAC ◐ ──┬─► WP-03 Auditoria/política/kill switch ◐
                                                                           └─► WP-04 Domínios (Assunto) ○
WP-03 + WP-04 ──► WP-05 Documentos/versões ◐ ──► WP-06 Busca com fonte ✅ ──┐
WP-03 + WP-04 ──► WP-07 Casos/tarefas/prazos ○ ─────────────────────────────┴─► WP-08 Hoje/dossiê ○ ──► WP-09 Briefing ○
WP-03 + WP-07 ──► WP-10 Aprovações com escopo congelado ○
WP-05 ──► WP-11 Contratos ◐ ─┐
WP-05 ──► WP-12 Faturas ✅ ──┴─► WP-13 Comparador ✅/◐ ──► (WP-10) ──► WP-14 Revisão Optimize ◐ ──► WP-15 ROI ○
WP-05/07 ──► WP-16 Conformidade ○        WP-07/10 ──► WP-17 Ativos/OS ○ ──► WP-18 Zelador/fornecedor ○
WP-07/03 ──► WP-19 Notificações ○ ──► WP-20 WhatsApp ○      WP-11/10/18 ──► WP-21 RFQ ○
WP-12 ──► WP-22 Financeiro ampliado ○     WP-07/10 ──► WP-23 Governança (P2) ○     WP-24 (P3) ○
```

**Caminho crítico** (Plano §4.2, ajustado ao código): WP-00 → **WP-01** → fechar **WP-02** → **WP-03** (política mínima + kill switch) → **WP-04/07** (Assunto, VS-01) → WP-08 (Hoje) → WP-09 (briefing, VS-04).

**Trilho paralelo do Optimize** (após WP-03 e o modelo de acesso/revisão, EP-09): WP-11 (aviso prévio, cláusulas) → WP-13 (Oportunidade) → WP-14 (revisão interna) → VS-03 → WP-15.

**Paralelizáveis sem conflito:** ADR-P04 (proveniência por campo, WP-05) com WP-04/07; avaliação ao vivo do chat (só precisa de chave); WP-11 cláusulas novas com WP-07.

**Só depois de G4:** WP-17..21 (qualquer efeito externo).

## 5. Ciclos propostos (recalibrados ao código)

| Ciclo | Conteúdo | Pacotes | Critério de passagem |
|---|---|---|---|
| C0 | Diagnóstico + decisões | WP-00 | Docs vivos criados; DV-01..05 respondidas (D73–D77); plano de migração aprovado |
| C1 | **Fechar G1**: CI, fuso, evento de segurança, revogação provada | WP-01, WP-02 | CI verde com isolamento; SEC-01/SEC-10 automatizados |
| C2 | Modelo de acesso e revisão proporcional (migrações 0011–0012) | WP-02, WP-03 | Critérios de `docs/data-model.md` §8 (0011, 0012) |
| C2b | Política mínima e kill switch | WP-03 | SEC-08 (kill switch) e "nega por padrão" testados |
| C3 | **VS-01** Assunto completo (migração 0013) | WP-04, WP-07 | Aceite VS-01 + critérios 0013 |
| C4 | Proveniência por campo + tela Hoje | WP-05, WP-08 | G2 |
| C5 | **VS-04** briefing + **VS-05** aprovação (sem envio externo) | WP-09, WP-10 | Briefing sem afirmação inventada; escopo congelado |
| C6 | **VS-03** Oportunidade, estágios de economia e revisão interna (migração 0014) | WP-11, WP-13, WP-14 | G3 + critérios 0014 |
| C7 | Piloto Core/Optimize (shadow mode) | WP-15, qualidade | Go/No-go por módulo |
| C8+ | Operate (OS, fornecedor, notificações), WhatsApp, compras | WP-16..22 | G4 antes de qualquer envio |

C6 pode subir para logo após C2 se o Marcio decidir que o Optimize vem antes do Assunto (decisão de produto, ver `docs/roadmap-status.md`).

## 6. Trilhos (T1–T7) e estado

| Trilho | Estado | Próximo passo |
|---|---|---|
| T1 Plataforma e segurança | Forte em tenant/RLS; sem CI, política, MFA | C1, C2 |
| T2 Memória e documentos | Forte | Proveniência por campo (ADR-P04) |
| T3 Workflow | Inexistente | VS-01 |
| T4 Advisor e UX | Chat e telas de auditoria | Hoje, briefing |
| T5 Optimize | Comparação forte; sem oportunidade/revisão | EP-09 e depois VS-03 |
| T6 Operate/Procurement | Inexistente | Após G4 |
| T7 Validação | Aceite fictício; sem baseline real | `docs/pilot-protocol.md` |
