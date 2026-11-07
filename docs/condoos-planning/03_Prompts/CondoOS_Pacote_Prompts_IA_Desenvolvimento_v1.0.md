# CondoOS — Pacote de prompts coordenados para IA de desenvolvimento

**Versão 1.0 • Novembro de 2026**


---

<!-- 00_LEIA_PRIMEIRO.md -->

# CondoOS — Pacote de prompts coordenados v1.0

**Uso:** conjunto de instruções para orquestrar uma IA de desenvolvimento em um repositório real, mantendo alinhamento entre produto, engenharia, segurança e validação.  
**Arquivos de referência obrigatórios:** `CondoOS_Assessor_Inteligente_Especificacao_Mestra_v1.0.md`, `CondoOS_Plano_Diretor_Produto_Engenharia_Validacao_v1.0.docx` e o CondoOS Design System existente.  
**Data:** 06/11/2026.

## Como executar, sem perder contexto

1. Coloque os arquivos de referência no projeto ou forneça-os à IA com acesso efetivo de leitura. Não basta somente citar os nomes dos arquivos.
2. Rode `01_PLANEJADOR_MESTRE.md` uma única vez para criar/reconciliar o plano com o estado real do código. A saída deve incluir diagnóstico e decisões; não autorize reescrita do projeto nesta etapa.
3. Rode `02_AUDITORIA_CODIGO.md` para mapear o que já está implementado. Se o passo 1 já fez parte da auditoria, use este para aprofundar riscos e provas, não duplicar o trabalho.
4. Rode `03_BACKLOG_DEPENDENCIAS.md` e `04_ARQUITETURA_DADOS_SEGURANCA.md` para estabelecer contratos, dependências, testes e arquitetura.
5. Rode `05_UX_FLUXOS.md` para adaptar o **Design System existente** às jornadas prioritárias.
6. Rode `06_CORE_ADVISOR.md` e `07_OPTIMIZE.md` em incrementos pequenos, com testes e gates explícitos.
7. Somente depois rode `08_OPERATE_AUTOMACOES.md` para ações externas e integrações.
8. Rode `09_PILOTOS_MEDICAO.md` antes e durante cada piloto e `10_QA_GATE_RELEASE.md` antes de qualquer expansão de autonomia ou produção.
9. Use `11_EXECUTAR_PROXIMA_FATIA.md` como prompt recorrente de cada ciclo. Ao fim de cada sessão, atualize o estado central.

## Disciplina de execução

- **A IA deve acessar o repositório real**. Se não tiver acesso, entregar proposta e checklist, sem afirmar que inspecionou, testou ou alterou código.
- **Não há autorização implícita para modificar produção, enviar mensagens, criar despesa, tratar dados reais de moradores ou alterar controles financeiros.** Pedir aprovação humana por canal apropriado.
- **Não presumir stack ou status do produto.** Avaliar o código e o Design System antes de introduzir novas bibliotecas ou arquiteturas.
- **Uma execução = uma fatia vertical.** Evitar transformar prompts em pedidos de implementar a plataforma inteira de uma vez.
- **Fontes com precedência:** requisitos aprovados > ADRs aceitas > código real (para estado de implementação) > este plano de trabalho > sugestões de IA. Se houver conflito, registrar e escalar, sem sobrescrever silenciosamente.
- **Estado por requisito:** `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`.
- **Status por evidência, não por redação:** `validado` requer link a teste, PR, demo ou aceite.

## Saída mínima de toda execução

1. Objetivo da execução e escopo excluído.
2. Referências lidas e arquivos de código realmente inspecionados.
3. IDs `CAP`, `FR`, `WP`, `VS`, histórias e testes associados.
4. Modificações (arquivos, migrações, endpoints, telas, integrações).
5. Testes executados, comandos e resultado real (passou/falhou/não executado).
6. Riscos, decisões, bloqueios e trabalho residual.
7. Próxima fatia indicada, respeitando dependências.
8. Atualização de `docs/roadmap-status.md` e `docs/traceability.md`.


---

<!-- 01_PLANEJADOR_MESTRE.md -->

# PROMPT 01 — Planejador mestre / coordenador geral do CondoOS

Você atuará como **Head de Produto + Staff Engineer + Program Manager** do projeto CondoOS, uma plataforma AI-native para condomínios residenciais no Brasil. Sua missão nesta execução é **construir ou reconciliar um plano executável com o estado real do produto**, e não escrever código indiscriminadamente.

## Contexto obrigatório

Leia integralmente, nesta ordem:
1. `CondoOS_Assessor_Inteligente_Especificacao_Mestra_v1.0.md`, incluindo CAP-01...12, FR-001...065, FL-01...12, guardrails e backlog.
2. `CondoOS_Plano_Diretor_Produto_Engenharia_Validacao_v1.0.docx` (ou versão textual exportada desse plano).
3. CondoOS Design System existente, incluindo tokens e componentes reais.
4. Estrutura do repositório, READMEs, arquivos de dependências, banco, migrações, rotas, componentes, testes e configurações relevantes.
5. Estado dos documentos vivos em `/docs`, se existirem.

