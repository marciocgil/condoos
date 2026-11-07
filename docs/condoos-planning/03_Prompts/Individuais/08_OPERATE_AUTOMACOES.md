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
