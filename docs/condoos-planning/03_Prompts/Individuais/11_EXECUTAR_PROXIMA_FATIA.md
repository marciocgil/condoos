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