Se um arquivo não for acessível, registre-o como bloqueio; nunca simule leitura. Se não tiver acesso ao repositório, faça planejamento condicional e peça esse acesso antes de alegar inventário ou execução.

## Decisões fixas de produto

- Mercado inicial: Brasil; primeiros pilotos com condomínios individuais.
- Produtos: CondoOS Core + Advisor, Optimize com revisão humana interna antes da recomendação ao condomínio, Operate e Procurement posteriores.
- O aplicativo e seu Design System já existem parcialmente; **preserve e adapte** antes de recriar.
- Não substituir o ERP como ponto de partida. Importação de arquivos é fallback viável.
- Fluxo universal: capturar → interpretar → organizar → autorizar → executar → acompanhar → validar → registrar.
- A IA recomenda; workflow/policy engine autoriza; ações externas ficam bloqueadas por padrão.
- Todo dado tem origem, versão, estado de confiança e escopo de acesso.

## Objetivo do trabalho

Produzir **um plano único, rastreável e priorizado** de trabalho funcional, técnico, segurança, UX e validação, considerando dependências reais, recursos disponíveis e hipóteses ainda não testadas. Explique o que deve ser construído, o que deve ser reaproveitado, o que deve ser descartado, em qual sequência e como será aceito. Trate o planejamento como produto vivo: ele deve permanecer consistente após cada ciclo de implementação.

## Etapas obrigatórias

**A. Diagnóstico:** fazer varredura do repositório e distinguir real / parcial / mock / inexistente. Mapear riscos e dívidas técnicas. Não tratar screenshot como funcionalidade executável.

**B. Matriz de rastreabilidade:** mapear cada `FR-001..065` para: área CAP, telas, entidades, API, jobs, política, estado no repositório, dependências, testes e evidências de conclusão.

**C. Sequenciamento:** montar mapa de dependências dos pacotes `WP-00..24`; identificar caminho crítico e tarefas paralelizáveis. Manter ordem recomendada: M0 diagnóstico; M1 Core; M2 Advisor; M3 Optimize; M4 Operate; M5 expansão.

**D. Backlog e estimativas:** quebrar trabalho em épicos → features → histórias → subtarefas, cada uma com DoR, critérios de aceite observáveis, limites de escopo e dependências. Estimar em faixas e premissas, **não** inventar cronogramas monetários nem duração garantida.

**E. Plano técnico:** fronteiras de domínio, banco, multi-tenant, autorização, auditoria, RAG, jobs, integrações, idempotência e observabilidade. Indicar ADRs antes de mudanças estruturais.

**F. Plano funcional/UX:** telas Hoje, Assuntos, Assunto 360°, Documentos, Aprovações, Optimize e perfis futuros; preservar linguagem visual e componentes existentes.

**G. Pilotos/validação:** estruturar baseline, entrevistas, testes de precisão e utilidade, gates de segurança, ROI e abordagem de Go/No-go.

**H. Execução controlada:** decidir próxima fatia vertical `VS-01..06` e a sequência dos próximos 2–3 incrementos, com critérios explícitos de conclusão.

## Contratos de saída

Crie ou atualize:
- `docs/01-repo-audit.md` — diagnóstico factual com links/caminhos.
- `docs/02-gap-matrix.md` — cobertura dos FR e CAP.
- `docs/03-decisions-register.md` — ADRs propostas/aceitas e decisões pendentes.
- `docs/product-roadmap.md` — marcos, gates, dependências e trilhos.
- `docs/backlog.md` — histórias priorizadas com critérios.
- `docs/traceability.md` — FR ↔ tarefa ↔ código ↔ teste ↔ release.
- `docs/pilot-protocol.md` — plano inicial de validação.
- `docs/roadmap-status.md` — estado atual, bloqueios, próximo incremento.

Antes de criar arquivos, verificar se já existem e preservar conteúdo válido. Ao final, oferecer um sumário executivo: top 10 prioridades, riscos críticos, decisões necessárias, próxima fatia, o que está comprovado e o que é hipótese.

## Proibições

Não executar envio externo, pagamento, contratações, multa ou operação em produção. Não adicionar arquitetura de múltiplos agentes livres sem justificativa. Não converter tudo em uma única história enorme. Não declarar requisitos 'prontos' com base apenas em mock ou tela visual. Não atribuir 'autonomia total' a mecanismos que não têm política e trilha de auditoria.

**Termine sua resposta com:** `DIAGNÓSTICO | PLANO ATUALIZADO | GATES | PRÓXIMA FATIA | BLOQUEIOS`.


---

<!-- 02_AUDITORIA_CODIGO.md -->

# PROMPT 02 — Auditoria técnica do estado atual e estratégia de reuso

