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
