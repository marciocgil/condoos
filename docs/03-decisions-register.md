# 03 — Registro de decisões: ADRs propostas, divergências e decisões pendentes

Data: 07/11/2026. Este arquivo **não substitui** `docs/decisions.md`: lá ficam as decisões aceitas do projeto (D1–D71, e D72 em diante). Aqui ficam as **propostas** (ADR-P…), as **divergências** entre o planejamento e o produto atual, e as decisões abertas do Plano Diretor (citadas como "Plano D-01..D-12", sem colidir com D1–D71). Quando uma proposta for aceita, ela ganha um número D7x em `docs/decisions.md` e este registro aponta para lá.

Precedência (pacote de prompts): requisitos aprovados > decisões aceitas > código real > plano > sugestão de IA.

## 1. Divergências com o produto — respondidas pelo Marcio em 07/11/2026

| # | Tema | Resposta | Decisão aceita |
|---|---|---|---|
| DV-01 | Público inicial e papel da administradora | Condomínio contrata direto; administradora é colaboradora opcional, nunca dependência estrutural; trabalho da analista dividido em automatizável / validação (CondoOS Reviewer) / fica na administradora | D73 |
| DV-02 | Revisão interna | Identificar tudo automaticamente; revisão proporcional ao risco por política configurável; economia sempre com revisão interna no piloto; críticos/altos com pessoa qualificada; inconclusivos pendentes de evidência; gerente pode validar se o condomínio permitir | D74 |
| DV-03 | Assunto × Achado | ADR-P01 aprovada: Assunto independente, N:N com achados, pode nascer sem achado, checagem de duplicidade | D75 |
| DV-04 | Oportunidade e economia | Sim: objetos separados; cinco estágios de economia; estimado nunca como capturado | D76 |
| DV-05 | Papéis | Síndico, CondoOS Admin, CondoOS Reviewer, administradora no piloto; zelador, conselho com aprovação, fornecedor e morador previstos; permissões granulares, múltiplos papéis, acesso temporário | D77 |
| DV-06 | Acesso negado | Proposta mantida (404 + evento de segurança); sem objeção | Entra com CB-003 |
| DV-07 | Nome dos documentos vivos | Resolvido | D72 |

**Pendente agora:** aprovação do plano de migração 0011–0014 (`docs/data-model.md` §7) antes de qualquer mudança persistente.

## 2. ADRs (situação em 07/11/2026)

### ADR-P01 — Assunto (Case) como módulo novo, ligado a achados por vínculo — **aceita (D75)**; detalhada em `docs/data-model.md` §4
- **Contexto:** FR-021..026 exigem Assunto, Tarefa, timeline e estados. Achado já tem ciclo próprio auditado.
- **Proposta:** tabelas `case`, `case_event`, `task`, `case_link` (N:N para achado, documento, contrato, fornecedor, despesa), todas com `condominium_id`, RLS e migração com política. `case_event` append-only como `decision`. Achado **não** muda; um assunto pode nascer de um achado ("abrir assunto") e cita o achado como evidência.
- **Alternativas:** (a) converter achado em subtipo de assunto (migração pesada, mexe em R01–R12 e testes de aceite); (b) não ter assunto (contraria P0 da Especificação).
- **Afeta:** WP-04, WP-07, VS-01. Ampliação da decisão: vínculo N:N também com oportunidade e outros assuntos; origens sem achado; checagem de duplicidade.

### ADR-P02 — Revisão interna CondoOS como estado antes da publicação — **substituída por ADR-P09 (D74)**
- **Proposta:** papel de plataforma `revisor_condoos` (fora do tenant, acesso mínimo e auditado, §9.4) e estado `em_revisao_interna` antes de `publicado` para o que for "recomendação". Reaproveita a fila de exceções e `decision`.
- **Depende de:** DV-01, DV-02. **Afeta:** WP-02, WP-14, FR-046, G3.

### ADR-P03 — Motor de políticas tipado, negar por padrão
- **Proposta:** módulo `app/policy/` com regras em Python tipado (sem avaliação de strings, §9.2), tabela `policy_version` (versão, vigência, responsável) e decisão `ALLOW / REQUIRE_APPROVAL / REQUIRE_REVIEW / DENY / PAUSE`. Toda ação com efeito fora do sistema passa por ele; enquanto não houver ação externa, o motor só registra e nega. Kill switch por condomínio e tipo (`automation_pause`) consultado pelo worker antes de cada job com efeito.
- **Afeta:** WP-03, WP-10, FR-006/007/034, G4.

### ADR-P04 — Proveniência por campo
- **Proposta:** acrescentar a `document.extracted` (ou tabela `extracted_field`) página, trecho e classe de proveniência (CONFIRMADO, EXTRAÍDO, INFERIDO, NÃO DISPONÍVEL, CONFLITANTE), derivada do que já existe (`field_confidence`, `reviewed_at`, `extraction_correction`).
- **Afeta:** FR-012, FR-016, WP-05.

### ADR-P05 — Oportunidade separada de achado — **aceita (D76)**; detalhada em `docs/data-model.md` §5
- **Proposta:** tabela `opportunity` (campos da §6.3) ligada a achados/contratos/despesas; o cálculo de economia fica em código determinístico; estados da §6.4 do Plano. Achado continua sendo o "indício"; oportunidade é a recomendação acionável.
- **Afeta:** WP-13/14/15. Ampliação da decisão: cinco estágios de economia em `savings_record` (só inclusão).