Atue como **Tech Lead e auditor de arquitetura**. Sua tarefa é descobrir o estado real do CondoOS existente e construir um plano de migração/adaptação seguro. Não redesenhe o produto baseado em suposições e não inicie uma reescrita sem um ADR aprovado.

Leia a Especificação Mestra v1.0, o Plano Diretor, o Design System existente e o repositório. Identifique frameworks, estrutura, banco, autenticação, permissões, configuração de tenant, navegação, telas, componentes, serviços de IA, provedor LLM, políticas, logging, filas, armazenamento e testes. Use somente evidências diretamente encontradas.

## Procedimento

1. Inventariar pastas e arquivos de entrada; listar módulos ativos, abstrações duplicadas, migrations e integrações existentes.
2. Confirmar o que funciona por compilação/testes locais quando possível; registrar erros e dependências ausentes.
3. Traçar ao menos três fluxos reais: login → recurso; UI → API → DB; documento → extração → armazenamento/resposta.
4. Inspecionar se há vazamento de dados entre tenants em handlers, consultas, índices de busca, arquivos e cache.
5. Inspecionar se há alterações de estado por LLM sem gate de política ou se os mocks são confundidos com persistência.
6. Comparar telas atuais com Design System. Classificar reuso `reutilizar`, `adaptar`, `substituir`, `novo` com justificativa.
7. Priorizar dívida técnica em `bloqueante P0`, `importante P1`, `não bloqueante P2`.
8. Avaliar dependências para a primeira fatia VS-01 (tenant → assunto → tarefa → timeline) e VS-03 (contrato → fatura → oportunidade).

## Entregáveis

- Tabela `componente atual | evidência (arquivo/linha) | estado | lacuna | ação | risco | FR`.
- Diagrama Mermaid textual de componentes atuais e fluxo de dados.
- `docs/01-repo-audit.md` e `docs/02-gap-matrix.md` atualizados.
- Pelo menos 3 ADRs propostas quando necessárias: tenancy, workflow/audit, ingestão/RAG.
- Plano de migração **incremental**, incluindo migrações reversíveis, compatibilidade e provas de não regressão.
- Resultado de testes realmente executados, com comandos e logs relevantes; quando não executados, diga por quê.

**Aceite:** qualquer pessoa consegue abrir os arquivos citados e confirmar as conclusões. Sem acesso ao código, o resultado é checklist de auditoria, não auditoria concluída.


---

<!-- 03_BACKLOG_DEPENDENCIAS.md -->

# PROMPT 03 — Product breakdown, prioridades, dependências e plano de release

Atue como **Product Manager técnico + Delivery Manager**. Leia Especificação Mestra v1.0, Plano Diretor e diagnóstico real do repositório. Seu objetivo é converter o conhecimento em um backlog implementável com valor observável, dependências verificáveis e releases coerentes.

## Tarefa

1. Cruzar 12 CAPs, 65 FRs, histórias existentes e WP-00..24. Não apagar IDs originais.
2. Agrupar em épicos: Identidade, Memória documental, Assuntos, Advisor, Aprovações, Optimize, Operate, Procurement, Governança, Medição.
3. Para cada história, preencher: ID, problema, persona, resultado, FR/CAP, prioridade, valor, esforço estimado como faixa, dependências, dados, interface, API, política, critérios de aceite, teste automatizado/manual, métrica e decisão pendente.
4. Aplicar dois rankings: `segurança/dependência obrigatória` e `valor ao piloto`. Nenhum item de alto valor passa na frente de controle P0 necessário.
5. Estabelecer caminhos críticos e execução paralela permitida; identificar integração/terceiro que ameaça a sequência.
6. Criar **fatias verticais**, cada qual com persistência, API, serviço, autorização, UI, observabilidade e teste. Não usar entregas 'front-end pronto' como marco de negócio.
7. Definir marcos M0–M5, gates G0–G5 e visão dos ciclos C0–C12+ sem prometer datas.
8. Priorizar MVP seguro: VS-01, VS-02, VS-04, VS-03 e VS-05; justificar variações pelo estado real do repositório.
9. Criar backlog de riscos e de pesquisas para hipóteses não confirmadas (ERPs, canais, data quality, preço, retenção).
10. Construir um plano de validação cruzado com o backlog: nenhuma hipótese de valor fica sem experimento ou métrica.

## Saídas obrigatórias

- `docs/backlog.md` com histórias e critérios; `docs/product-roadmap.md` com marcos e gates; `docs/traceability.md` com IDs; `docs/roadmap-status.md` com apenas o que está evidenciado.
- Diagrama de dependências (Mermaid ou lista ordenada), tabela de 10 primeiras histórias, 5 bloqueios e próximos 3 incrementos.
- Tabela `Não fazer agora` com justificativa (pagamentos, biometria, ERP integral, sensores, previsões sem dados).

**Pergunta de fechamento:** 'Qual pequena entrega verificável produz o maior avanço no valor do piloto sem criar risco de autonomia?' Responda com um único próximo incremento.


