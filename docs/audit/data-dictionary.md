# CondoOS Audit — dicionário de dados (migração 0029)

Todas as tabelas de condomínio têm `condominium_id`, RLS por condomínio e consultas sempre filtradas. Valores em `Numeric(14,2)` (`Decimal`, centavos exatos), nunca `float`.

| Tabela | Para quê | Campos principais | Cardinalidade e regras |
|---|---|---|---|
| `bank_account` | Conta do condomínio, como o extrato a identifica | banco, agência, número, rótulo, tipo | 1 por (condomínio, banco, agência, número) |
| `bank_statement` | Um arquivo de extrato importado | conta, documento, período, saldo inicial e final **como o arquivo declara** (vazio se não declara), origem do saldo, formato | 1 por documento; N por conta |
| `bank_transaction` (+2 colunas) | Lançamento | `bank_account_id`, `statement_id` (vazios em importações antigas) | idempotente por `external_id` |
| `audit_period` | Mês auditado | competência | 1 por (condomínio, mês) |
| `audit_run` | Execução do A0 | número, gatilho, status, resumo (versões de prompt e de regra usadas) | N por período |
| `audit_stage_run` | Etapa 1–8 de uma execução | etapa, status, detalhe | 8 por execução |
| `audit_agent_run` | Trabalho de um agente | agente, `prompt_version_id`, `runtime_prompt_sha256`, `llm_invoked`, modelo, entradas, saída, não resolvidos, avisos, duração | N por execução |
| `audit_control_result` | Avaliação de um controle | controle, versão da regra, status (6), estado de revisão (4), testes, evidências, cobertura, diferença, motivo, o que falta, impressão digital das entradas, agentes participantes, origem (motor ou revisão), `superseded_by_id` | só um atual por (período, controle); o anterior nunca é apagado |
| `audit_control_review` | Revisão humana (só inclusão) | decisão, motivo, de → para, pessoa | N por resultado |
| `audit_fact` | Fato lido de um documento (só inclusão) | campo, valor bruto e normalizado, competência, página, trecho, método, versão do extrator, confiança, verificação, vigência (`effective_from/to`), `recorded_at` | 1 por impressão digital; leitura nova = fato novo |
| `evidence_edge` | Vínculo entre registros | de (tipo, id) → para (tipo, id), sugerido ou verificado, método, motivo, valor | N:N; sugerido vira verificado só por regra objetiva ou pessoa |
| `agent_prompt_version` | Versão imutável do prompt de um agente (plataforma) | agente, versão, status (DRAFT, IN_REVIEW, ACTIVE, ARCHIVED), texto, SHA-256, papel do modelo, configuração, origem, nota da mudança, autor, aprovador, datas | só uma ACTIVE por agente; o texto nunca muda |
| `agent_prompt_event` | Histórico da versão (só inclusão) | tipo (rascunho, testada, enviada, aprovada, ativada, arquivada, rollback, descartada), pessoa, detalhe | N por versão |
| `prompt_test_run` | Teste no sandbox (só inclusão) | passou, resultados por verificação | N por versão |

## Ciclo 2 (migração 0030, D123)

| Tabela | Para quê | Campos principais | Regras |
|---|---|---|---|
| `unit` | Unidade (dado interno) | código, bloco, fração, documento de origem | 1 por (condomínio, código); **sem nome de morador** |
| `receivable_title` | Título (boleto) da unidade | competência, competência do consumo, tipo, valor, vencimento, nosso número, situação, pagamento (data e valor), cancelamento, chave de importação | importar de novo atualiza a situação, não duplica |
| `utility_reading` | Consumo da unidade | competência, serviço (água, gás, energia), leituras, consumo | 1 por (unidade, competência, serviço) |
| `payment_allocation` | Lançamento ↔ despesa, com valor | valor, verificada ou sugerida, método, motivo | N:N; soma nunca passa do lançamento nem da despesa |
| `audit_issue` | Pendência da auditoria | controle, assunto, título, situação, primeira e última competência | 1 por (condomínio, controle, assunto); reabre com o mesmo id |
| `audit_issue_event` | Histórico da pendência (só inclusão) | aberta, reaberta, resolvida; competência; execução | N por pendência |
| `audit_control_result.calculation` | Memória de cálculo | linhas (rótulo, valor, fórmula) e linhas por item | — |

O que o documento-mestre lista e fica para os ciclos seguintes: fundos, orçamento e plano de contas, obrigações e alocações de pagamento N:N com valor, parcelamentos, tributos agrupados, aprovações formais das contas.
