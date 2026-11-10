# Regras de auditoria v1

As regras são **determinísticas**: com os mesmos dados, produzem os mesmos achados. A IA só entra em R04 e R07, sempre com saída estruturada e justificativa, e o achado fica marcado como "assistido por IA" (`finding.ai_assisted = true`). Sem IA disponível, essas verificações são registradas como "não avaliadas" e nunca adivinhadas.

Código: uma classe por regra em `api/app/rules/rNN_*.py`. Cada uma tem `code`, `name`, `default_severity`, `default_params` (ajustáveis por condomínio em `condominium.rule_params[código]`) e `evaluate(contexto) -> list[FindingDraft]`. O motor fica em `api/app/rules/engine.py`.

**Linguagem:** nunca "fraude", "desvio" ou "irregularidade comprovada". Use "indício", "divergência" e "ponto de atenção". O motor recusa um achado que contenha essas palavras; foi assim que "média + 2 desvios" virou "variação típica" no R11.

**Roteamento:** severidade alta começa em `aguardando_validacao` (o gerente valida antes de o síndico ver). Média e baixa começam em `publicado`.

**Idempotência:** cada achado tem uma chave estável (`dedupe_key`). Rodar de novo atualiza números e evidências, mas nunca muda um status definido por uma pessoa.

**Data de referência:** o "hoje" das carências (R09, R10) é a data em que o motor roda. No seed e nos testes, é 05/11/2026.

| Código | Regra | Lógica implementada | Parâmetros padrão | Severidade | Valor em risco |
| --- | --- | --- | --- | --- | --- |
| R01 | Pagamento duplicado | Duas despesas do mesmo CNPJ com valores dentro de ±`tolerance_pct`% emitidas a até `window_days` dias **na mesma competência**, ou o mesmo número de nota pago duas vezes (qualquer mês). A duplicata é a de emissão mais recente. | `tolerance_pct=1`, `window_days=45` | alta | Valor da duplicata |
| R02 | Valor acima do contrato | Valor pago > valor mensal reajustado pelo índice do contrato até a competência × (1 + `tolerance_pct`%). No mês de reajuste de contrato indexado, quem julga é o R03. | `tolerance_pct=2` | média | Pago − valor reajustado |
| R03 | Reajuste fora do índice | No mês-base (aniversário) de contrato IPCA/IGP-M/INPC: reajuste aplicado sobre o mês anterior − índice acumulado nos 12 meses antes do mês-base > `tolerance_pp` p.p. | `tolerance_pp=0.5` | média | Pago − anterior × (1 + índice), no mês |
| R04 | Serviço fora do escopo | Primeiro uma checagem por palavras: se o serviço cobrado compartilha ≥ 50% das palavras significativas com o objeto ou com um item do escopo, está dentro. Senão, a IA julga, com justificativa; achado só com "fora" e confiança ≥ `min_confidence`. | `min_confidence=0.8` | média | Valor da despesa |
| R05 | Contrato vencido | Data do pagamento (débito casado; sem débito, o vencimento; sem vencimento, a emissão) posterior ao fim da vigência. | — | média | Valor da despesa |
| R06 | Fornecedor irregular | Situação cadastral diferente de "ATIVA" com data de situação até a data de emissão da despesa. | — | alta | Valor da despesa |
| R07 | CNAE incompatível | Para categorias mapeadas, consulta à tabela de classes CNAE compatíveis (`matching/categories.py`), sem IA. Para categorias sem mapa, a IA julga com justificativa (confiança ≥ `min_confidence`). Um achado por fornecedor e categoria no mês. | `min_confidence=0.8` | baixa | Soma das despesas do fornecedor na categoria no mês |
| R08 | Conflito de interesse | Nome completo de um sócio (QSA) igual ao de um membro do corpo diretivo (`board_member`) com mandato cobrindo a data da despesa. Acentos, caixa e espaços são ignorados; nome parcial não conta. | — | alta | Total pago ao fornecedor nos 12 meses até a competência |
| R09 | Pago sem nota | Débito do mês sem despesa casada, ou casado com despesa sem número de nota e sem documento fiscal ou recibo, passados `grace_days` dias. Ignora tarifas, IOF, juros, aplicações e resgates. Conta de concessionária (energia, água, gás) casada com a despesa vale como documento fiscal (D62). | `grace_days=10` | média | Valor do débito |
| R10 | Nota sem pagamento | Despesa do mês vencida há mais de `grace_days` dias sem débito casado. | `grace_days=10` | baixa | Valor da despesa |
| R11 | Variação anômala | Gasto da categoria no mês > média + `sigma` × desvio-padrão dos meses anteriores (até 12, só meses com gasto, mínimo `min_months`). **Despesas de contrato ficam fora**: contratos são auditados por R02, R03 e R05. | `sigma=2`, `min_months=6` | baixa | Gasto acima do limite |
| R12 | Quebra de alçada | Despesa acima do limite de `approval_limits` (por categoria, senão o padrão) sem linha em `approval`. Despesas de contrato (aprovadas na assinatura) e categorias isentas não são verificadas. | `exempt_categories=["energia","agua","gas","tributos"]` | média | Valor da despesa |