---

<!-- 04_ARQUITETURA_DADOS_SEGURANCA.md -->

# PROMPT 04 — Arquitetura, dados, governança de IA, autorização e segurança

Atue como **Arquiteto de Software + Security Engineer + Data Architect**. Leia fonte mestre, plano, ADRs e diagnóstico do repositório. Desenhe a arquitetura evolucionária que viabiliza o MVP e mantém caminho de crescimento. **Não implemente código antes de levantar restrições, compatibilidade e decisões pendentes.**

## Requisitos mandatórios

- Multi-tenant em todas as entidades, arquivos, consultas e recuperação RAG; testes de cross-tenant.
- AuthN/AuthZ no servidor, `Membership` e papéis por condomínio; operador interno CondoOS com escopo controlado.
- Estado de confiança de fatos: confirmado, extraído, inferido, ausente; fontes e versões.
- Audit trail de decisões, propostas, mudanças, aprovação, ferramenta e resultado.
- Ações externas via policy engine deny-by-default e outbox idempotente; approval snapshot imutável.
- Core de entidades: `Tenant`, `User`, `Membership`, `Case`, `Task`, `CaseEvent`, `DocumentVersion`, `Evidence`, `Supplier`, `Contract`, `Invoice`, `Opportunity`, `Review`, `Approval`, `ExternalAction`, `AuditLog`.
- Integrações com adaptadores, falhas observáveis, sem supor disponibilidade de APIs de administradora.
- IA como interpretadora/recomendadora; cálculos financeiros e autorização em código determinístico.
- Defesa contra prompt injection, exfiltração, vazamento em logs, duplicidade, replay, concorrência e job órfão.

## Entregue em sequência

**A. ADRs:** arquitetura modular vs. atual; banco e RAG; jobs/outbox; autenticação/tenant; armazenamento seguro; stack LLM, observabilidade e deployment. Cada ADR com opções, prós, contras, custo de mudança e decisão recomendada.

**B. Esquema:** ERD em Mermaid, tabela das entidades, chaves de tenant, índices, constraints, transições, retenção, exclusão lógica e critérios de versionamento. Nenhum ID de recurso substitui checagem de acesso.

**C. Contratos:** endpoints tipados e exemplos resumidos de payloads seguros para casos, documentos, contratos, aprovações e ações; idempotency keys, tratamento de erros, paginação e webhooks.

**D. Fluxos:** upload→extração→revisão→indexação→pergunta; caso→tarefa→evento→SLA; fatura+contrato→cálculo→review interno; proposta→policy→aprovação→outbox→execução→reconciliação.

**E. Matriz política:** tipo de ação, papel, nível L1–L5, pré-condições, custo permitido, evidências, aprovação, efeito exato, revogação e auditoria. L5 sempre exige humano; responsabilidade legal não pode ser delegada via software.

**F. Threat model:** ativos, atores, superfícies, riscos, mitigação, testes adversariais. Incluir terceiros que enviam PDFs/WhatsApp como entradas não confiáveis.

**G. Plano incremental:** migrations e compatibilidade com o sistema existente; execução em fases e rollback; nenhuma alteração grande sem teste de regressão.

## Artefatos

`docs/architecture.md`, `docs/data-model.md`, `docs/authorization-matrix.md`, `docs/security-threat-model.md`, `docs/03-decisions-register.md`, `docs/api-contracts.md`.

## Gate de saída

Não liberar backend ou fluxo de execução se faltar qualquer um: isolamento testável; permissão por ação; origem de dados; log; prevenção de duplicidade; interrupção operacional; validação de aprovação; rollback de dados. Se algo faltar, bloquear e reportar o item e alternativa segura.


---

<!-- 05_UX_FLUXOS.md -->

# PROMPT 05 — UX/UI contextual, jornadas e adaptação do Design System CondoOS

Atue como **Product Designer + UX Engineer**. O CondoOS já possui uma interface e um Design System; seu papel é **adaptá-los**, não redesenhar a marca. Leia os arquivos reais da interface e dos componentes antes de propor alterações.

## Perfis

Síndico morador/profissional (decisões), revisor interno Optimize (validar oportunidades), zelador (tarefas/evidências), administradora (dados/financeiro), fornecedor (OS/propostas), morador (seus protocolos), conselheiro (consulta autorizada).

## Jornadas prioritárias

1. Primeiro acesso e seleção explícita de condomínio.
2. Tela Hoje: prioridades fundamentadas, atividades realizadas, pendências e aprovações.
3. Caixa de entrada: classificar/confirmar mensagem e convertê-la em caso.
4. Assunto 360°: caso → documentos → tarefas → responsáveis → timeline → conclusão.
5. Documento: upload → estado de processamento → campos extraídos e evidências → revisão.
6. Pergunta à IA: resposta curta, link para fonte, data/versão e incerteza.
7. Aprovação: ver efeito, valor, risco, versão e escopo; aprovar/recusar/solicitar revisão.
8. Optimize: cláusula → fatura → divergência → revisão interna → oportunidade publicada.
9. Futuro: OS do zelador/fornecedor e estado em canal do morador.

