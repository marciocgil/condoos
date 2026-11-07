# Backlog — épicos, features, histórias e critérios

Data: 07/11/2026. Prioridade e ordem seguem `docs/product-roadmap.md`. IDs de história próprios do projeto: **CB-xxx** (para não colidir com US-001..020 da Especificação, citadas quando correspondem).

**Estimativa:** tamanho relativo **P** (até ~1 dia de trabalho assistido), **M** (alguns dias), **G** (uma ou mais semanas), com premissas. Não é prazo nem custo.

**DoR (Plano §11.3)** — história pronta quando tem: problema e persona; FR e fluxo; dependências; dados e fontes; controle de acesso; estados e erros; critérios testáveis; métrica; referência visual (DS v1.0); política, se gerar ação externa.
**DoD (Plano §11.4 + CLAUDE.md)** — implementação integrada; migração com política RLS quando houver tabela de condomínio; testes passando (inclusive isolamento); erros e loading; auditoria; métrica; DS v1.0; `docs/decisions.md`, `roadmap-status.md` e `traceability.md` atualizados; nada vendido como pronto sem teste.

---

## Épico EP-01 — Plataforma segura (G1) · WP-01, WP-02 · P0

### Feature F-01.1 — Integração contínua (ADR-P06)
**CB-001 — CI com lint e testes do backend** · M · FR transversal · NFR qualidade (§16.6)
- Como mantenedor, quero que cada push rode lint e pytest, para que uma regressão de isolamento não passe despercebida.
- Aceite: workflow em `.github/workflows/` roda `ruff`, `black --check`, `mypy`, `eslint`, `tsc`, `prettier` e `pytest` com serviço PostgreSQL 16 + pgvector; falha de qualquer um deixa o job vermelho; nenhum segredo de LLM (modo `replay`); tempo e cache registrados.
- Fora do escopo: E2E no CI, deploy.
- Subtarefas: workflow; serviço pgvector; cache uv/npm; badge no README; registrar D7x.
- Premissa: a suíte roda sem a stack completa (já é assim localmente).

### Feature F-01.2 — Lacunas de identidade e tenant
**CB-002 — Fuso horário do condomínio** (ADR-P07) · P · FR-001
- Aceite: `condominium.timezone` com padrão `America/Sao_Paulo`, validado contra a base IANA; editável em Configurações (gerente); migração sem RLS nova (coluna); agenda e "em atraso" usam o fuso; teste com fuso diferente.

**CB-003 — Evento de segurança em acesso negado** (DV-06) · P · FR-003, US-001
- Aceite: acesso a condomínio alheio continua 404 (D15) e grava `audit_log` `security.access_denied` só com ids; teste para rota de leitura e de escrita; nada de dado pessoal no log.

**CB-004 — Revogação imediata provada (SEC-10)** · P · FR-002, FR-004
- Aceite: após remover o acesso (ou desativar o usuário), a sessão existente recebe 404/401 na próxima requisição; teste automatizado; se falhar, corrigir em `auth/deps.py`.

**CB-005 — Convite com prazo** · M · FR-002, US-001 · *depende de DV-05*
- Aceite: acesso concedido fica "convidado" até o primeiro login, expira em prazo configurável, pode ser reenviado e revogado; auditado.

## Épico EP-02 — Política e kill switch · WP-03 · P0

**CB-010 — Motor de política mínimo, nega por padrão** (ADR-P03) · M · FR-006, FR-034, NFR-009
- Aceite: `app/policy/` com decisão tipada (`ALLOW/REQUIRE_APPROVAL/REQUIRE_REVIEW/DENY/PAUSE`); ação desconhecida → `DENY`; toda avaliação auditada com versão da política; testes positivo e negativo por tipo de ação; texto de documento nunca é entrada de autorização (teste SEC-02/SEC-05 com PDF adversarial).
- Fora do escopo: nenhuma ação externa nova.

**CB-011 — Kill switch por condomínio e tipo** · M · FR-007, US-014, SEC-08
- Aceite: gerente pausa/retoma tipos de automação (ex.: `finding.explain`, `rules.evaluate` automático, futuros envios); worker consulta antes de executar; jobs pendentes do tipo ficam `paused` (não executam); auditoria de quem pausou/retomou; tela de Configurações mostra "automação pausada" com texto e ícone.

**CB-012 — Política versionada de alçadas** · P · FR-006
- Aceite: alteração de `approval_limits`/`rule_params` gera nova versão com responsável e vigência; histórico consultável; regras usam a versão vigente na data avaliada.

## Épico EP-03 — Assuntos e tarefas (VS-01) · WP-04, WP-07 · P0 · *depende de ADR-P01 / DV-03*

