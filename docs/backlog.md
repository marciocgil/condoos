# Backlog — épicos, features, histórias e critérios

Data: 07/11/2026 (revisado com D73–D77). Prioridade e ordem seguem `docs/product-roadmap.md`. IDs de história próprios do projeto: **CB-xxx** (para não colidir com US-001..020 da Especificação, citadas quando correspondem).

**Estimativa:** tamanho relativo **P** (até ~1 dia de trabalho assistido), **M** (alguns dias), **G** (uma ou mais semanas), com premissas. Não é prazo nem custo.

**DoR (Plano §11.3)** — história pronta quando tem: problema e persona; FR e fluxo; dependências; dados e fontes; controle de acesso; estados e erros; critérios testáveis; métrica; referência visual (DS v1.0); política, se gerar ação externa.
**DoD (Plano §11.4 + CLAUDE.md)** — implementação integrada; migração com política RLS quando houver tabela de condomínio; testes passando (inclusive isolamento); erros e loading; auditoria; métrica; DS v1.0; `docs/decisions.md`, `roadmap-status.md` e `traceability.md` atualizados; nada vendido como pronto sem teste.

---

## Épico EP-01 — Plataforma segura (G1) · WP-01, WP-02 · P0

### Feature F-01.1 — Integração contínua (ADR-P06)
**CB-001 — CI com lint e testes do backend** · M · ✅ entregue (D78; E2E e badge ficaram de fora) · FR transversal · NFR qualidade (§16.6)
- Como mantenedor, quero que cada push rode lint e pytest, para que uma regressão de isolamento não passe despercebida.
- Aceite: workflow em `.github/workflows/` roda `ruff`, `black --check`, `mypy`, `eslint`, `tsc`, `prettier` e `pytest` com serviço PostgreSQL 16 + pgvector; falha de qualquer um deixa o job vermelho; nenhum segredo de LLM (modo `replay`); tempo e cache registrados.
- Fora do escopo: E2E no CI, deploy.
- Subtarefas: workflow; serviço pgvector; cache uv/npm; badge no README; registrar D7x.
- Premissa: a suíte roda sem a stack completa (já é assim localmente).

### Feature F-01.2 — Lacunas de identidade e tenant
**CB-002 — Fuso horário do condomínio** (ADR-P07) · P · FR-001 · ✅ entregue (D79)
- Aceite: `condominium.timezone` com padrão `America/Sao_Paulo`, validado contra a base IANA; editável em Configurações (gerente); migração sem RLS nova (coluna); agenda e "em atraso" usam o fuso; teste com fuso diferente.

**CB-003 — Evento de segurança em acesso negado** (DV-06) · P · FR-003, US-001 · ✅ entregue (D78; também no 403)
- Aceite: acesso a condomínio alheio continua 404 (D15) e grava `audit_log` `security.access_denied` só com ids; teste para rota de leitura e de escrita; nada de dado pessoal no log.

**CB-004 — Revogação imediata provada (SEC-10)** · P · FR-002, FR-004 · ✅ entregue (D78)
- Aceite: após remover o acesso (ou desativar o usuário), a sessão existente recebe 404/401 na próxima requisição; teste automatizado; se falhar, corrigir em `auth/deps.py`.

**CB-005 — Convite com prazo** · movido para **CB-014** (EP-09), junto com o acesso temporário de externos (D77).

## Épico EP-02 — Política e kill switch · WP-03 · P0

**CB-010 — Motor de política mínimo, nega por padrão** (ADR-P03) · M · FR-006, FR-034, NFR-009
- Aceite: `app/policy/` com decisão tipada (`ALLOW/REQUIRE_APPROVAL/REQUIRE_REVIEW/DENY/PAUSE`); ação desconhecida → `DENY`; toda avaliação auditada com versão da política; testes positivo e negativo por tipo de ação; texto de documento nunca é entrada de autorização (teste SEC-02/SEC-05 com PDF adversarial).
- Fora do escopo: nenhuma ação externa nova.

**CB-011 — Kill switch por condomínio e tipo** · M · FR-007, US-014, SEC-08
- Aceite: gerente pausa/retoma tipos de automação (ex.: `finding.explain`, `rules.evaluate` automático, futuros envios); worker consulta antes de executar; jobs pendentes do tipo ficam `paused` (não executam); auditoria de quem pausou/retomou; tela de Configurações mostra "automação pausada" com texto e ícone.

