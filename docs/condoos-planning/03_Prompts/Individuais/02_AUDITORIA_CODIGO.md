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
