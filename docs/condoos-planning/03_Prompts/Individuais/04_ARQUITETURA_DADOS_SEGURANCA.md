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
