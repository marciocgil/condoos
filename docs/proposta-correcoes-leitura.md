# Proposta: correções na leitura e na conferência de documentos

Data: 10/11/2026. **Aguardando decisão do Marcio.** Nada foi implementado. Origem: os testes do Marcio com vários documentos (contratos 1024_5, 1025_6, 1054_7, 1058_11, 1060_13, 1061_14, comprovante p056 e outros).

## 1. Diagnóstico

| # | O que aconteceu | Causa no código |
|---|---|---|
| 1 | Quase todo contrato vai para revisão, mesmo com 80% ou mais | A regra do projeto manda para a fila **todo campo obrigatório abaixo de 90%** (`extraction/confidence.py`, `REVIEW_THRESHOLD = 0.9`). Nos contratos, a IA costuma dar entre 80% e 89% para objeto, escopo e razão social. O sistema não usa nenhuma evidência para subir essa confiança, mesmo quando o valor está escrito no documento ou confere com a Receita. |
| 2 | 1054_7: "Qual índice" e "Fim da vigência" aparecem como "não encontrado" | Esses dois campos **não** são obrigatórios e não mandam para a fila. O documento foi para a revisão pelos campos obrigatórios abaixo de 90% (item 1). A tela de correção mostra os opcionais vazios do mesmo jeito que os pendentes, o que confunde. |
| 3 | 1024_5: assinatura em 05/09/2024, depois do início da vigência (18/11/2023) | Não existe essa verificação. Hoje só se confere se o fim vem antes do início. |
| 4 | 1025_6: o contratante no documento é a administradora (Manager), não o condomínio | O sistema baixa a confiança e manda para a fila. Quando a pessoa digita o CNPJ do condomínio para liberar, **o que estava escrito no documento se perde**: não fica observação nem alerta. |
| 5 | 1060_13: o CNPJ do condomínio está errado no próprio contrato | O mesmo do item 4: a correção na tela apaga a divergência, e ninguém é avisado de que o contrato precisa ser corrigido. |
| 6 | 1058_11: não achou o CNPJ da contratada, que está no documento | A IA deixou o campo vazio e não há conferência por código. Causa provável: o CNPJ está numa parte que a IA não destacou (cabeçalho, rodapé, bloco de assinaturas ou anexo). Hoje não existe busca por código de CNPJs válidos no texto. |
| 7 | 1061_14: o contrato não tem CNPJ da contratada | Campo obrigatório: sem ele, o documento fica na fila e não há caminho alternativo. |
| 8 | Contrato pontual tratado como recorrente | O modelo de contrato só conhece **valor mensal**, reajuste e NF esperada todo mês (`pending.py`). Um serviço pontual (obra, reparo, laudo) acaba pedindo índice e gerando "NF não recebida" nos meses seguintes. |
| 9 | p056: o comprovante pegou o banco como beneficiário | Não existe o tipo "comprovante de pagamento": ele cai em boleto ou conta e é lido com os campos de boleto, em que "beneficiário" é quem emite o boleto, às vezes o banco. |
| 10 | A mesma NF enviada duas vezes, com nomes diferentes, gerou alerta de pagamento duplicado | Arquivos idênticos já são reconhecidos (pelo conteúdo, não pelo nome). Aqui os dois arquivos eram diferentes por dentro (baixados duas vezes, por exemplo) e, provavelmente, em um deles o número da nota saiu diferente (zeros à esquerda, série) ou vazio. Por isso virou uma segunda despesa, e a regra R01 apontou duplicidade. |
| 11 | Documentos sem classificação | Faltam tipos: comprovante de pagamento, guia de tributo (DARF, GPS/DCTFWeb, FGTS, ISS), relatório da administradora e extrato de rendimento. Sem o tipo "guia de tributo", o pagamento de imposto aparece no extrato **sem nota** e a regra R09 pode apontar indevidamente. |

## 2. O que propomos

### Parte A: sem mudança no banco (pode começar já)