**CB-012 — Política versionada de alçadas** · P · FR-006
- Aceite: alteração de `approval_limits`/`rule_params` gera nova versão com responsável e vigência; histórico consultável; regras usam a versão vigente na data avaliada.

## Épico EP-09 — Modelo de acesso e revisão proporcional (D73, D74, D77) · WP-02, WP-03 · P0 · *migrações 0011–0012 aguardam aprovação*

**CB-013 — Papéis de plataforma com atribuição por condomínio** (ADR-P08, migração 0011) · G · FR-002, FR-004, FR-008 · ✅ entregue (D79; tela de atribuição pendente → CB-018)
- Aceite: `condoos_admin` e `condoos_reviewer` existem só com `condo_assignment` vigente; sem atribuição = 404; revogação/vencimento cortam o acesso na próxima requisição; Admin atribui e revoga com motivo (auditado); papéis zelador/fornecedor/morador aceitos no CHECK e sem permissão; critérios de `docs/data-model.md` §8 (0011).
**CB-014 — Acesso externo temporário e convite** (migração 0011) · M · FR-002, US-001, US-002 · ✅ entregue (D79; convite pendente sem prazo próprio)
- Aceite: acesso com prazo opcional, convite pendente até o primeiro login, reenvio e revogação; tudo auditado; gerente da administradora continua dando acesso como hoje.
**CB-015 — Política de revisão versionada** (ADR-P09, migração 0012) · G · FR-006, FR-046 · ✅ entregue (D79; tela do síndico pendente → CB-019)
- Aceite: política padrão da plataforma reproduz o comportamento atual (graves aguardam, demais publicam; `test_planted_cases.py` exato); `review_requirement` e versão gravados no achado; nova versão não altera achados decididos; leitura da política no Configurações (somente leitura para o síndico nesta fase).
**CB-016 — Reviewer opera a fila e valida** · M · FR-046, D73 · ✅ entregue (D79)
- Aceite: reviewer atribuído vê a fila de exceções, corrige extração, resolve casamento, valida/descarta graves e fecha o mês do condomínio sem administradora; o gerente só valida se `management_company_reviews`; ação `solicitar_evidencia` leva a `pendente_evidencia` (fora do relatório e do valor em risco).
**CB-017 — Separação validar × aprovar** · P · D77 · ✅ entregue (D79)
- Aceite: teste garante que `review_*` não concede `approve_in_condo` e vice-versa, para todo papel; a interface mostra só as ações permitidas.

**CB-018 — Tela de atribuição da equipe CondoOS** · M · D77 · *novo, sobra do incremento 2*
- Aceite: o Admin lista, atribui (com motivo e prazo opcional) e remove pessoas da equipe CondoOS em Configurações, usando a API existente; status com texto e ícone.
**CB-019 — Política de revisão na tela do síndico** · P · D74 · *novo, sobra do incremento 2*
- Aceite: o síndico vê quem revisa os achados e liga/desliga a revisão pela administradora no celular, usando a API existente.

## Épico EP-03 — Assuntos e tarefas (VS-01) · WP-04, WP-07 · P0 · *ADR-P01 aceita (D75); migração 0013 aguarda aprovação*

