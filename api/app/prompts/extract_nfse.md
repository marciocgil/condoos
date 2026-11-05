Documento: nota fiscal de serviço eletrônica (NFS-e).

Campos:
- numero: número da NFS-e (não confundir com o número do RPS ou código de verificação).
- data_emissao: data de emissão da nota.
- competencia: mês de competência do serviço.
- cnpj_prestador / razao_social_prestador: o prestador do serviço (fornecedor).
- cnpj_tomador: o tomador do serviço (o condomínio).
- valor_servicos: valor total dos serviços, antes das retenções.
- valor_liquido: valor líquido a pagar, depois das retenções.
- retencao_iss, retencao_inss, retencao_ir, retencao_pis, retencao_cofins, retencao_csll: valores efetivamente retidos. ISS só conta como retenção se a nota disser "ISS retido". Se não houver retenção, devolva nulo.
- discriminacao: texto da discriminação dos serviços, completo.