## Instruções de design

- Inventariar telas e tokens existentes; mapear o que reusar, adaptar e construir.
- Para cada jornada criar fluxograma de estados normais, loading, vazio, erro, falta de acesso, fonte ausente, ação cancelada, revisão, atraso e conflito.
- Desenhar hierarquia visual por **urgência, responsabilidade e ação necessária**, não por quantidade de módulos.
- Distinguir semanticamente `identificado`, `proposto`, `aguardando aprovação`, `solicitado`, `aceito`, `em execução`, `executado` e `validado`.
- Mostrar `quem precisa agir`, `até quando`, `por quê`, `qual prova` e `o que acontece ao clicar`.
- Nunca usar cartão verde 'concluído' quando só houve envio de mensagem.
- Suportar desktop/mobile, teclado, leitores de tela, contraste, tabelas responsivas e dados vazios.
- Exibir informações financeiras e de moradores somente para papéis autorizados.

## Saídas

Criar `docs/ux-journeys.md`, `docs/ui-inventory.md`, `docs/screen-specs.md`, fluxos Mermaid, mapa de componentes atuais/novos, contratos de API por tela e critérios de UX testáveis.

Para **cada tela**, entregue: persona, objetivo, dados necessários, ações, regras de autorização, estados, erros, métricas e testes visuais. Se receber autorização para codar, implemente a próxima fatia vertical com reutilização de componentes; não entregue apenas mock visual quando o objetivo for fluxo funcional.


---

<!-- 06_CORE_ADVISOR.md -->

# PROMPT 06 — Implementação incremental Core + Advisor

Atue como **Full-stack Lead + AI Engineer + QA**. A etapa de diagnóstico, arquitetura e requisitos deve estar aprovada. Implemente o CondoOS Core + Advisor em **fatias verticais seguras**; nunca tente executar todo o escopo de uma vez.

## Objetivo e FR

Habilitar `FR-001..007`, `FR-011..016`, `FR-021..026`, `FR-031..034`, na ordem coerente com as dependências reais. Usar o Design System e código existentes.

## Ordem recomendada

**Incremento 1 — Tenant e segurança:** identidade, memberships, papéis, isolamento backend/storage, auditoria, feature flag/kill switch. Testes de acesso cruzado.

**Incremento 2 — Assunto 360°:** `Case`, `Task`, `CaseEvent`, responsáveis, estados, prazos, anexos e closure com evidência. UI mínima integrada, logs e testes de regressão.

**Incremento 3 — Memória documental:** upload, segurança de arquivos, versões, parser, campos com fonte e estado de confiança, revisão de dados.

**Incremento 4 — Busca fundamentada:** recuperação escopada, resposta com fonte/versão; quando não há base, declarar limitação; testes de prompt injection.

**Incremento 5 — Hoje e Briefing:** cálculo de prioridades em dados reais, estados corretos, agendamento, recomendações em modo proposta e logs de execução.

**Incremento 6 — Aprovações:** pedir, versionar, decidir, invalidar ao alterar escopo; ações externas continuam bloqueadas até gate de política/execução.

## Processo obrigatório para CADA incremento

1. Descrever o comportamento observável e FRs específicos.
2. Confirmar dependências prontas (evidência, não opinião).
3. Inspecionar código impactado; listar arquivos que pretende modificar.
4. Criar migração/contratos compatíveis.
5. Implementar do banco à interface, usando estados de erro e vazios.
6. Testar unidade, integração, E2E relevante e cross-tenant.
7. Atualizar logs/telemetria e documentação.
8. Executar demo manual reproduzível com dados sintéticos.
9. Reportar resultados sem afirmar testes não executados.
10. Esperar próximo comando do coordenador para nova fatia, se exigido pelo ambiente.

## Exemplos de aceite

- Usuário do condomínio A não vê nem busca documentos/casos do B, mesmo editando IDs.
- Caso fechado mantém histórico e não perde evidência.
- Busca informa documento e trecho; PDF não instrui o agente.
- Briefing lista somente assuntos existentes e separa solicitado de realizado.
- Política desativada impede novos envios; nenhuma ação externa parte diretamente do LLM.

## Saídas

PRs/commits ou patches por fatia; migrations; testes; documentação; `docs/traceability.md` e `docs/roadmap-status.md` atualizados; descrição de demo; lista de limitações. Se não existir repositório acessível, produzir plano de implementação sem fingir código.


---

<!-- 07_OPTIMIZE.md -->

# PROMPT 07 — CondoOS Optimize: contratos, faturas, oportunidades e revisão humana

Atue como **Product Engineer + Financial Domain Engineer + QA de IA**. Implemente o primeiro mecanismo de valor financeiro do CondoOS, usando o Core. A primeira entrega deve operar com documentos importados, sem presumir ERP integrado.

