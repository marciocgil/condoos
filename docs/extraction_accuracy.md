# Acurácia da extração — corpus fictício (Marco 2)

- Data de referência: 05/11/2026
- Modo do LLM: `replay` · Conversor: Docling
- Documentos: 30

| Métrica | Resultado | Meta |
| --- | --- | --- |
| Documentos sem revisão manual | 12/30 (40%) | ≥ 90% |
| Automáticos com dado divergente | 0 | 0 |
| Tipo de documento correto | 29/30 (97%) | — |

## Acurácia por campo

| Campo | Corretos | % |
| --- | --- | --- |
| chave_acesso | 3/3 | 100% |
| cnpj_beneficiario | 9/10 | 90% |
| cnpj_contratada | 1/1 | 100% |
| cnpj_contratante | 1/1 | 100% |
| cnpj_destinatario | 3/3 | 100% |
| cnpj_emitente | 3/3 | 100% |
| cnpj_pagador | 9/10 | 90% |
| cnpj_prestador | 11/12 | 92% |
| cnpj_tomador | 11/12 | 92% |
| competencia | 11/12 | 92% |
| data | 3/4 | 75% |
| data_emissao | 14/15 | 93% |
| data_fim | 0/1 | 0% |
| data_inicio | 0/1 | 0% |
| descricao | 0/4 | 0% |
| discriminacao | 10/12 | 83% |
| documento_recebedor | 0/4 | 0% |
| indice_reajuste | 1/1 | 100% |
| itens | 3/3 | 100% |
| itens_escopo | 0/1 | 0% |
| linha_digitavel | 9/10 | 90% |
| mes_base_reajuste | 0/1 | 0% |
| nome_beneficiario | 0/10 | 0% |
| nome_recebedor | 0/4 | 0% |
| numero | 9/15 | 60% |
| numero_documento | 0/8 | 0% |
| objeto | 0/1 | 0% |
| razao_social_contratada | 0/1 | 0% |
| razao_social_emitente | 3/3 | 100% |
| razao_social_prestador | 6/12 | 50% |
| retencao_cofins | 1/2 | 50% |
| retencao_csll | 1/2 | 50% |
| retencao_inss | 3/4 | 75% |
| retencao_ir | 1/2 | 50% |
| retencao_iss | 4/4 | 100% |
| retencao_pis | 1/2 | 50% |
| valor | 13/14 | 93% |
| valor_liquido | 6/12 | 50% |
| valor_mensal | 0/1 | 0% |
| valor_servicos | 10/12 | 83% |
| valor_total | 3/3 | 100% |
| vencimento | 9/10 | 90% |

## Por documento

| Arquivo | Tipo esperado | Tipo obtido | Automático | Campos certos | Fonte | Motivo da revisão |
| --- | --- | --- | --- | --- | --- | --- |
| 01_nfse.pdf | nfse | nfse | não | 7/10 | texto | Número da nota: não encontrado; Data de emissão: baixa confiança; Razão social do prestador: não encontrado; Valor dos serviços: baixa confi |
| 02_nfse.pdf | nfse | nfse | não | 11/11 | texto | Número da nota: baixa confiança; Data de emissão: baixa confiança; Razão social do prestador: baixa confiança; Valor dos serviços: baixa con |
| 03_nfse.pdf | nfse | nfse | não | 6/9 | texto | Número da nota: não encontrado; Data de emissão: baixa confiança; Razão social do prestador: não encontrado; Valor dos serviços: baixa confi |
| 04_nfse.pdf | nfse | nfse | não | 10/10 | texto | Número da nota: baixa confiança; Data de emissão: baixa confiança; Razão social do prestador: baixa confiança; Valor dos serviços: baixa con |
| 05_nfse.pdf | nfse | nfse | não | 6/9 | texto | Número da nota: não encontrado; Data de emissão: baixa confiança; Razão social do prestador: não encontrado; Valor dos serviços: baixa confi |
| 06_nfse.pdf | nfse | nfse | não | 13/13 | texto | Número da nota: baixa confiança; Data de emissão: baixa confiança; Razão social do prestador: baixa confiança; Valor dos serviços: baixa con |
| 07_nfse.pdf | nfse | nfse | não | 6/9 | texto | Número da nota: não encontrado; Data de emissão: baixa confiança; Razão social do prestador: não encontrado; Valor dos serviços: baixa confi |
| 08_nfse.pdf | nfse | nfse | não | 10/10 | texto | Número da nota: baixa confiança; Data de emissão: baixa confiança; Razão social do prestador: baixa confiança; Valor dos serviços: baixa con |
| 09_boleto.pdf | boleto | boleto | sim | 5/7 | texto |  |
| 10_boleto.pdf | boleto | boleto | sim | 5/7 | texto |  |
| 11_boleto.pdf | boleto | boleto | sim | 5/7 | texto |  |
| 12_boleto.pdf | boleto | boleto | sim | 5/7 | texto |  |
| 13_boleto.pdf | boleto | boleto | sim | 5/7 | texto |  |
| 14_boleto.pdf | boleto | boleto | sim | 5/7 | texto |  |
| 15_conta_energia.pdf | boleto | boleto | não | 5/6 | texto | Vencimento: baixa confiança |
| 16_conta_agua.pdf | boleto | boleto | não | 5/6 | texto | Vencimento: baixa confiança |
| 17_recibo.pdf | recibo | recibo | não | 2/5 | texto | Data: baixa confiança; Valor: baixa confiança; Quem recebeu: não encontrado; Referente a: não encontrado |
| 18_recibo.pdf | recibo | recibo | não | 2/5 | texto | Data: baixa confiança; Valor: baixa confiança; Quem recebeu: não encontrado; Referente a: não encontrado |
| 19_recibo.pdf | recibo | recibo | não | 2/5 | texto | Data: baixa confiança; Valor: baixa confiança; Quem recebeu: não encontrado; Referente a: não encontrado |
| 20_contrato.pdf | contrato | contrato | não | 3/10 | texto | Razão social da contratada: não encontrado; Objeto: não encontrado; Itens do escopo: não encontrado; Valor mensal: não encontrado; Índice de |
| 21_nfe.xml | nfe | nfe | sim | 8/8 | nfe |  |
| 22_nfe.xml | nfe | nfe | sim | 8/8 | nfe |  |
| 23_nfe.xml | nfe | nfe | sim | 8/8 | nfe |  |
| 24_nfse_nacional.xml | nfse | nfse | sim | 10/10 | nfse_nacional |  |
| 25_nfse_abrasf.xml | nfse | nfse | sim | 10/10 | nfse_abrasf |  |
| 26_foto_nfse.jpg | nfse | nfse | não | 4/10 | texto | Número da nota: não encontrado; Data de emissão: baixa confiança; Razão social do prestador: não encontrado; Valor dos serviços: não encontr |
| 27_foto_nfse.jpg | nfse | nfse | não | 0/13 | nenhuma | Número da nota: não encontrado; Data de emissão: não encontrado; CNPJ do prestador: não encontrado; Razão social do prestador: não encontrad |
| 28_foto_boleto.jpg | boleto | boleto | sim | 5/7 | texto |  |
| 29_foto_boleto.jpg | boleto | outro | não | 0/7 | nenhuma | Documento sem texto legível (foto ou digitalização): é preciso ler e preencher. |
| 30_foto_recibo.jpg | recibo | recibo | não | 1/5 | texto | Data: não encontrado; Valor: baixa confiança; Quem recebeu: não encontrado; Referente a: não encontrado |