| # | Mudança | Resolve |
|---|---|---|
| A1 | **Confiança por evidência.** Um campo sobe para "confirmado" (95%) quando há prova por código: **o valor está escrito no documento** (o trecho já é guardado na proveniência, D85); a **razão social confere com a da Receita** para aquele CNPJ; o **CNPJ do condomínio confere** com o cadastro. Sem prova, vale a confiança da IA, e abaixo de 90% continua indo para a fila. Nada "chutado". | 1, 2 |
| A2 | **Tela de correção mais clara:** campos opcionais vazios aparecem como "opcional, não encontrado", separados dos pendentes, e cada pendente diz por que está ali. | 2 |
| A3 | **Busca de CNPJ por código:** procurar no texto todos os CNPJs válidos, tirar o do condomínio e o da administradora; se sobrar um só e a IA não achou, ele entra como sugestão "lida do texto", confirmada se a razão social conferir na Receita. | 6 |
| A4 | **Mesma nota, outro arquivo:** comparar número da nota sem zeros à esquerda e sem série. Se o número faltar numa das cópias, comparar fornecedor, valor e data de emissão; se baterem, o segundo arquivo vira **"cópia da nota já recebida"**, sem despesa nova e sem alerta de duplicidade. Também comparar o texto lido dos dois arquivos: texto igual é o mesmo documento. | 10 |
| A5 | **Assinatura depois do início da vigência:** a leitura passa a conferir e grava uma **observação** no documento ("Assinado em 05/09/2024, depois do início da vigência em 18/11/2023"), visível no contrato, sem travar o cadastro. | 3 (parte) |

### Parte B: com mudança no banco (migração 0027, precisa da sua aprovação)

| # | Mudança | Resolve |
|---|---|---|
| B1 | **Alertas de contrato** na Central de Validação, ligados ao documento e ao contrato, com o que estava escrito guardado: (a) assinatura depois do início; (b) **contratante não é o condomínio** (com o nome da Receita, ex.: "é a administradora Manager"); (c) **CNPJ do condomínio errado no contrato**; (d) **contrato sem CNPJ da contratada**. A pessoa continua podendo corrigir o cadastro para liberar, mas a divergência fica registrada, e o alerta oferece "Pedir correção do contrato" (pedido de documentos, D95) ou "Criar assunto". | 3, 4, 5, 7 |
| B2 | **Contrato sem CNPJ da contratada:** se o valor mensal (ou total) ficar **até a alçada do síndico** e o serviço **não for essencial** (fora de portaria, limpeza, elevadores, segurança, manutenção predial e seguro), o contrato entra **pela razão social**, com observação. Acima disso, ou se for essencial, entra também, mas com um **assunto "Ajustar contrato: incluir o CNPJ da contratada"** com responsável e prazo. Quando chegar a primeira nota desse fornecedor, o CNPJ é preenchido pela nota. | 7 |
| B3 | **Contrato pontual × contínuo:** a leitura identifica a natureza (contínuo: mensalidade, vigência, reajuste; pontual: valor total, entrega, parcelas). O contrato pontual guarda **valor total** e parcelas, **não pede índice nem fim de vigência**, não espera NF todo mês e é conferido pelo total pago contra o valor do contrato. | 8 |
| B4 | **Tipos novos de documento:** **comprovante de pagamento** (data, valor, **beneficiário final** e documento dele, banco pagador e autenticação; serve de prova de pagamento e é ligado ao extrato, não vira despesa nova); **guia de tributo** (tributo, competência, vencimento, valor, código de barras; vira despesa da categoria tributos, sem fornecedor, e evita o "pago sem nota"); **relatório da administradora** e **extrato de rendimento** (guardados como texto e pesquisáveis no chat). | 9, 11 |
| B5 | **Relação de devedores:** contém nomes e unidades de **moradores**. O termo do piloto diz que dados de moradores não entram. Proposta: a triagem reconhece esse documento e **recusa** com a explicação ("relação de devedores tem dados de moradores e não entra no piloto"). | 11 |

## 3. Ordem sugerida

1. **Parte A** (A1 a A5): resolve os incômodos maiores (revisão em excesso, CNPJ não achado, nota duplicada) sem mexer no banco.
2. **Parte B**, se aprovada: B4 e B5 primeiro (classificação), depois B1 e B2 (alertas de contrato) e por último B3 (contrato pontual, a maior).

Cada item com teste positivo e negativo. Para os casos reais que você relatou, os testes usam documentos fictícios que reproduzem a mesma situação: os seus documentos não entram no repositório.

## 4. Decisões que preciso

1. **Começo pela Parte A?** (recomendo)
2. **Confiança por evidência (A1):** um valor escrito no documento, ou que confere com a Receita, conta como confirmado mesmo que a IA tenha dado menos de 90%? (recomendo sim; a regra dos 90% continua para o que não tem prova)
3. **Aprovar a migração 0027** com B1 a B4?
4. **B2:** contrato sem CNPJ entra pela razão social até a **alçada do síndico** e para serviço **não essencial**; nos outros casos, entra com um assunto "Ajustar contrato". A lista de serviços essenciais está boa?
5. **B5:** recusar a relação de devedores (recomendo), ou aceitar só o total, sem nomes?
