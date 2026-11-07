# Launch — Fase 0: diagnóstico AS-IS

Data: 07/11/2026. Fonte: `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md` (prompt mestre v1.0, lido integralmente), `CLAUDE.md`, `docs/decisions.md` (D1–D87), Especificação Mestra v1.0, documentos vivos do planejamento (`docs/01-repo-audit.md`, `docs/02-gap-matrix.md`, `docs/roadmap-status.md`) e inspeção do código no commit `96c1ced`.

**Nada foi executado nesta fase além de leitura de código e documentos.** Testes, stack e E2E não foram rodados nesta sessão; os números de testes citados vêm de `docs/roadmap-status.md` (307 testes do backend, 29 fluxos E2E, D85).

Legenda das colunas: **Existente** (código e teste) · **Parcial** (há base, falta parte do requisito do Launch) · **Ausente** · **Desconhecido** (depende de dado externo ou decisão). Cada linha diz também a natureza da afirmação: ✔ confirmado no repositório · ⚖ decisão já validada · ? hipótese · ⛓ dependência externa.

---

## 1. Resumo do entendimento

O Launch é a **implantação guiada e a saúde contínua dos dados** de um condomínio. Hoje o CondoOS já faz o trabalho pesado depois que os dados existem (extração, casamento, 12 regras, achados, assuntos, oportunidades, briefing, aprovações sem envio), mas a **entrada** do condomínio é de backoffice: um gerente de administradora ou um Admin CondoOS cadastra o condomínio num formulário (`NewCondoForm`) ou por JSON (`python -m app.onboarding`), dá acesso às pessoas e depois alguém envia documentos. O síndico não tem jornada, não escolhe objetivo, não vê o que já foi feito por ele nem o que falta para cada capacidade.

O Launch não é um módulo novo de domínio. É uma **camada de condução** (jornada, próximo passo, prontidão por capacidade, delegação) sobre os objetos que já existem: documento, contrato, despesa, extrato, achado, assunto, oportunidade, ação, membership, política.

## 2. Inventário do código atual (o que o Launch reaproveita)