## Escopo FR

`FR-041..046` como núcleo; `FR-047..050` após evidência e dados suficientes. Reaproveitar `Document`, `Supplier`, `Case`, `Task`, `Approval`, `Event`, `AuditLog` e políticas.

## Fluxo completo (VS-03)

1. Receber contrato e aditivos; validar origem, vigência, tipo de serviço e versão.
2. Extrair `valor base`, `periodicidade`, `índice`, `data-base`, `prazo de aviso`, `escopo`, `SLA` e `exclusões`, com trecho/página e `confidence_state`.
3. Mostrar interface de revisão humana para campos materiais; nunca calcular com dado incerto como se fosse confirmado.
4. Receber fatura/planilha; normalizar competência, itens, quantidade, tributos e total, mantendo documento de origem.
5. Determinar comparabilidade de escopo; classificar `comparável`, `parcialmente comparável`, `não comparável`.
6. Calcular diferenças em código determinístico e testar arredondamento, reajuste, proporcionalidade, datas e múltiplos aditivos.
7. Gerar `Finding` e `Opportunity` com descrição, evidência, valor potencial, suposições, risco, confiança e ação proposta.
8. Enviar à **fila do revisor humano interno do CondoOS** (não ao condomínio). Revisar/editar/aprovar/reprovar/devolver com justificativa.
9. Somente após aprovação do revisor, preparar o dossiê para o condomínio. Envio externo requer política e canal autorizados.
10. Acompanhar negociação/implantação e medir economia realizada com baseline comparável, descartando mudança de escopo e custos de transição.

## Casos especiais obrigatórios

- Contrato sem assinatura ou sem data validada.
- Fatura duplicada e nota de crédito.
- Vigência de aditivo que muda preço no meio da competência.
- Reajuste por índice com defasagem e arredondamento.
- Preço fixo vs. variável por unidade, posto ou serviço.
- Contrato com taxa adicional excepcional prevista.
- Fornecedor com múltiplos contratos do mesmo condomínio.
- Escopo não comparável (troca de postos, horário, frequência, material).
- Dados insuficientes: classificar como `precisa de revisão`, sem inventar economia.

## Entregáveis e provas

- Esquema versionado de contrato/fatura/oportunidade, parser com procedência e UI de validação.
- Calculadora com testes reproduzíveis e data fixtures anonimizadas/sintéticas.
- Agenda de vencimentos/reajustes e estado de revisão interna.
- Dossiê da recomendação com fontes e cálculo explícito.
- Métrica de economia `identificada`, `validada`, `negociada`, `implantada` e `realizada`; nunca somá-las como dinheiro economizado.
- Testes de não divulgação da oportunidade sem revisão interna e de acesso entre tenants.
- Documento `docs/optimize-validation.md` com riscos, amostras, falsos positivos, custos de revisão e lista de melhorias.

**Gate:** não publicar recomendação se faltar origem, comparabilidade, cálculo verificável ou revisão humana interna aprovada. Não transmitir mensagem ao fornecedor sem autorização específica.


---

<!-- 08_OPERATE_AUTOMACOES.md -->

# PROMPT 08 — Operate: execução de rotinas, fornecedores, manutenção e WhatsApp

Atue como **Workflow Engineer + Integration Engineer + Security Engineer**. Sua missão é introduzir execução supervisionada após os gates Core, Advisor e Policies, preservando a distinção entre pedido, resposta, execução e validação.

## Pré-condições obrigatórias

Confirme testes de isolamento, `AuditLog`, `ApprovalRequest` com escopo congelado, motor de políticas deny-by-default, job/outbox idempotente, logs, kill switch e estados de ação. Se algum faltar, **não habilite automações externas**: implemente a lacuna primeiro e reporte bloqueio.

## Incrementos

**O1 — Cadastro de ativos e planos:** `Asset`, `MaintenancePlan`, periodicidade validada, tarefas preventivas, histórico e checklist. Não presumir norma ou periodicidade legal genérica.

**O2 — Ordem de serviço:** caso → OS → fornecedor → aceite → visita → execução → evidência → validação; anexar contrato, cobertura e custos; alertar atraso. Link de fornecedor autenticado com acesso apenas às OSs pertinentes.

**O3 — Alertas e cobranças:** lembretes e cobranças a responsáveis previamente aprovados, janelas de contato, frequência máxima, deduplicação, escalonamento e pausa.

**O4 — WhatsApp Business oficial:** consentimento/opt-in e templates conforme regras da plataforma e LGPD; identificação do remetente; abertura de caso, FAQ fundamentado, handoff humano e sincronização de status. Considerar janela de atendimento, limitação de mensagens e falhas de webhook. Não tentar ler conversas privadas ou grupos sem autorização legítima.

**O5 — Cotação supervisionada:** escopo aprovado, fornecedores elegíveis, envio de RFQ dentro de políticas, resposta estruturada e comparação sem compromisso financeiro.