**CB-020 — Criar e editar assunto** · G · FR-021, FR-023, US-005
- Aceite: assunto com ID legível, categoria, criticidade, estado, dono, próxima ação e prazo; `case_event` append-only; RLS e migração com política; outro condomínio = 404; edição sem permissão negada; timeline com criação e mudanças (autor, momento, motivo).
**CB-021 — Tarefas do assunto** · M · FR-022
- Aceite: tarefa com responsável, prazo, estado, vínculo; mudança de prazo exige motivo (§7.7).
**CB-022 — Máquina de estados e conclusão com evidência** · M · FR-024, US-007, OPS-02, WF-04
- Aceite: transições da §8.2; `resolvido` exige critério do tipo (evidência anexada quando exigida); "concluído pelo fornecedor" não resolve; reabertura preserva histórico.
**CB-023 — Fila de pendências de assuntos** · M · FR-025
- Aceite: filtros por pessoa, categoria, prazo, criticidade; assunto sem dono/prazo aparece como antipadrão (§8.4).
**CB-024 — Abrir assunto a partir de achado** · P · FR-014, FR-027 (parcial)
- Aceite: ação no detalhe do achado cria assunto ligado; achado não muda de status.
**CB-025 — Telas Assuntos e Assunto 360° (mínimo)** · G · FR-023, FR-025 · DS v1.0
- Aceite: lista e detalhe com `DataTable`, `Timeline`, `SidePanel`; status sempre com texto e ícone; mobile (síndico) e desktop (administradora); Playwright do fluxo VS-01.

## Épico EP-04 — Informação confiável (G2) · WP-05 · P0

**CB-030 — Proveniência por campo** (ADR-P04) · M · FR-012, FR-016, DOC-01
- Aceite: cada campo extraído tem página (quando houver), trecho e classe de proveniência; campo ausente = "não disponível", nunca valor inventado; correção humana vira "confirmado" com autor; tela de correção mostra o trecho.
**CB-031 — Versão de documento** · M · FR-015, DOC-02
- Aceite: novo arquivo do mesmo documento lógico vira versão; versão vigente identificada; busca usa a vigente; anteriores preservadas.

## Épico EP-05 — Advisor · WP-06, WP-08, WP-09 · P0

**CB-040 — Avaliação ao vivo do chat** · P · FR-031, AI-01 · *bloqueado: chave de API*
- Aceite: `make chat-eval` ≥ 90 %, zero vazamento; resultado em `docs/chat_eval.md`.
**CB-041 — Tela Hoje** · G · FR-032, FR-033 · §7.3
- Aceite: blocos "precisa de você", decisões, atrasos, agenda, radar; cada cartão abre o contexto; nada de "nota única"; fonte e última atualização visíveis.
**CB-042 — Briefing diário (VS-04)** · G · FR-032, US-008
- Aceite: período e fuso corretos; persistido com versão; só cita fatos com fonte; dado parcial sinalizado; não afirma execução inexistente; entrega interna (tela) primeiro — nada por e-mail/WhatsApp sem política.

## Épico EP-06 — Aprovações com escopo congelado · WP-10 · P0

**CB-050 — Pedido de aprovação contextual (VS-05 sem envio)** · G · FR-034, FR-058, US-013, SEC-04/05
- Aceite: `approval_request` com efeito exato, valor e teto, executor, prazo, evidências, versão e hash do payload; alteração material invalida; expiração impede execução; rejeição bloqueia; tela §7.5.

## Épico EP-07 — Optimize com revisão interna (VS-03) · WP-11, WP-13, WP-14 · P0 · *depende de DV-01, DV-02, DV-04*

**CB-060 — Cláusulas de aviso prévio e rescisão** · M · FR-041, FR-042
- Aceite: extração de aviso prévio (dias), multa e renovação automática com trecho; agenda mostra a data-limite de aviso; testes com contratos do corpus.
**CB-061 — Oportunidade** (ADR-P05) · G · FR-045, US-010, FIN-01/02
- Aceite: campos da §6.3; economia calculada em código, reproduzível em teste; escopos não comparáveis marcados; ligada a achados e documentos.
**CB-062 — Fila de revisão interna** (ADR-P02) · G · FR-046, US-011, OPT-01
- Aceite: recomendação invisível ao condomínio até aceite do revisor; revisor vê fontes, cálculo e incerteza; aprovar/ajustar/rejeitar com motivo; versão congelada; mudança após aceite exige nova revisão.
**CB-063 — Economia realizada** · G · FR-050, US-012 · P1
- Aceite: baseline explícito; custo de mudança descontado; estimada ≠ realizada.

## Épico EP-08 — Piloto e medição · WP-15 · T7
**CB-070 — Instrumentação do baseline** · M · §17, `docs/pilot-protocol.md`
- Aceite: métricas do protocolo calculáveis por condomínio e período, sem dado pessoal.

## Itens P1+ (não detalhados até o gate anterior)
Ativos e OS (WP-17), portais zelador/fornecedor (WP-18), notificações e escalonamento (WP-19), WhatsApp (WP-20), RFQ/comparador (WP-21), financeiro ampliado (WP-22), conformidade (WP-16), MFA (FR-010), preferências (FR-009). Detalhar apenas quando G4 (para os que têm efeito externo) ou o gate correspondente estiver satisfeito.

## Ordem recomendada
CB-001 → CB-003 → CB-004 → CB-002 → CB-011 → CB-010 → CB-012 → CB-020..025 → CB-030/031 → CB-041 → CB-042 → CB-050 → CB-060..063. CB-040 a qualquer momento em que houver chave. CB-005 depois de DV-05.