| Área do Launch | Estado | O que existe (caminho) | Lacuna para o Launch |
|---|---|---|---|
| Criar condomínio (tenant) | Parcial ✔ | `app/onboarding/__init__.py` (`onboard`, nunca sobrescreve), `POST /portfolio/condominiums` em `app/routers/registry.py:405` (só gerente ou Admin CondoOS), `web/components/condoos/NewCondoForm.tsx`, fuso por condomínio (`condominium.timezone`, D79) | Formulário único com CNPJ, endereço, unidades e alçadas obrigatórios; síndico não se cadastra; sem estado "identidade não verificada"; alçada exigida no cadastro (o Launch pede "sem alçadas presumidas") |
| Login | Existente ✔ | Link mágico (`app/auth/service.py`, `routers/auth.py`), sessões, `/me` | E-mail desconhecido não recebe link (correto). Não há auto-cadastro |
| Pessoas e papéis | Existente ✔ ⚖ | `membership` com `invited_at/accepted_at/expires_at/revoked_at` (D79), `platform_role` + `condo_assignment`, `auth/rbac.py`, `auth/deps.py::access_for`, `POST/DELETE /condominiums/{id}/members`, `board_member`, tela Configurações | Convite não envia nada nem tem estado "pendente de aceite" visível; sem `Contact` (pessoa sem login: zelador, contato do fornecedor); papéis zelador/fornecedor/morador reservados sem permissão (D77) |
| Upload e e-mail | Existente ✔ | `ingestion/documents.py` (hash, `sniff`, limite `max_upload_mb=20`, chave S3 por condomínio), `ingestion/email.py` (`<slug>@ingest…`, provedor por pasta), CSV/OFX/CNAB, `UploadForm.tsx` | Upload não devolve resultado ao síndico (só envia); sem antivírus; sem lote com acompanhamento; e-mail real (IMAP/SES) não implementado (`InboundEmailProvider` é o ponto de extensão) |
| Classificação e extração | Parcial ✔ | `extraction/pipeline.py` (XML → heurística → IA), `fields.py`, `confidence.py` (<0,9 → fila), `provenance.py` (origem, página, trecho; D85), `clauses.py` (aviso prévio, renovação, multa), versões (`supersedes_id`, D85) | Tipos: nfse, nfe, boleto, recibo, extrato, cnab_retorno, contrato, convencao, ata, outro. **Faltam** apólice, balancete, regimento, laudo, plano de manutenção, aditivo como tipo (hoje aditivo é detectado pelo título, D66). Classe "inferido"/"conflitante" ainda não distinguida (FR-016) |
| Primeira leitura útil de contrato | Parcial ✔ | Contrato nasce do documento (D59), cláusulas com trecho (D85), valor reajustado (`rules/contracts.py`), agenda de aviso prévio (D71) | Não há "cartão de primeiro valor": o síndico não recebe, após o upload, um resumo verificável com o que foi lido, com que fonte e o que falta (aditivos, faturas) |
| Perguntas sobre documentos | Parcial ✔ ⛓ | `chat/` (busca híbrida, 9 ferramentas de leitura, verificação de números e citações), `prompts/chat_system.md` | Sem `ANTHROPIC_API_KEY` o chat responde 503 (bloqueio B4). Sem teste explícito de injeção em PDF (SEC-02 parcial, `docs/traceability.md:52`) |
| Reconciliação | Existente ✔ | `matching/documents.py` (documento → despesa → contrato), `matching/bank.py`, `match_issue` para ambiguidade, regras R01–R12 | Bidirecional parcial: "contrato sem cobrança" existe em `pending.py` (D70); "fatura sem contrato" existe como avulso sem aprovação (D70). Sem cobertura por período por fonte |
| Central de validação | Parcial ✔ | Fila de exceções (`routers/queue.py`, telas `admin/fila`), revisão de documento e casamento, revisão interna de oportunidade (D81) | Só desktop e só equipe/administradora; sem priorização por valor em risco na fila de dados; sem "conflito entre documentos" (contrato × aditivo) como item |
| Documentos esperados | Parcial ✔ | `app/pending.py`: contrato vigente sem NF no mês pela periodicidade (`billing_frequency`, migração 0010) | Calculado na leitura, só para NF de contrato; sem janela/fonte preferencial; não verifica canais antes de acusar ausência; só administradora vê |
| Delegação a terceiros | Ausente | `membership` temporário serve a quem tem login; `case_task` tem responsável, prazo e status (D80) | Sem pedido de documento com link seguro de envio sem conta, sem rastreio de entrega/resposta, sem lembrete |
| Comunicações externas | Ausente ✔ ⚖ | Só o link mágico sai por e-mail (`auth/mailer.py`). Ações aprovadas não enviam nada (`action.dispatch`, D83) | WhatsApp, e-mail de cobrança, lembrete: nada existe e o Plano D-04 diz "só notificações internas" |
| Política, aprovação, kill switch | Existente ✔ ⚖ | `app/policy/` (nega por padrão; L5 sempre negado), `app/actions/` (hash, 7 dias, outbox), `automation_pause` (D83) | Política não conhece "prontidão de dados" como pré-condição |
| Prontidão por capacidade | Ausente | Sinais soltos: `extraction_status`, `needs_review`, `field_confidence`, `pending.py`, briefing "dados parciais" (D82), `competence` fechada só com fila vazia | Nenhum objeto ou função que diga, por capacidade, "não configurado / análise parcial / supervisionada / autorizada" |
| Saúde contínua dos dados | Parcial ✔ | Briefing marca seções desatualizadas (D82); retenção diária (`core/retention.py`); `job` com falhas | Sem monitor de canal parado, último documento recebido, contato inválido, troca de síndico |
| Jornada, marcos e retomada | Ausente | Tela "Hoje" (`/resumo`, D82) é o ponto natural de entrada | Sem estado de jornada, objetivo inicial, modos, "o que o CondoOS já fez por você" |
| Observabilidade econômica | Parcial ✔ | `llm_calls` (custo por chamada), teto mensal (`llm/client.py::month_spend_usd`), `metrics.py` (precisão, extração automática, revisão, custo; base do piloto D84) | Sem tempo até primeiro valor, sem esforço do síndico, sem eventos de ativação/abandono |
| Auditoria | Existente ✔ | `audit_log` e `decision` só inclusão; `case_event`, `action_decision`, `savings_record` só inclusão | Reaproveitar para eventos do Launch |
| Isolamento | Existente ✔ | RLS em todas as tabelas de condomínio (`RLS_TABLES`), `test_isolation.py`, 404 + evento de segurança (D78) | Link de envio sem conta abre uma superfície nova (ver riscos) |

