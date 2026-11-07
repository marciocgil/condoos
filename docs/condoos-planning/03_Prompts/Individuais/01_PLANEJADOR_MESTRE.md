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
