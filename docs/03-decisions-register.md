# 03 — Registro de decisões: ADRs propostas, divergências e decisões pendentes

Data: 07/11/2026. Este arquivo **não substitui** `docs/decisions.md`: lá ficam as decisões aceitas do projeto (D1–D71, e D72 em diante). Aqui ficam as **propostas** (ADR-P…), as **divergências** entre o planejamento e o produto atual, e as decisões abertas do Plano Diretor (citadas como "Plano D-01..D-12", sem colidir com D1–D71). Quando uma proposta for aceita, ela ganha um número D7x em `docs/decisions.md` e este registro aponta para lá.

Precedência (pacote de prompts): requisitos aprovados > decisões aceitas > código real > plano > sugestão de IA.

## 1. Divergências que exigem decisão do Marcio (não resolvidas em silêncio)

| # | Tema | Planejamento diz | Produto atual / decisão aceita | Impacto | Pergunta ao Marcio |
|---|---|---|---|---|---|
| DV-01 | Público inicial e papel da administradora | Pilotos com **condomínios individuais**; administradora não é canal inicial (Espec. §1.5, Plano §1.3-1) | Produto operado pela administradora (gerente/analista, Carteira); D3 permite síndico profissional como `gerente` sem administradora | Define quem opera fila, correções e validação no piloto | O piloto será com condomínio contratando direto? Quem faz o trabalho hoje feito pela "analista" (o CondoOS? o síndico?) |
| DV-02 | Revisão interna do Optimize | Recomendação **só sai após revisor interno CondoOS** (FR-046, §22.2) | Gerente da **administradora** valida só os graves (D48); médios e baixos publicam direto ao corpo diretivo | Bloqueia FR-046 e o gate G3 | Achados de auditoria contam como "recomendação Optimize"? Se sim, todo achado passa por revisor CondoOS antes do síndico? |
| DV-03 | Objeto central | Assunto/Case com tarefas e máquina de estados (§8) | Achado de auditoria com status próprio (D48, D61) | Risco de dois fluxos paralelos | Achado vira um tipo de Assunto, ou Assunto é criado a partir de achado (vínculo)? (ADR-P01) |
| DV-04 | Vocabulário de economia | Oportunidade com economia bruta/líquida estimada e realizada (§6.3) | "Valor em risco"; o DS foi aplicado sem KPIs de economia (ui-audit §3, conflito 3) | Telas e relatório | Podemos introduzir "Oportunidade" e "economia estimada" nas telas, separadas de "achado"? |
| DV-05 | Papéis | 11 papéis (§9.4: zelador, morador, fornecedor, revisor_condoos, suporte, auditor…) | 5 papéis | Escopo de WP-02 | Quais papéis entram antes do piloto? Proposta: só `revisor_condoos` (se DV-02 = sim) |
| DV-06 | Acesso negado | US-001: "acesso negado e evento de segurança" | 404 sem evento dedicado (D15) | Pequeno | Manter 404 (D15) e **acrescentar** registro de evento de segurança? Proposta: sim, sem mudar a resposta |
| DV-07 | Nome dos documentos vivos | Plano §12.3 cita `docs/decision-log.md` | Projeto usa `docs/decisions.md` (CLAUDE.md) | Nenhum | Resolvido por D72: `decisions.md` é o decision-log; este arquivo é o registro de propostas |

## 2. ADRs propostas (nenhuma aceita ainda)

### ADR-P01 — Assunto (Case) como módulo novo, ligado a achados por vínculo
- **Contexto:** FR-021..026 exigem Assunto, Tarefa, timeline e estados. Achado já tem ciclo próprio auditado.
- **Proposta:** tabelas `case`, `case_event`, `task`, `case_link` (N:N para achado, documento, contrato, fornecedor, despesa), todas com `condominium_id`, RLS e migração com política. `case_event` append-only como `decision`. Achado **não** muda; um assunto pode nascer de um achado ("abrir assunto") e cita o achado como evidência.
- **Alternativas:** (a) converter achado em subtipo de assunto (migração pesada, mexe em R01–R12 e testes de aceite); (b) não ter assunto (contraria P0 da Especificação).
- **Depende de:** DV-03. **Afeta:** WP-04, WP-07, VS-01.

### ADR-P02 — Revisão interna CondoOS como estado antes da publicação
- **Proposta:** papel de plataforma `revisor_condoos` (fora do tenant, acesso mínimo e auditado, §9.4) e estado `em_revisao_interna` antes de `publicado` para o que for "recomendação". Reaproveita a fila de exceções e `decision`.
- **Depende de:** DV-01, DV-02. **Afeta:** WP-02, WP-14, FR-046, G3.

