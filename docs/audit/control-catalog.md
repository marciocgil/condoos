# Catálogo dos 25 controles (CondoOS Audit)

Gerado de `api/app/audit/catalog.py` (fonte única). IDs estáveis em todas as competências. Ciclo atual: 2. Controle sem teste implementado fica **Não avaliado** com o ciclo previsto; nunca vira verde por ausência.

## Seis estados

| Estado | Quando |
|---|---|
| Validado | Todos os testes obrigatórios passaram, fontes suficientes, nenhuma divergência aberta. |
| Com ressalva | Resultado utilizável, com o limite descrito no motivo. |
| Pendente | Falta evidência essencial; o motivo diz exatamente o que falta. |
| Divergente | Incompatibilidade verificada, com diferença em centavos. Sempre vai para revisão humana. |
| Não avaliado | Teste não executado (ainda não existe ou falhou). Não conta como concluído. |
| Não aplicável | O evento não ocorreu no período, com motivo objetivo (ex.: extrato recebido sem estornos). |

A política da A9 (código) barra "Validado" sem todos os testes passados e sem evidência. Divergência ou diferença em centavos marca revisão humana (`NEEDS_HUMAN_REVIEW`). Revisão humana pode confirmar ou reclassificar com motivo (novo resultado, o anterior fica como substituído); "Validado" não pode ser dado a um controle Pendente ou Não avaliado sem a fonte que falta.

## Documental

### DOC-01 — Integridade do acervo do mês

- Ciclo: 1 · versão da regra: 1.0 · agentes: A1, A2, A9
- Fontes obrigatórias: documentos do mês; extrato de cada conta conhecida
- Depende de (grafo de reprocessamento): documentos, extrato
- Critérios de Validado:
  - Há documentos recebidos para a competência.
  - Cada conta conhecida tem extrato que cobre o mês.
  - Todos os documentos foram lidos (nenhum ilegível ou aguardando correção).
  - Cópias e versões ficam registradas, nunca descartadas.

### DOC-02 — Comprovação de lançamentos

- Ciclo: 1 · versão da regra: 1.0 · agentes: A1, A2, A9
- Fontes obrigatórias: despesas do mês; documento fiscal, recibo ou guia de cada despesa
- Depende de (grafo de reprocessamento): despesas, documentos
- Critérios de Validado:
  - Toda despesa do mês tem documento fiscal, recibo ou guia.
  - Ter documento não prova pagamento válido (isso é DES-01).

### DOC-03 — Aprovação formal das contas

- Ciclo: 3 · versão da regra: — · agentes: A7, A9
- Fontes obrigatórias: termo, ata ou decisão de aprovação
- Depende de (grafo de reprocessamento): documentos, aprovacoes
- Critérios de Validado:
  - Aprovação com signatários, data, abrangência e poderes.

## Bancário

### BAN-01 — Saldo bancário recalculado

- Ciclo: 1 · versão da regra: 1.0 · agentes: A4, A8
- Fontes obrigatórias: extrato com saldo inicial e final de cada conta; saldo contábil do demonstrativo
- Depende de (grafo de reprocessamento): extrato, saldos
- Parâmetros: tolerancia: R$ 0,00 (exatidão centesimal)
- Critérios de Validado:
  - Saldo inicial + créditos − débitos = saldo final, ao centavo, em cada conta.
  - Todas as contas conhecidas têm extrato com saldos declarados.
  - Saldo do extrato confere com o saldo contábil do demonstrativo.

### BAN-02 — Continuidade entre meses

- Ciclo: 1 · versão da regra: 1.0 · agentes: A4, A8
- Fontes obrigatórias: extrato do mês anterior e do mês, por conta
- Depende de (grafo de reprocessamento): extrato, saldos
- Parâmetros: tolerancia: R$ 0,00
- Critérios de Validado:
  - O saldo de abertura do mês é igual ao de fechamento do mês anterior, em cada conta.
  - Ajustes e transferências entre os dois saldos explicados.

### BAN-03 — Débitos bancários identificados

- Ciclo: 1 · versão da regra: 1.0 · agentes: A4, A3
- Fontes obrigatórias: extrato do mês
- Depende de (grafo de reprocessamento): extrato, despesas, pagamentos
- Critérios de Validado:
  - 100% dos débitos ligados a uma despesa ou classificados como movimento que não é despesa (tarifa, IOF, aplicação, transferência entre contas, estorno).
  - Pagamentos a intermediário ficam marcados como indiretos.

### BAN-04 — Créditos bancários identificados

- Ciclo: 1 · versão da regra: 1.0 · agentes: A4, A5
- Fontes obrigatórias: extrato do mês
- Depende de (grafo de reprocessamento): extrato
- Critérios de Validado:
  - 100% dos créditos classificados (arrecadação, rendimento, resgate, transferência, estorno ou empréstimo).
  - Transferência e estorno nunca contam como receita operacional.

### BAN-05 — Estornos e tentativas