**CB-020 — Criar e editar assunto** · G · FR-021, FR-023, US-005
- Aceite: assunto com ID legível, categoria, criticidade, estado, dono, próxima ação e prazo; `case_event` append-only; RLS e migração com política; outro condomínio = 404; edição sem permissão negada; timeline com criação e mudanças (autor, momento, motivo).
**CB-021 — Tarefas do assunto** · M · FR-022
- Aceite: tarefa com responsável, prazo, estado, vínculo; mudança de prazo exige motivo (§7.7).
**CB-022 — Máquina de estados e conclusão com evidência** · M · FR-024, US-007, OPS-02, WF-04
- Aceite: transições da §8.2; `resolvido` exige critério do tipo (evidência anexada quando exigida); "concluído pelo fornecedor" não resolve; reabertura preserva histórico.
**CB-023 — Fila de pendências de assuntos** · M · FR-025
- Aceite: filtros por pessoa, categoria, prazo, criticidade; assunto sem dono/prazo aparece como antipadrão (§8.4).
**CB-024 — Vínculos N:N e assunto a partir de achado** · M · FR-014, FR-027 (parcial)
- Aceite: ação no detalhe do achado cria assunto ligado ou vincula a um existente; um achado pode estar em mais de um assunto (motivo obrigatório); vínculo com oportunidade, documento, contrato, fornecedor, despesa e outro assunto; desvincular preserva histórico; o achado não muda de status.
**CB-026 — Duplicidade antes de criar** · M · FR-028 (parcial), D75
- Aceite: criação devolve candidatos (vínculos em comum ou mesma categoria recente); seguir exige "vincular ao existente" ou "criar mesmo assim" com motivo; teste positivo e negativo.
**CB-027 — Assunto sem achado** · P · D75
- Aceite: síndico ou reviewer cria assunto com origem `human_request` (e as demais origens disponíveis na API), com dono, próxima ação e prazo ou suspensão justificada.
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

## Épico EP-07 — Optimize com revisão interna (VS-03) · WP-11, WP-13, WP-14 · P0 · *D73, D74, D76 aceitas; migração 0014 aguarda aprovação*

**CB-060 — Cláusulas de aviso prévio e rescisão** · M · FR-041, FR-042
- Aceite: extração de aviso prévio (dias), multa e renovação automática com trecho; agenda mostra a data-limite de aviso; testes com contratos do corpus.
**CB-061 — Oportunidade e economia potencial** (ADR-P05, D76) · G · FR-045, US-010, FIN-01/02
- Aceite: `opportunity` com tipo, risco, prontidão e status; reúne N achados ou nasce sem achado; economia **potencial** gravada em `savings_record` por função de cálculo versionada (`method_code`), com baseline, premissas, evidências, confiança, custos e riscos; reproduzível em teste; escopos não comparáveis marcados.
**CB-062 — Fila de revisão interna** (ADR-P09, D74) · G · FR-046, US-011, OPT-01
- Aceite: oportunidade invisível ao corpo diretivo (API e tela) até `aprovada_para_cliente`; só `condoos_reviewer` revisa; vê fontes, cálculo e incerteza; aprovar/ajustar/devolver/rejeitar com motivo (`opportunity_review`, só inclusão); aprovação grava "estimada validada" e o hash da versão; mudança material reabre a revisão.
**CB-063 — Aprovação, contratação e economia realizada** · G · FR-050, US-012 · P1
- Aceite: síndico aprova dentro da alçada (registra "aprovada"); "contratada" exige documento do acordo; "realizada" exige faturas posteriores conferidas contra o baseline e custo de mudança descontado; nada disso move dinheiro nem envia mensagem.
**CB-064 — Estágios de economia na interface** · M · D76
- Aceite: cada estágio com rótulo, ícone e texto próprios (potencial identificada, estimada validada, aprovada para execução, contratada/negociada, realizada e comprovada); nenhum total soma estágios; "realizada" só com evidência; teste de tela e de API.

## Épico EP-08 — Piloto e medição · WP-15 · T7
**CB-070 — Instrumentação do baseline** · M · §17, `docs/pilot-protocol.md`
- Aceite: métricas do protocolo calculáveis por condomínio e período, sem dado pessoal.

## Itens P1+ (não detalhados até o gate anterior)
Ativos e OS (WP-17), portais zelador/fornecedor (WP-18), notificações e escalonamento (WP-19), WhatsApp (WP-20), RFQ/comparador (WP-21), financeiro ampliado (WP-22), conformidade (WP-16), MFA (FR-010), preferências (FR-009). Detalhar apenas quando G4 (para os que têm efeito externo) ou o gate correspondente estiver satisfeito.

## Ordem recomendada
CB-001 → CB-003 → CB-004 → CB-002 → **CB-013 → CB-014 → CB-015 → CB-016 → CB-017** → CB-011 → CB-010 → CB-012 → CB-020..027 → CB-030/031 → CB-041 → CB-042 → CB-050 → CB-060..064. CB-040 a qualquer momento em que houver chave. Itens com migração (CB-013..016, CB-020..027, CB-061..064) só começam após aprovação do plano de migração (`docs/data-model.md` §7).
