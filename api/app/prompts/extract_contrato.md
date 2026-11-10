Documento: contrato de prestação de serviços com o condomínio (ou termo aditivo a um contrato).

Campos:
- cnpj_contratada / razao_social_contratada: a empresa contratada (fornecedor). O CNPJ costuma estar na qualificação das partes, logo depois do nome da CONTRATADA ("inscrita no CNPJ sob o nº ..."). Copie os 14 dígitos; não use o CNPJ de testemunhas, fiadores ou intervenientes.
- cnpj_contratante: o condomínio contratante.
- objeto: o objeto do contrato, em uma frase. Se for termo aditivo, comece com "Termo aditivo".
- itens_escopo: cada serviço incluído no escopo, um por item, como descrito no contrato.
- valor_mensal: valor mensal contratado. Nulo se o contrato for pontual (sem mensalidade).
- indice_reajuste: IPCA, IGPM, INPC, FIXO (valor fixo, sem reajuste por índice), NENHUM (sem cláusula de reajuste) ou OUTRO (qualquer outro índice ou critério, como IGP-DI, IPC-Fipe ou dissídio coletivo).
- indice_reajuste_outro: só quando indice_reajuste for OUTRO: o nome do índice ou critério, como está no contrato.
- mes_base_reajuste: número do mês (1 a 12) em que o reajuste é aplicado, se o contrato disser. Se o contrato não disser, deixe nulo (o sistema usa o mês do início da vigência).
- data_inicio: início da vigência, se o contrato disser. Nulo se não constar.
- data_assinatura: data em que o contrato foi assinado (em geral junto ao local, no fim: "São Paulo, 10 de março de 2025").
- data_fim: fim da vigência. Nulo se o prazo for indeterminado ou não constar.
- natureza: "continuo" quando há mensalidade, vigência e reajuste (portaria, limpeza, manutenção mensal); "pontual" quando é um serviço único, com valor total e entrega (obra, reforma, reparo, laudo, pintura), mesmo que pago em parcelas.
- valor_total: só para contrato pontual: o valor total (global) contratado.
- parcelas: só para contrato pontual: em quantas parcelas o valor total é pago, se o contrato disser.