### ADR-P03 — Motor de políticas tipado, negar por padrão
- **Proposta:** módulo `app/policy/` com regras em Python tipado (sem avaliação de strings, §9.2), tabela `policy_version` (versão, vigência, responsável) e decisão `ALLOW / REQUIRE_APPROVAL / REQUIRE_REVIEW / DENY / PAUSE`. Toda ação com efeito fora do sistema passa por ele; enquanto não houver ação externa, o motor só registra e nega. Kill switch por condomínio e tipo (`automation_pause`) consultado pelo worker antes de cada job com efeito.
- **Afeta:** WP-03, WP-10, FR-006/007/034, G4.

### ADR-P04 — Proveniência por campo
- **Proposta:** acrescentar a `document.extracted` (ou tabela `extracted_field`) página, trecho e classe de proveniência (CONFIRMADO, EXTRAÍDO, INFERIDO, NÃO DISPONÍVEL, CONFLITANTE), derivada do que já existe (`field_confidence`, `reviewed_at`, `extraction_correction`).
- **Afeta:** FR-012, FR-016, WP-05.

### ADR-P05 — Oportunidade separada de achado
- **Proposta:** tabela `opportunity` (campos da §6.3) ligada a achados/contratos/despesas; o cálculo de economia fica em código determinístico; estados da §6.4 do Plano. Achado continua sendo o "indício"; oportunidade é a recomendação acionável.
- **Depende de:** DV-04, ADR-P02. **Afeta:** WP-13/14/15.

### ADR-P06 — CI no GitHub Actions
- **Proposta:** workflow com `make lint` e `pytest` contra serviço `pgvector/pgvector:pg16`; E2E fora do CI no primeiro passo (exige a stack completa). Sem segredo de LLM (modo `replay`).
- **Afeta:** WP-01. Baixo risco; pode ser decidido pelo Claude e registrado em `decisions.md` quando implementado.

### ADR-P07 — Fuso horário por condomínio
- **Proposta:** coluna `condominium.timezone` (padrão `America/Sao_Paulo`), usada em prazos, agenda e briefing; datas continuam armazenadas em UTC.
- **Afeta:** FR-001, WF-05, briefing.

## 3. Decisões abertas do Plano Diretor (Plano D-01..D-12)

| ID | Decisão | Opção conservadora do Plano | Situação no projeto |
|---|---|---|---|
| Plano D-01 | Comprador primário | Condomínio cliente, síndico usuário-chave | Aberta; ligada a DV-01 |
| Plano D-02 | Integração da administradora | Importação de arquivo | **Coerente com o produto**: só arquivos (OFX/CSV/CNAB, documentos) |
| Plano D-03 | Stack e deploy | Reusar stack atual | **Resolvida pelo código**: FastAPI + Next.js + PostgreSQL (ver `docs/decisions.md`); propor confirmação formal |
| Plano D-04 | Conteúdo que sai automaticamente | Só notificações internas | Coerente: nada sai hoje |
| Plano D-05 | RAG | Busca híbrida com ACL | **Resolvida** por D52/D53 |
| Plano D-06 | Taxonomia de contratos/faturas | Tipos comuns dos pilotos | Parcial: tipos de documento e categorias por condomínio existem |
| Plano D-07 | Método de economia realizada | Escopo equivalente | Aberta (antes de WP-15) |
| Plano D-08 | Critérios da revisão Optimize | Dupla checagem para riscos altos | Aberta; ligada a DV-02 |
| Plano D-09 | Acesso do fornecedor | Link autenticado mínimo | Aberta (WP-18) |
| Plano D-10 | Obrigações aplicáveis | Cadastro validado manualmente | Aberta (WP-16) |
| Plano D-11 | Retenção | Política por categoria | Parcial: `retention_years` por condomínio + job diário |
| Plano D-12 | Expansão e monetização | Medir antes de precificar | Aberta (G5) |

## 4. Decisões da Especificação §23.2 (D-01..D-12 da Especificação)

Sobrepõem-se às do Plano. As que ainda não têm correspondente acima: Espec. D-02 (Advisor embutido no Optimize — recomendação da própria Especificação, coerente com o produto atual), Espec. D-05 (histórico mínimo para anomalia — hoje R11 usa média e desvio de 12 meses, D23), Espec. D-06 (regras delegáveis pelo síndico — necessária antes de qualquer L4), Espec. D-08 (modelo de cobertura de contrato por ativo/posto/serviço — necessária antes de WP-17), Espec. D-12 (fornecedores de IA externos — ligada a D54 e ao checklist LGPD).