- Ciclo: 1 · versão da regra: 1.0 · agentes: A4
- Fontes obrigatórias: extrato do mês
- Depende de (grafo de reprocessamento): extrato, pagamentos
- Parâmetros: janela_dias: 10
- Critérios de Validado:
  - Cada estorno ou devolução tem o débito original pareado (mesmo valor, até 10 dias antes).
  - O débito devolvido não é contado como pagamento de despesa.

### BAN-06 — Transferências entre contas

- Ciclo: 2 · versão da regra: 1.0 · agentes: A4
- Fontes obrigatórias: extratos das contas de origem e destino
- Depende de (grafo de reprocessamento): extrato
- Parâmetros: janela_dias: 3
- Critérios de Validado:
  - Cada transferência tem a contrapartida na outra conta (mesmo valor, sinal oposto, até 3 dias).
  - Transferência de ou para conta não apresentada fica com ressalva: crédito recebido não é origem comprovada.

### BAN-07 — Pagamentos por intermediário

- Ciclo: 2 · versão da regra: 1.0 · agentes: A4, A6
- Fontes obrigatórias: comprovante de liquidação ao favorecido final
- Depende de (grafo de reprocessamento): extrato, pagamentos, documentos
- Critérios de Validado:
  - Todo pagamento feito por intermediário (administradora, plataforma de cobrança) tem comprovante cujo beneficiário final é o fornecedor da despesa (CNPJ).
  - Saída ao intermediário não é liquidação final comprovada.

### BAN-08 — Lastro dos fundos

- Ciclo: 3 · versão da regra: — · agentes: A8
- Fontes obrigatórias: saldos por fundo e contas de suporte
- Depende de (grafo de reprocessamento): fundos, saldos
- Critérios de Validado:
  - Cada fundo com lastro próprio demonstrado, não pela soma do consolidado.

### BAN-09 — Aplicações e rendimentos

- Ciclo: 3 · versão da regra: — · agentes: A4, A8
- Fontes obrigatórias: extrato próprio da aplicação
- Depende de (grafo de reprocessamento): extrato, fundos
- Critérios de Validado:
  - Aportes, resgates, IR/IOF, rendimentos e saldos conciliados.

## Arrecadação

### REC-01 — Receitas efetivas

- Ciclo: 1 · versão da regra: 1.0 · agentes: A5, A4
- Fontes obrigatórias: extrato do mês; demonstrativo de receitas
- Depende de (grafo de reprocessamento): extrato, receitas, documentos
- Critérios de Validado:
  - Créditos de arrecadação conferem com o demonstrativo de receitas.
  - Transferências e estornos separados da receita.
  - Todos os créditos classificados (BAN-04).

### REC-02 — Boletos por unidade

- Ciclo: 2 · versão da regra: 1.0 · agentes: A5
- Fontes obrigatórias: títulos emitidos por unidade; extrato ou retorno de cobrança
- Depende de (grafo de reprocessamento): unidades, receitas, extrato
- Parâmetros: janela_credito_dias: 3
- Critérios de Validado:
  - Toda unidade cadastrada tem título na competência.
  - Nenhum título repetido (mesma unidade, tipo e competência).
  - Todo título pago tem confirmação: liquidação no retorno de cobrança (nosso número) ou crédito do extrato cujo valor fecha a soma dos pagamentos do dia.

### REC-03 — Consumo e rateios

- Ciclo: 2 · versão da regra: 1.0 · agentes: A5
- Fontes obrigatórias: fatura da concessionária; rateio por unidade; leituras por unidade
- Depende de (grafo de reprocessamento): unidades, despesas, receitas
- Parâmetros: arredondamento_por_unidade: R$ 0,01
- Critérios de Validado:
  - A soma do rateio por unidade é igual à fatura do consumo, ao centavo.
  - Com leituras: cada unidade paga fatura × consumo da unidade ÷ consumo total, com diferença de no máximo R$ 0,01 por arredondamento.
  - Sem leituras: só a aritmética é validada; a medição fica pendente (ressalva).

### REC-04 — Inadimplência

- Ciclo: 2 · versão da regra: 1.0 · agentes: A5
- Fontes obrigatórias: títulos por unidade com situação de pagamento
- Depende de (grafo de reprocessamento): unidades, receitas
- Critérios de Validado:
  - Saldo em aberto no início + títulos vencidos no mês − pagamentos − cancelamentos = saldo em aberto no fim, por unidade.
  - Título marcado como pago tem data e valor pagos; pagamento parcial fica em aberto pela diferença.
  - "Não há inadimplentes" só depois de reconciliar os títulos em aberto.

## Despesas e fiscal

### DES-01 — Despesas liquidadas

- Ciclo: 1 · versão da regra: 1.0 · agentes: A6, A4, A3
- Fontes obrigatórias: despesas do mês com documento; débito bancário de cada pagamento
- Depende de (grafo de reprocessamento): despesas, pagamentos, documentos
- Parâmetros: tolerancia: R$ 0,00
- Critérios de Validado:
  - Toda despesa vencida no mês tem documento e débito bancário ligado.
  - O valor pago é igual ao valor da despesa, ao centavo.
  - Pagamento a intermediário fica com ressalva até a liquidação final.