## Notas de cálculo

- **Valor contratual reajustado** (`rules/contracts.py`): o primeiro reajuste é no mês-base, pelo menos 12 meses após o início; depois, a cada 12 meses. Em cada aniversário, valor × (1 + índice acumulado nos 12 meses anteriores), arredondado ao centavo. Contratos `FIXO` e `NENHUM` não mudam. Se faltar um mês do índice, a regra registra "não avaliada" em vez de supor.
- **Índices:** séries reais do Banco Central (SGS 433 IPCA, 189 IGP-M, 188 INPC), em `index_value`. O seed usa `app/seed/fixtures/bcb_indices.json` (jan/2020 a out/2026), e o worker atualiza uma vez por dia.
- **Por que o R01 exige a mesma competência:** um contrato mensal paga o mesmo valor todo mês, a 30 dias de distância. Sem essa condição, todo contrato viraria "duplicidade" mensal.
- **Por que o R11 exclui contratos e mede o excesso:** o gasto normal da categoria não está em questão; o reajuste de um contrato já é julgado por R02 e R03.
- **Por que o R12 isenta contratos e contas de consumo:** o contrato é aprovado quando assinado; água, luz e gás são cobranças obrigatórias de concessionária. As isenções são configuráveis por condomínio.

## Casos plantados no seed (outubro/2026)

O teste `tests/test_planted_cases.py` exige que o motor encontre exatamente estes achados e nenhum outro.

| Regra | Positivo | Negativo |
| --- | --- | --- |
| R01 | Hidráulica: duas notas de R$ 3.400,00 no mesmo mês | Pagamentos mensais iguais dos contratos |
| R02 | Portaria do Jardim das Acácias R$ 1.850,00 acima do reajustado | Limpeza no valor exato |
| R03 | Elevadores do Mirante: reajuste de 9% contra o IGP-M | Coberto nos testes unitários |
| R04 | Pintura da fachada cobrada no contrato de limpeza (precisa da IA) | Troca de botoeira em "atendimento a chamados" |
| R05 | Bombas de recalque pagas após o fim do contrato (31/08/2026) | Limpeza dentro da vigência |
| R06 | Reforma Rápida, CNPJ baixado desde 10/05/2026 | Vidraçaria inapta só a partir de 01/12/2026 |
| R07 | Loja de roupas cobrando manutenção elétrica | Empresas elétricas e hidráulicas na manutenção |
| R08 | Sócia da Jardins & Cia é conselheira do Jardim das Acácias | Sócio com nome parcial; síndica do *outro* condomínio |
| R09 | PIX de R$ 2.300,00 sem nota | Tarifa bancária; PIX dentro da carência |
| R10 | Interfone vencido em 20/10 sem débito | Lâmpadas com vencimento em 02/11 (carência) |
| R11 | Conta de água três vezes a média | Energia e gás normais |
| R12 | Portão de R$ 6.000,00 acima da alçada de obras | Grades de R$ 7.000,00 com aprovação em assembleia |