### Design System e componentes reaproveitáveis ✔

Tokens em `web/app/globals.css` (tema escuro, Inter, verde-lima só em ação primária e item ativo; `docs/ui-audit.md`).

- `components/ui`: `Button`, `Card`, `KpiCard`, `Badge`, `Field`, `DataTable`, `FilterChips`, `SidePanel`, `Timeline`, `EmptyState` — cobrem cartões de jornada, escolhas rápidas (FilterChips), progresso (Timeline), painel de evidência (SidePanel).
- `components/condoos`: `InsightCard` (base do cartão de primeiro valor), `EvidenceList` (trechos), `ChatPanel` (guia conversacional), `ContractClauses`, `DocumentNewVersion`, `BriefingView`/`BriefingActions` (tela Hoje), `CaseForm`/`CaseCards` (pendências como assunto), `ActionForm`/`ApprovalPanel` (autorização de envio), `StaffAssignmentsCard`, `SettingsForm`, `NewCondoForm`.
- Layout síndico mobile-first (`BottomTabs`, `/condominio/[id]/...`), administradora desktop (`AdminNav`, `/admin/...`).

**Nenhum componente novo de base é necessário.** Os novos são de domínio: `JourneyCard`, `FirstValueCard` (sobre `InsightCard` + `EvidenceList`), `CapabilityReadiness` (lista com status em texto e ícone), `QuickReplies` (sobre `FilterChips`), `DelegationRequestCard`.

## 3. Lacunas e riscos críticos

| # | Risco | Tipo | Impacto | Mitigação proposta |
|---|---|---|---|---|
| R-L01 | **Identidade e autoridade do síndico.** Hoje quem cria o condomínio é gerente ou Admin CondoOS; o Launch supõe que o síndico chega sozinho. Auto-cadastro abre fraude de identidade (alguém se dizer síndico de um CNPJ alheio) e acesso a dados de terceiros | Identidade | Alto | Piloto: implantação **assistida** (Admin CondoOS cria o tenant e convida o síndico, como F1 de `docs/flows.md`); jornada começa no primeiro login. Auto-cadastro só com verificação (ata de eleição + CNPJ) e decisão do Marcio (pergunta Q-L01) |
| R-L02 | **Envio para terceiros.** Nada sai do sistema hoje além do link mágico (D83, Plano D-04). Delegação e lembretes exigem envio | Comunicação | Alto | Primeiro corte: o sistema **gera o link e o texto**, o síndico copia e envia pelo canal dele (nada sai do CondoOS). Envio por e-mail depois, como tipo de ação pela política (pergunta Q-L02) |
| R-L03 | **Link de envio sem conta** (administradora/fornecedor) é superfície nova de ataque | Segurança | Alto | Token aleatório com hash no banco, escopo de 1 pedido, só upload (nunca leitura), validade curta, revogável, limite de tamanho e quantidade, `ingest_file(process=…)` no condomínio do pedido, auditoria, rate limit |
| R-L04 | **Injeção de instruções em documento** | IA | Alto | Já mitigado em parte (ferramentas só de leitura, política nega por padrão, números conferidos por código). Falta teste explícito com PDF adversarial (SEC-02) — entra como P0 do Launch |
| R-L05 | **Sem chave de API** (B4): classificação por IA, extração por IA, chat e reescrita ficam em replay | Dependência ⛓ | Médio | Guia conversacional **determinístico** (cartões, escolhas rápidas, roteiro) que funciona sem LLM; IA só interpreta texto livre quando disponível, sempre com confirmação |
| R-L06 | **Barra de progresso virar permissão** | Produto | Alto | Marcos derivados de fatos do banco; prontidão é função separada; política consulta prontidão, nunca o marco |
| R-L07 | **WhatsApp oficial** exige conta Meta verificada, BSP, templates aprovados, opt-in e custo por conversa | Dependência ⛓ | Médio | Fora do escopo até a Fase 5 e de decisão comercial; nenhum código antes |
| R-L08 | **Antivírus no upload** inexistente | Segurança | Médio | `sniff` já valida tipo; acrescentar ClamAV (GPL — **não pode no produto**, CLAUDE.md). Alternativa: serviço externo com licença compatível ou só aceitar PDF/XML/imagem/planilha e converter. Decisão adiada (ADR-L06) |
| R-L09 | **Tipos documentais faltantes** (apólice, balancete, laudo, regimento) | Dados | Médio | Acrescentar valores ao enum exige migração (`ck_document_doc_type_valid`, migração 0001, linha 455); só classificação e busca, sem extração estruturada no primeiro corte |
| R-L10 | **Colisão de nomes**: Launch usa M1–M5, Fases 0–8 e gates G0–G8; o Plano Diretor usa M0–M5 e G0–G5; o MVP usa "Marco 1–6" | Documentação | Médio | Prefixo próprio: marcos **LM1–LM5**, fases **LF0–LF8**, gates **LG0–LG8**, backlog **LB-xxx** (D88) |
| R-L11 | Custo operacional não medido (horas humanas de implantação) | Economia | Médio | Instrumentar eventos de jornada (LB-090) e registrar horas humanas no diário do piloto (`docs/pilot-protocol.md`) |
| R-L12 | Dados de moradores | LGPD | Médio | Fora do escopo do Launch inicial (D77: morador sem permissão); importação de contatos só na Fase 4, com minimização |