### DES-02 — Tributos retidos e guias federais

- Ciclo: 2 · versão da regra: 1.0 · agentes: A6
- Fontes obrigatórias: retenções das notas da competência; guia federal (DARF) da competência paga
- Depende de (grafo de reprocessamento): tributos, documentos, pagamentos
- Critérios de Validado:
  - Soma das retenções federais (IR, PIS, COFINS, CSLL) das notas da competência = soma das guias federais da competência, ao centavo.
  - Cada guia tem débito bancário ligado.
  - Alíquotas não são calculadas: só a aritmética entre notas, guia e pagamento.

### DES-03 — Encargos e tributos periódicos

- Ciclo: 2 · versão da regra: 1.0 · agentes: A6
- Fontes obrigatórias: perfil de auditoria; guias FGTS, INSS/DCTFWeb e ISS da competência
- Depende de (grafo de reprocessamento): tributos, pagamentos
- Critérios de Validado:
  - Com funcionários próprios: guia de FGTS e de INSS/DCTFWeb da competência.
  - Com ISS retido nas notas: guia de ISS da competência com o total retido.
  - Cada guia vencida tem débito bancário; guias de meses anteriores pagas no mês aparecem separadas.

### DES-04 — Parcelamento fiscal

- Ciclo: 2 · versão da regra: 1.0 · agentes: A6
- Fontes obrigatórias: perfil de auditoria; guias das parcelas
- Depende de (grafo de reprocessamento): tributos, pagamentos
- Critérios de Validado:
  - Parcelas numeradas em sequência, com o mesmo total (02/04 depois de 01/04).
  - Total diferente entre parcelas (02/02 e depois 03/04) exige documento do novo acordo: fica com ressalva até ser apresentado.
  - Cada parcela vencida tem débito bancário.

## Contratos

### CON-01 — Contrato vigente e preço

- Ciclo: 3 · versão da regra: — · agentes: A7
- Fontes obrigatórias: contrato aplicável à competência
- Depende de (grafo de reprocessamento): contratos, despesas
- Critérios de Validado:
  - Valor bruto, escopo e reajuste conferidos com a nota.

### CON-02 — Serviço extraordinário e aceite

- Ciclo: 3 · versão da regra: — · agentes: A7
- Fontes obrigatórias: proposta, autorização, ordem de serviço e aceite
- Depende de (grafo de reprocessamento): contratos, aprovacoes
- Critérios de Validado:
  - Autorização dentro da alçada e serviço fora do escopo recorrente.

### CON-03 — Parcelas contratuais

- Ciclo: 3 · versão da regra: — · agentes: A7
- Fontes obrigatórias: cronograma e pagamentos
- Depende de (grafo de reprocessamento): contratos, pagamentos
- Critérios de Validado:
  - Sequência, total e saldo futuro coerentes.

## Governança

### GOV-01 — Orçado × realizado e caixa

- Ciclo: 3 · versão da regra: — · agentes: A8
- Fontes obrigatórias: orçamento aprovado
- Depende de (grafo de reprocessamento): orcamento, despesas
- Critérios de Validado:
  - Desvios explicados e projeção com premissas declaradas.

### GOV-02 — Seguros e obrigações técnicas

- Ciclo: 3 · versão da regra: — · agentes: A7, A8
- Fontes obrigatórias: apólice, AVCB, laudos
- Depende de (grafo de reprocessamento): obrigacoes
- Critérios de Validado:
  - Vigência na competência e plano de renovação.

## Classificação de lançamentos (classificacao_v1)

Primeira regra que casa vale. Débito ligado a uma despesa (direto ou por alocação verificada) é sempre "Pagamento de despesa". PIX ou depósito sem identificação fica só como indício. Linhas de retorno de cobrança (CNAB) não entram como lançamento do extrato: servem de confirmação dos títulos (REC-02).

| Lado | Classificação | Padrão |
|---|---|---|
| débito | Estorno ou devolução | `estorno|devolu` |
| débito | Tarifa bancária | `tarifa|cesta de servi|pacote de servi|manuten[cç][aã]o de conta` |
| débito | Tributo bancário (IOF/IR) | `\biof\b|\birrf\b s/ ?aplic` |
| débito | Juros ou encargos | `\bjuros\b|encargos|\bmulta\b` |
| débito | Aplicação | `aplica[cç][aã]o|\binvest` |
| débito | Transferência entre contas | `mesma titularidade|entre contas|transf\.? (?:p/|para) conta pr[oó]pria` |
| crédito | Estorno ou devolução | `estorno|devolu` |
| crédito | Rendimento | `rendimento|rend\.? pago|remunera[cç][aã]o` |
| crédito | Resgate de aplicação | `resgate` |
| crédito | Empréstimo | `empr[eé]stimo|m[uú]tuo` |
| crédito | Transferência entre contas | `mesma titularidade|entre contas|transf|ted receb|doc receb` |
| crédito | Arrecadação (cotas e boletos) | `cobran|liquida[cç][aã]o|boleto|taxas? condom|cotas? condom|arrecada` |