### ADR-P08 — Papéis de plataforma com atribuição por condomínio — **implementada (D79)**
- **Proposta:** `platform_role` (condoos_admin, condoos_reviewer) + `condo_assignment` com prazo e revogação; terceiro ramo em `app_accessible_condominium_ids`; papéis zelador/fornecedor/morador reservados no CHECK sem permissão; `membership` com `expires_at`/`revoked_at`/convite. Detalhe em `docs/data-model.md` §2 e `docs/authorization-matrix.md`.
- **Alternativa descartada:** papel de plataforma com visão de todos os condomínios (fere menor privilégio).
- **Aguarda:** aprovação da migração 0011.

### ADR-P09 — Política de revisão versionada — **implementada (D79)**
- **Proposta:** `review_policy` versionada (padrão da plataforma + por condomínio), regras tipadas por objeto, regra, categoria, severidade, valor e confiança; requisitos `none / internal_review / qualified_review / pending_evidence`; status `pendente_evidencia`; política padrão reproduz o comportamento atual. Detalhe em `docs/data-model.md` §3.
- **Aguarda:** aprovação da migração 0012.

### ADR-P06 — CI no GitHub Actions
- **Proposta:** workflow com `make lint` e `pytest` contra serviço `pgvector/pgvector:pg16`; E2E fora do CI no primeiro passo (exige a stack completa). Sem segredo de LLM (modo `replay`).
- **Afeta:** WP-01. Baixo risco; pode ser decidido pelo Claude e registrado em `decisions.md` quando implementado.

### ADR-P07 — Fuso horário por condomínio — **implementada (D79)**
- **Proposta:** coluna `condominium.timezone` (padrão `America/Sao_Paulo`), usada em prazos, agenda e briefing; datas continuam armazenadas em UTC.
- **Afeta:** FR-001, WF-05, briefing.

## 3. Decisões abertas do Plano Diretor (Plano D-01..D-12)

| ID | Decisão | Opção conservadora do Plano | Situação no projeto |
|---|---|---|---|
| Plano D-01 | Comprador primário | Condomínio cliente, síndico usuário-chave | **Resolvida** por D73 (condomínio cliente, síndico usuário-chave) |
| Plano D-02 | Integração da administradora | Importação de arquivo | **Coerente com o produto**: só arquivos (OFX/CSV/CNAB, documentos) |
| Plano D-03 | Stack e deploy | Reusar stack atual | **Resolvida pelo código**: FastAPI + Next.js + PostgreSQL (ver `docs/decisions.md`); propor confirmação formal |
| Plano D-04 | Conteúdo que sai automaticamente | Só notificações internas | Coerente: nada sai hoje |
| Plano D-05 | RAG | Busca híbrida com ACL | **Resolvida** por D52/D53 |
| Plano D-06 | Taxonomia de contratos/faturas | Tipos comuns dos pilotos | Parcial: tipos de documento e categorias por condomínio existem |
| Plano D-07 | Método de economia realizada | Escopo equivalente | **Resolvida** por D87 (`medicao_faturas_v1`, D84) |
| Plano D-08 | Critérios da revisão Optimize | Dupla checagem para riscos altos | **Resolvida** por D74 (revisão proporcional ao risco; economia sempre revisada) |
| Plano D-09 | Acesso do fornecedor | Link autenticado mínimo | Aberta (WP-18) |
| Plano D-10 | Obrigações aplicáveis | Cadastro validado manualmente | Aberta (WP-16) |
| Plano D-11 | Retenção | Política por categoria | Parcial: `retention_years` por condomínio + job diário |
| Plano D-12 | Expansão e monetização | Medir antes de precificar | Aberta (G5) |

## 4. Decisões da Especificação §23.2 (D-01..D-12 da Especificação)

Sobrepõem-se às do Plano. As que ainda não têm correspondente acima: Espec. D-02 (Advisor embutido no Optimize — recomendação da própria Especificação, coerente com o produto atual), Espec. D-05 (histórico mínimo para anomalia — hoje R11 usa média e desvio de 12 meses, D23), Espec. D-06 (regras delegáveis pelo síndico — necessária antes de qualquer L4), Espec. D-08 (modelo de cobertura de contrato por ativo/posto/serviço — necessária antes de WP-17), Espec. D-12 (fornecedores de IA externos — ligada a D54 e ao checklist LGPD).

## 5. CondoOS Launch — divergências e perguntas (D88)

Detalhe em `docs/condoos-planning/launch/01-diagnostico-as-is.md` §4 e `00-status-e-proximos-passos.md`.

| # | Tema | Situação |
|---|---|---|
| DL-01 / Q-L01 | Síndico cria o próprio condomínio × só gerente ou Admin CondoOS cria (`registry.py`) | **Respondida (D89):** implantação assistida pelo Admin no piloto |
| DL-02 / Q-L02 | Delegação e lembretes com envio × nada sai do sistema (D83, Plano D-04) | **Respondida (D89):** link e texto gerados, síndico envia |
| DL-03 | Revisor convidado pela jornada × atribuído pelo Admin (D79) | Proposta: manter D79 |
| DL-04 | Tabelas de fato extraído × `field_provenance` (D85) | Proposta: reusar (ADR-L03 no Launch) |
| DL-05 | `OnboardingTask` × `case_task` (D80) | Proposta: reusar `case_task` |
| DL-06 / Q-L03 | Fases e gates do Launch × caminho crítico do Plano (VS-06) | **Respondida (D89):** LF2 antes da VS-06 |
| Q-L04 | Migração 0018 (`launch_state`) e alçadas opcionais no cadastro | **Aprovadas (D89)** |