## 4. Divergências entre o prompt do Launch e o projeto (não resolvidas em silêncio)

| # | Prompt do Launch diz | Projeto hoje | Proposta |
|---|---|---|---|
| DL-01 | Síndico abre a conversa e cria o ambiente (LM1 "cria tenant") | Só gerente ou Admin CondoOS cria condomínio (`registry.py:405`); D73: condomínio contrata direto | Piloto assistido; auto-cadastro como P2 após decisão (Q-L01) |
| DL-02 | Delegação "envia link seguro", lembretes, cobranças | Nada sai do sistema (D83, Plano D-04) | Gerar link e texto para o síndico enviar; envio pelo sistema só como tipo de ação aprovado (Q-L02) |
| DL-03 | Revisor CondoOS é convidado pela jornada | Equipe CondoOS é atribuída pelo Admin (D79, `platform/`) | Manter: a jornada mostra "revisor atribuído / ainda não" como requisito, não convida |
| DL-04 | Entidades `ExtractedFact`, `FactEvidence`, `FactValidation` | Proveniência por campo em `document.field_provenance` (D85), revisão em `reviewed_at` e `extraction_correction` | Não criar tabelas de fato agora (ver ADR-L03) |
| DL-05 | `OnboardingTask`, `DelegationRequest` como objetos | `case_task` existe (D80) | Pendência da jornada pode virar assunto/tarefa quando precisa de responsável; pedido externo é objeto novo (ver ADR-L04) |
| DL-06 | Fases 0–8 com gates G0–G8 | Plano Diretor tem G0–G5 e caminho crítico na VS-06 (aguardando decisão) | Launch corre como trilha própria; LF2 não depende de VS-06. Ordem entre Launch e VS-06 é decisão do Marcio (Q-L03) |

## 5. Recomendação de sequência

1. **LF1 (este documento + blueprint)** → revisão do Marcio (gate LG1).
2. **LF2 — primeiro valor**, sem envio externo e sem auto-cadastro: jornada derivada dos dados, objetivo inicial, cartão de primeiro valor de contrato, prontidão de 3 capacidades, retomada. Uma migração pequena (preferências da jornada). Ver `05-backlog.md`.
3. **LF3** reaproveita quase tudo de matching/pending; maior trabalho é a Central de Validação para o síndico/revisor e conflitos contrato × aditivo.
4. **LF4–LF5** dependem das decisões Q-L02 (envio) e, para WhatsApp, de contrato comercial e conta oficial.
5. **LF6–LF8** depois de piloto real (bloqueio B5).

## 6. Gate LG0 — verificação

- [x] Nenhum componente novo proposto sem dizer o que reaproveita (seção 2 e `03-arquitetura-e-dados.md`).
- [x] Nenhuma tecnologia inventada: toda peça citada existe no repositório ou está marcada como dependência externa.
- [x] Lacunas documentais registradas: sem chave de API (B4), sem piloto real (B5), sem decisão sobre auto-cadastro e envio.