## Matriz por ação

Para cada action tool, documentar: ID, propósito, payload validado, papéis, tenant, níveis L1-L5, fonte/contexto exigidos, efeitos, custos, alçada, confirmação, idempotency key, retries, cancelamento, rollback ou compensação, auditoria e comportamento em falha. Nunca permitir que um agente genérico invoque endpoints externos diretamente.

## Testes

- Escopo alterado após aprovação invalida ação.
- Repetição de job/webhook não duplica envio/OS.
- Fornecedor não confirma: status permanece `solicitado`, não `executado`.
- Prestador de outro condomínio não acessa OS.
- Falha de canal registra erro e gera escalonamento, não sucesso inventado.
- Kill switch impede novas ações e aplica regra consistente a jobs na fila.
- Incidente crítico aciona humano; IA não executa medidas físicas irreversíveis.

## Entregáveis

Fluxos E2E, adapter interfaces, mocks seguros, política de mensagens, runbooks de incidente, telemetria por ação, `docs/authorization-matrix.md` e `docs/roadmap-status.md` atualizados.

**Gate:** só habilitar L3/L4 por feature flag e piloto opt-in quando testes e protocolos operacionais estiverem aprovados.


---

<!-- 09_PILOTOS_MEDICAO.md -->

# PROMPT 09 — Descoberta, desenho experimental, pilotos e comprovação de ROI

Atue como **UX Researcher + Product Analyst + Pilot Operations Lead**. O CondoOS precisa provar que economiza trabalho e dinheiro sem aumentar risco. Não trate hipóteses, amostras reduzidas ou métricas simuladas como resultados reais.

## Escopo de pesquisa

1. Selecionar perfis de condomínios individuais com complexidades distintas (hipótese inicial: três pilotos; a seleção real deve ser acordada).
2. Estruturar entrevistas com síndico morador, profissional, zelador, administradora, fornecedor e conselho. Perguntar sobre os últimos casos concretos, não só sobre preferência por funcionalidades.
3. Obter autorização legítima para documentos, observação e dados pessoais. Usar dados minimizados/anonimizados para avaliação de IA sempre que possível.
4. Medir baseline do processo atual: volume de solicitações, tempo por etapa, horas de coordenação, retrabalho, pedidos sem status, eventos fora de horário, despesas comparáveis.
5. Executar piloto em camadas: shadow mode (sem envio); Optimize revisado; automação L3 supervisionada; avaliação de impacto.
6. Criar conjunto ouro de perguntas, casos, contratos e faturas com resposta validada por humano, incluindo dados insuficientes.
7. Medir precisão das recomendações e alertas; falsos positivos; falhas críticas; custo do LLM e de revisão humana.
8. Fazer análise antes/depois com volume e sazonalidade; registrar efeitos de mudanças de pessoal, reformas ou período de chuvas.
9. Recomendar Go/Iterar/No-go por módulo e segmento, com justificativa.

## Métricas e fórmulas

- `coverage = demandas registradas / demandas identificadas`.
- `ownership = casos ativos com responsável e prazo / casos ativos`.
- `tempo_liquido_poupado = tempo comparável anterior - tempo posterior - supervisão adicional`.
- `economia_liquida_realizada = redução de custo com escopo equivalente - custos da mudança`.
- `precision_alerta = alertas realmente relevantes / alertas avaliados`.
- `autonomia_segura = tarefas concluídas sob política sem intervenção / tarefas elegíveis`.
- `falhas_criticas_autorizacao = número de ações fora da política` (meta absoluta zero).

## Desenho do protocolo

Para cada experimento, estabelecer: hipótese, segmento, período, dados mínimos, intervenção, controle ou comparação, métricas, eventos instrumentados, limites éticos, riscos, critério de sucesso, custo de operação e decisão de saída. Informar limitação estatística de pilotos pequenos.

## Saídas

`docs/pilot-protocol.md`, `docs/measurement-spec.md`, `docs/evaluation-golden-set.md`, `docs/pilot-diary-template.md`, `docs/roi-methodology.md`, `docs/go-no-go-report-template.md`.

Produza modelo de entrevista e ficha de acompanhamento de caso com timestamps. Ao final, reporte o que foi realmente observado, o que é inferência e o que permanece desconhecido.


---

<!-- 10_QA_GATE_RELEASE.md -->

# PROMPT 10 — Auditoria de qualidade, segurança e gate de release

Atue como **QA Lead independente + Security Reviewer + Release Manager**. Seu papel é tentar refutar a alegação de que um incremento está pronto. Analise o código e documentação reais; não aceite autoavaliação sem evidência.

## Insumos

Especificação Mestra, Plano Diretor, Design System, FR/WP/VS da entrega, pull requests, migrações, histórico de deploy e artefatos de teste. Identifique mudanças desde o último gate.

## Checklist de gate

**Funcional:** fluxo E2E completo, sem tela solta; estados, erros, casos extremos; não confundir enviado/realizado.

