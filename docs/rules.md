# Regras de auditoria v1

As regras são **determinísticas**: com os mesmos dados, produzem os mesmos achados. O LLM só entra em R04 e R07, sempre com saída estruturada e justificativa, e o achado fica marcado como "assistido por IA" (`finding.ai_assisted = true`).

Cada regra é uma classe em `api/app/rules/` com `code`, `name`, `default_severity`, `params` (ajustáveis por condomínio em `condominium.rule_params`) e `evaluate(context) -> list[FindingDraft]`. Os números usados pela regra vão para `finding.rule_inputs`. A explicação gerada pelo LLM só pode citar esses números.

**Linguagem:** nunca "fraude", "desvio" ou "irregularidade comprovada". Usar "indício", "divergência", "ponto de atenção".

> Status: especificação. A implementação e os testes de cada regra entram no Marco 3. Este documento será atualizado com os detalhes finais de cada cálculo.

| Código | Regra | Lógica | Parâmetros padrão | Severidade | Valor em risco |
| --- | --- | --- | --- | --- | --- |
| R01 | Pagamento duplicado | Duas despesas do mesmo CNPJ com valor dentro de ±`tolerance_pct`% em até `window_days` dias, ou o mesmo número de nota pago duas vezes | `tolerance_pct=1`, `window_days=45` | alta | Valor da despesa duplicada (a segunda ocorrência) |
| R02 | Valor acima do contrato | Valor pago > valor mensal do contrato reajustado pelo índice acumulado até a competência, + `tolerance_pct`% | `tolerance_pct=2` | média | Valor pago − valor contratual reajustado, somado no período |
| R03 | Reajuste fora do índice | Aumento aplicado no mês-base > variação acumulada de 12 meses do índice + `tolerance_pp` p.p. | `tolerance_pp=0.5` | média | (valor pago − valor com o reajuste do índice) × meses pagos desde o mês-base |
| R04 | Serviço fora do escopo | Item da discriminação da nota não corresponde a nenhum `scope_items` do contrato (LLM, confiança ≥ `min_confidence`) | `min_confidence=0.8` | média | Valor da despesa |
| R05 | Contrato vencido | Data do débito casado (ou o vencimento, sem casamento) posterior a `contract.end_date` | — | média | Valor da despesa |
| R06 | Fornecedor irregular | Situação cadastral diferente de "ATIVA" na data da despesa | — | alta | Valor da despesa |
| R07 | CNAE incompatível | Nenhuma atividade (principal ou secundária) do CNPJ cobre o serviço cobrado (LLM, confiança ≥ `min_confidence`) | `min_confidence=0.8` | baixa | Valor da despesa |
| R08 | Conflito de interesse | Nome completo de sócio do fornecedor igual ao de um membro de `board_member` com mandato vigente na data da despesa (sem acentos, sem diferença de caixa, espaços normalizados) | — | alta | Soma paga ao fornecedor no período analisado |
| R09 | Pago sem nota | Débito no extrato sem documento fiscal casado depois de `grace_days` dias | `grace_days=10` | média | Valor do débito |
| R10 | Nota sem pagamento | Documento vencido há mais de `grace_days` dias sem débito correspondente | `grace_days=10` | baixa | Valor da despesa |
| R11 | Variação anômala | Gasto da categoria no mês > média + `sigma` desvios-padrão dos 12 meses anteriores; exige pelo menos `min_months` meses de histórico | `sigma=2`, `min_months=6` | baixa | Gasto do mês − (média + `sigma` × desvio) |
| R12 | Quebra de alçada | Despesa acima do limite em `approval_limits` (por categoria; senão o padrão) sem linha em `approval` | — | média | Valor da despesa |

## Notas de cálculo

- **Índice acumulado (R02, R03):** produto de (1 + variação mensal) dos 12 meses anteriores ao mês-base, com dados de `index_value` (série SGS do Banco Central). Contratos `FIXO` ou `NENHUM` usam variação zero.
- **R11:** o valor em risco é o excesso sobre o limite, não o gasto inteiro, porque o gasto normal da categoria não está em questão.
- **R01:** a primeira despesa é tratada como legítima; a duplicada é a de data de emissão mais recente (empate: maior id).
- Achados de severidade alta vão para `aguardando_validacao`; média e baixa vão direto para `publicado` (seção 7 do prompt).
