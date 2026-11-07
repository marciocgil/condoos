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