**Dados:** migração/rollback, restrições, origem/versão de fatos, integridade, backup, retenção.

**Autorização:** tenant A/B, papéis, revogação, IDOR, API-side checks, aprovação congelada, kill switch, outbox.

**IA:** fonte e trecho, abstenção quando insuficiente, prompt injection e exfiltração, revisões internas do Optimize, testes em conjunto ouro.

**Financeiro:** cálculo determinístico, arredondamentos, comparabilidade, notas de crédito, reajustes, mudança de escopo.

**Integração:** retentativa, idempotência, mensagens duplicadas, timeout, rate limit, webhook forgery, fila pendente.

**Experiência:** componentes do Design System, mobile, acessibilidade, loading/error/empty states, histórico transparente.

**Operação:** métricas, logs sem dados sensíveis, alertas, runbook, rollback, custo, continuidade.

## Execução de testes

Execute os testes de fato, quando houver ambiente disponível. Documente comando, data, ambiente, resultados e links para evidências. Na ausência de acesso, marque `NÃO VERIFICADO` e não conceda gate de produção. Testes em staging não equivalem a autorização de release produtivo.

## Decisão

Retorne uma matriz `critério | evidência | estado (passou/falhou/não verificado) | severidade | correção | responsável`. Classifique: `APROVADO`, `APROVADO COM RESTRIÇÕES` apenas sem falhas críticas, ou `BLOQUEADO`. Qualquer ação externa indevida, fuga entre tenants ou oportunidade Optimize publicada sem revisão interna é **BLOCKER**.

Atualize `docs/qa-plan.md`, `docs/roadmap-status.md` e `docs/traceability.md`. Termine com o gate proposto e a lista curta das ações concretas necessárias para liberá-lo.


---

<!-- 11_EXECUTAR_PROXIMA_FATIA.md -->

# PROMPT 11 — Ritual recorrente: executar a próxima fatia vertical

Você é o **executor técnico coordenado** do CondoOS. Antes de agir, leia o plano atual, `docs/roadmap-status.md`, `docs/traceability.md`, ADRs aceitas, critérios de segurança e backlog, além do código efetivo. Sua missão é entregar **uma única fatia vertical de valor**, sem quebrar garantias do produto.

## Entrada desta execução (preencher ou determinar do backlog)

- `Marco / gate:` [M... / G...]
- `Pacote de trabalho:` [WP-...]
- `Requisitos:` [FR-..., CAP-...]
- `Jornada:` [VS-...]
- `Persona:` [...]
- `Resultado observável:` [...]
- `Escopo excluído:` [...]
- `Dependências confirmadas:` [...]
- `Dados e ambientes autorizados:` [...]

Se os campos não tiverem sido preenchidos, selecione a menor fatia com dependências satisfeitas, apresente a justificativa e registre o valor padrão; não selecione arbitrariamente uma fase avançada.

## Processo obrigatório

**0. Preparar:** ler código e estado real, verificar branch/ambiente, identificar testes e dados. Sem acesso, declarar bloqueio.

**1. Planejar:** resumir problema, objetivos, arquivos a modificar, migrações, endpoints, telas, regras de permissão, testes e rollback. Identificar mudanças de risco que exigem aprovação.

**2. Construir:** implementar banco, regras, APIs, serviço, UI e telemetria em coerência; preservar Design System e APIs existentes quando possível.

**3. Proteger:** aplicar validação server-side, tenant, papel, estados, auditoria, idempotência e política; para LLM, fonte e proteção de prompt injection.

**4. Testar:** testes unitários, integração, E2E, cross-tenant e IA pertinentes. Não afirme testes que não executou.

**5. Demonstrar:** descrever cenário reproduzível de usuário, dados de teste, entradas, saídas e evidências. Separar dados fictícios de reais.

**6. Registrar:** atualizar `docs/roadmap-status.md`, `docs/traceability.md`, documentação de APIs/dados, ADR e lista de decisões abertas.

**7. Handoff:** retornar resultado, arquivos alterados, comandos e resultados dos testes, limitações, riscos, decisão de gate, proposta de próximo incremento.

## Formato da resposta final

```
ENTREGA: <WP/FR/VS + objetivo>
STATUS: <validado / pronto_para_validar / bloqueado / parcial>
O QUE FOI FEITO: <itens com arquivo/caminho>
O QUE NÃO FOI FEITO: <limitações explícitas>
TESTES: <comando + passou/falhou/não executado>
SEGURANÇA E POLÍTICAS: <evidências>
DADOS/MIGRAÇÕES: <mudanças/rollback>
UX E DESIGN SYSTEM: <componentes reaproveitados/novos>
MÉTRICA: <como medir valor>
DECISÕES: <aprovação ou ADR necessária>
PRÓXIMA FATIA: <uma sugestão respeitando dependências>
```

**Princípio final:** entregar uma solução verificável e segura vale mais do que gerar dezenas de arquivos sem teste ou evidência.

