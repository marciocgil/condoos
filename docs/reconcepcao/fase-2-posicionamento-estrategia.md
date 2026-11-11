# Reconcepção do CondoOS — Fase 2: posicionamento e estratégia

Data: 11/11/2026 · Estado: **aguardando validação do Marcio** (fases 3 a 7 não iniciadas).

Parte das respostas do Marcio à Fase 1 (registradas em D88): beachhead em São Paulo capital com o síndico profissional; D73 mantida (condomínio é o cliente, administradora é fonte de dados e canal a testar); validação em campo corre em paralelo.

Marcação: **[FATO]** com fonte na seção 11; **[CÁLCULO]** com a conta à vista; **[HIPÓTESE]** a validar; **[PREMISSA]** assumida. Análise, não decisão: nada aqui altera roadmap ou código.

**O que mudou em relação à Fase 1.** Nada foi invalidado, mas dois pontos ficaram mais duros: (a) o retorno só pela economia é fino na base estreita de despesas (seção 4), o que torna a medição da taxa de achados ainda mais urgente; (b) a oferta de entrada não pode ser "auditar a carteira do síndico", porque isso audita as aprovações dele próprio. O momento certo de entrada é outro (seção 8).

---

## 1. Categoria

| Opção | O que o comprador entende | A favor | Contra | Veredito |
|-------|---------------------------|---------|--------|----------|
| "Copiloto do síndico" | Um assistente que responde | Simpático, fácil de demonstrar | Já ocupado (Móra da uCondo, GIA da Group); soa a chatbot; não tem valor em reais | Descartar como categoria; serve como forma de uso |
| "Auditor autônomo" | Alguém que confere as contas sozinho | Dor clara, valor contável | "Autônomo" assusta quem responde pelo dinheiro; "auditor independente" é termo de profissão regulada [HIPÓTESE jurídica, conferir com advogado] | Usar a ideia, não o nome |
| "CFO/COO do condomínio" | Um executivo que decide | Ambição alta | Promete decisão, e o produto nunca decide nem paga; condomínio de 100 unidades não se vê contratando um CFO | Descartar |
| "Camada de inteligência sobre o ERP" | Nada: é arquitetura | Verdadeiro tecnicamente | Ninguém compra camada; põe o ERP da administradora no centro da frase | Descartar como mensagem; manter como arquitetura |
| "Assessor inteligente de gestão" (Especificação Mestra §1.2) | Um consultor amplo | Guarda-chuva para Advisor, Operate e Optimize | Amplo demais para a primeira venda; não diz o que entrega no mês 1 | Manter como visão de longo prazo |
| **"Controladoria independente do condomínio"** | Alguém do meu lado conferindo cada pagamento, todo mês | Categoria que o síndico já conhece ("auditoria preventiva") e que já tem preço de referência; a palavra "independente" é o que o ERP não pode dizer | Menos glamour; exige disciplina para não virar "auditoria" no sentido regulado | **Recomendada para a entrada** |

**Recomendação: não criar categoria nova na primeira venda.** Criar categoria custa caro e pede caixa de marketing que não existe. O síndico já sabe o que é auditoria preventiva e quanto ela custa; o CondoOS entra como a versão contínua, barata e com evidência dessa categoria, e ganha o direito de se expandir para "assessor" depois que provar valor em reais.

Divergência registrada (R8): a Especificação Mestra posiciona como "assessor inteligente". Proponho "controladoria independente" como porta de entrada e "assessor" como destino. Precisa da sua decisão.

---

## 2. Substituir o ERP ou operar sobre ele

| Critério | Substituir o ERP | Camada sobre o ERP (leitura) |
|----------|------------------|------------------------------|
| Velocidade de adoção | Lenta: migração de dados, boletos, folha, treinamento | Rápida: recebe a pasta do mês e os contratos |
| Fricção de venda | Altíssima: o comprador é a administradora, que D73 excluiu | Baixa: o síndico decide; nada é desligado |
| Defensabilidade | Alta depois de instalado, mas contra Superlógica (130 mil condomínios) | Média: depende de independência, histórico e trilha |
| Dependência de terceiros | Baixa | **Alta**: o dado nasce no ERP da administradora |
| Receita potencial por cliente | Alta (assinatura + financeiro) | Menor (assinatura + economia medida) |
| Coerência com a tese "sistema de ação, não de registro" | Contradiz: vira sistema de registro | Coerente |
| Investimento | Anos e dezenas de milhões | O MVP já existe |

**Recomendação: camada, sem ambiguidade.** Já é o princípio da Especificação Mestra ("integrar antes de substituir", §4.2) e é a única opção compatível com D73 e com um fundador sem captação.

O preço dessa escolha é a dependência do dado. Como reduzi-la:

1. **O dado é do condomínio.** O síndico tem o dever de prestar contas (Código Civil, art. 1.348) e recebe a pasta todo mês. O caminho inicial é ele encaminhar a pasta (PDF, e-mail) e os contratos. Isso o produto já faz.
2. **Escolher condomínios cujas administradoras usam os dois ERPs dominantes** [HIPÓTESE: pastas da Superlógica e da Group têm formato repetível, o que barateia a leitura].
3. **Extrato direto do banco** (OFX, e depois Open Finance com consentimento do condomínio) para não depender da conciliação feita pela administradora.
4. **Nunca depender de API do ERP.** Se vier, é ganho; o plano não pode contar com ela.

---

## 3. ICP e beachhead

**Primeiro comprador (confirmado em D88):** síndico profissional em São Paulo capital.

| Atributo | Critério | Motivo |
|----------|----------|--------|
| Carteira | 5 ou mais condomínios | Uma venda, várias instalações |
| Condomínio | Residencial, 80 unidades ou mais, ou despesa acima de R$ 1 milhão/ano | Abaixo disso o retorno não paga o preço (seção 4) |
| Administradora | Existe, e entrega pasta mensal digital | Sem pasta digital não há ingestão |
| Momento | Assumindo condomínio novo, ou com contrato grande a renovar em até 6 meses | É quando há motivo para olhar para trás sem culpa (seção 8) |
| Fora do alvo agora | Autogestão pequena, condomínio-clube, comercial, loteamento | Volume e formato de dado diferentes |

**Tamanho do beachhead.** [CÁLCULO] 31,1 mil condomínios × 13,5% com síndico profissional = cerca de 4,2 mil condomínios. [HIPÓTESE] Se 40% deles passam de R$ 1 milhão/ano: cerca de 1,7 mil condomínios. A R$ 6 mil/ano cada (seção 7): **teto de cerca de R$ 10 milhões de receita anual no beachhead**. No Brasil, com as mesmas proporções: 65 mil × 30% × R$ 6 mil = cerca de R$ 117 milhões.

Leitura honesta: **só com a assinatura do controle de despesas, isto é um bom negócio próprio, não uma tese de venture.** Para ser maior, precisa de receita de expansão por condomínio (economia medida em renegociação, mão de obra) ou de outros segmentos.

**Caminho de expansão:**

1. Mais condomínios da carteira do mesmo síndico.
2. Síndico morador de condomínio grande, com o conselho fiscal como patrocinador.
3. Outras capitais (Minas Gerais tem mais de 51 mil condomínios; Rio de Janeiro).
4. Renegociação com economia medida (Optimize, D81/D84) nos condomínios já atendidos.
5. Administradoras pequenas como canal ou marca branca, só depois de provado o mercado direto (Especificação Mestra §22.4).

---

## 4. Proposta de valor quantificada e modelo de retorno

Condomínio de referência: **R$ 1 milhão de despesa por ano** [PREMISSA], preço de **R$ 500/mês** (R$ 6 mil/ano) [HIPÓTESE da seção 7].

| Cenário | Base conferível | Taxa de economia | Economia/ano | Retorno sobre o preço |
|---------|-----------------|:-:|:-:|:-:|
| Conservador: só contratos e administrativo (27% da despesa) | R$ 270 mil | 3% | R$ 8,1 mil | 1,35× |
| Central: inclui mão de obra terceirizada (75%) | R$ 750 mil | 3% | R$ 22,5 mil | 3,75× |
| Otimista: mesma base | R$ 750 mil | 5% | R$ 37,5 mil | 6,25× |

[CÁLCULO] Ponto de equilíbrio do cliente: R$ 6 mil ÷ R$ 1 milhão = **0,6% da despesa total**. A meta de 1,5% (H9 da Fase 1) dá 2,5×.

O que isso diz: **no cenário conservador o retorno é fraco (1,35×).** Um síndico não troca hábito por 35% de retorno incerto. Duas consequências:

- Cobrir a mão de obra terceirizada deixa de ser "expansão" e passa a ser condição para a proposta ficar forte.
- A venda não pode se apoiar só na economia. Precisa dos outros dois valores abaixo.

| Persona | Economia | Tempo | Risco |
|---------|----------|-------|-------|
| **Síndico profissional** | 0,8% a 3,75% da despesa de cada condomínio [HIPÓTESE] | [CÁLCULO] 32 h/semana ÷ 8 condomínios = 4 h por condomínio por semana. [HIPÓTESE] 2 h/mês poupadas por condomínio na conferência da pasta = 16 h/mês na carteira. A cerca de R$ 144/h (receita de R$ 20 mil/mês ÷ 139 h), vale R$ 2,3 mil/mês | Registro de que cada pagamento foi conferido e cada decisão teve evidência: a defesa dele na assembleia e na troca de gestão. Argumento para ganhar e reter contratos |
| **Conselho fiscal** | A mesma do condomínio | Parecer mensal sobre exceções, não sobre a pasta inteira | Assina com base em conferência completa, não em amostragem |
| **Condômino** | Indireta: menos pressão por reajuste da cota | — | Confiança |
| **Administradora (não compradora)** | — | Menos idas e vindas se a divergência chega com evidência | Risco para ela: exposição de erro. Ganho: cliente que confia fica |

Honorários de referência do síndico profissional: R$ 2 mil a R$ 3 mil por mês por condomínio (Secovi-SP, sem data clara) e média de R$ 3.297 (oHub, sem método) [FATO fraco]. A R$ 500/mês, o CondoOS custa ao condomínio cerca de um sexto do que custa o síndico.

---

## 5. Posicionamento

> **Para** o síndico profissional que responde por vários condomínios,
> **que** aprova pagamentos todo mês sem conseguir conferir cada um contra contrato, nota e extrato,
> **o CondoOS é** a controladoria independente do condomínio
> **que** confere todas as despesas, aponta só o que diverge, com evidência e valor, e guarda a trilha de cada decisão,
> **diferentemente** do sistema da administradora, que confere o próprio trabalho, e da auditoria tradicional, que chega depois e por amostragem,
> **porque** trabalha só para o condomínio, nunca recebe de fornecedor, mostra o cálculo de cada apontamento e mede a economia com as faturas seguintes.

Frase curta para conversa: **"Todo pagamento conferido, por alguém que só trabalha para o condomínio."**

A "prova" da última linha ainda não existe com cliente real. Hoje ela se sustenta no produto (regras determinísticas, evidência, trilha só de inclusão, método de economia versionado) e num aceite com dados fictícios. O primeiro caso real é o ativo que falta.

---

## 6. Diferenciação e defesas

| Defesa | Contra incumbentes | Contra "usar o ChatGPT" | Força hoje | O que a torna real |
|--------|--------------------|-------------------------|:-:|-------------------|
| **Independência** (cliente é o condomínio; nenhuma receita de fornecedor ou administradora) | Forte: ERP não pode auditar o próprio cliente sem perdê-lo | Neutra | Alta | Manter a regra sem exceção; publicá-la em contrato |
| **Trilha de diligência** (decisões e evidências que não se apagam) | Média | Forte: conversa não é registro | Alta (já existe) | Virar documento que o síndico leva à assembleia |
| **Portabilidade pelo síndico** (ele leva o CondoOS a cada condomínio novo) | Forte: é distribuição que o ERP não tem | — | Baixa (zero clientes) | Preço e conta por carteira |
| **Histórico do condomínio** (contratos, reajustes, preços, decisões) | Média: o ERP também tem, do lado dele | Forte | Cresce com o tempo | Sobreviver à troca de síndico: o histórico é do condomínio |
| **Profundidade determinística** (contrato × nota × extrato × índice, número conferido por código) | Média: Group já tem nove verificadores; copiável em 12 a 18 meses | Forte | Alta | Cobrir mão de obra e consumo antes deles |
| **Referência de preços entre condomínios** | Fraca hoje: eles têm 130 mil condomínios de dado, embora não o usem assim | Forte | **Nula** | [CÁLCULO] 40 condomínios × 15 contratos = 600 preços, pouco. Só vale a partir de algumas centenas de condomínios na mesma cidade e categoria |
| **Rede de fornecedores** | Fraca | — | Nula | Não perseguir agora; e nunca com fornecedor pagando |
| **Integrações** | Fraca | Média | Baixa | Não é defesa; é custo |

Ordem de aposta: independência e trilha agora; portabilidade pelo síndico como motor de distribuição; referência de preços como defesa de longo prazo, sem prometê-la antes de existir.

---

## 7. Monetização

| Modelo | A favor | Contra | Conflito de interesse | Veredito |
|--------|---------|--------|-----------------------|----------|
| Assinatura por unidade | Previsível; o mercado já conhece | Unidade não mede complexidade; prédio pequeno e caro paga pouco | Nenhum | Usar como referência, cobrar por faixa |
| **Assinatura por condomínio, por faixa de despesa anual** | Previsível; proporcional ao valor; cabe em "despesa administrativa" | Exige declarar ou medir a despesa | Nenhum | **Base recomendada** |
| Taxa sobre economia em todos os achados | Alinha preço a resultado; entrada sem custo | Receita irregular; disputa sobre o que é "economia"; **incentiva o sistema a inflar achados**, o que destrói a independência | **Alto** | Descartar para o controle de despesas |
| Taxa sobre economia realizada em renegociação | Alinhada; medida pelo método já aprovado (D84/D87: faturas depois do acordo) | Ciclo longo; depende de o síndico agir | Baixo, se medido por método publicado e revisado | **Complemento recomendado**, só no Optimize |
| Comissão do fornecedor ou percentual em compras | Receita grande no papel | O agente recomendaria quem lhe paga | **Inaceitável** | **Nunca.** Já vedado pela Especificação Mestra §22.4 |
| Taxa de diagnóstico inicial | Qualifica o cliente; paga a revisão humana | Fricção na entrada | Nenhum | Usar depois dos primeiros casos |

**Proposta [HIPÓTESE, a testar nas entrevistas]:**

| Faixa de despesa anual | Assinatura mensal | % da despesa |
|------------------------|:-:|:-:|
| Até R$ 1 milhão | R$ 390 | 0,47% ou mais |
| R$ 1 a 2 milhões | R$ 590 | 0,35% a 0,71% |
| R$ 2 a 4 milhões | R$ 890 | 0,27% a 0,53% |
| Acima de R$ 4 milhões | sob consulta | — |

- Desconto por carteira para o síndico (por exemplo, 15% a partir de 5 condomínios), mantendo **um contrato por condomínio**: quem paga e quem é dono do dado é o condomínio.
- Renegociação com economia medida: 20% da economia realizada nos primeiros 12 meses, com teto, cobrada só depois da medição. A única referência de mercado que achei é uma empresa que cobrava 50% da economia em 2016 [FATO fraco].
- Âncora de preço: auditoria preventiva mensal custava R$ 1 mil/mês por volta de 2012 [FATO fraco, SíndicoNet]; corrigida pela inflação do período, algo como R$ 2 mil hoje [CÁLCULO aproximado, não conferi o índice]. O CondoOS ficaria em um quarto a um terço disso.

Divergência registrada (R9): o Plano Diretor deixa a monetização aberta até o gate G5 ("medir valor antes de precificar"). Concordo em não fechar preço antes de medir; a tabela acima é hipótese para testar disposição a pagar, não tabela de venda.

---

## 8. Go-to-market

**Movimento:** venda consultiva feita pelo fundador. Produto que se vende sozinho não funciona aqui: o valor depende de documentos que o cliente precisa entregar, e a confiança é pessoal. Seu histórico em venda consultiva é a vantagem; o risco é o ticket de R$ 6 mil/ano não pagar o seu tempo, o que só se resolve com a carteira (uma venda, cinco a oito condomínios).

**A oferta de entrada e o problema da "auditoria gratuita dos últimos 12 meses".** A ideia do prompt tem um defeito: oferecida a um síndico sobre a carteira que ele já administra, ela audita as aprovações dele. O achado vira prova contra o próprio comprador. Proposta:

| Oferta | Para quem | Por que funciona |
|--------|-----------|------------------|
| **Diagnóstico de entrada** (12 meses anteriores) | Síndico que acabou de assumir um condomínio | Ele não aprovou nada daquilo. O diagnóstico vira o "estado em que recebi", protege-o e mostra serviço ao conselho no primeiro trimestre |
| **Revisão antes da renovação** | Condomínio com contrato grande vencendo em até 6 meses | Há uma decisão marcada e um valor claro em jogo |
| Diagnóstico da carteira atual | Só depois de confiança estabelecida | Enquadrado como conferência de fornecedores e da administradora, nunca do síndico |

Gratuito ou pago: para os primeiros 5 a 10, gratuito em troca de dados reais, entrevista e direito de publicar o caso sem identificação. Depois, taxa de diagnóstico abatida da assinatura. Cada diagnóstico custa horas de revisão humana (D74 exige revisão proporcional ao risco), então "grátis para sempre" não escala.

**Canais, em ordem:**

1. Rede direta e indicações entre síndicos profissionais (são cerca de 500 em São Paulo; o mercado é pequeno o bastante para ser coberto pessoalmente).
2. Associações e eventos do setor (ABRASSP, encontros de síndicos) e conteúdo com casos reais.
3. Conselheiros fiscais de condomínios grandes, que têm a dor e não têm o conflito.
4. Administradoras pequenas, como teste de canal, sem dependência.

**Ciclo esperado [HIPÓTESE]:** 2 a 4 semanas até o diagnóstico (o gargalo é receber os documentos); 30 a 90 dias até a assinatura, porque despesa nova pode pedir aval do conselho. A lei dá ao síndico poderes de administração ordinária, mas a jurisprudência diverge sobre contratar sem assembleia [FATO]; ficar dentro da verba administrativa já aprovada e pedir o aval do conselho reduz o risco.

**Funil dos primeiros 12 meses [HIPÓTESE]:**

| Etapa | Quantidade |
|-------|:-:|
| Síndicos profissionais em São Paulo capital | cerca de 500 |
| Conversas | 100 |
| Diagnósticos de entrada feitos | 20 |
| Síndicos pagantes | 10 |
| Condomínios pagantes (4 por síndico no primeiro ano) | 40 |
| Receita mensal recorrente ao fim de 12 meses | cerca de R$ 20 mil |

R$ 20 mil por mês em um ano é pouco em receita e muito em prova: 40 condomínios reais dão a taxa de achados, o primeiro caso e os primeiros 600 preços de contrato.

---

## 9. Fechamento da Fase 2

### Resumo

- **Categoria de entrada: controladoria independente do condomínio**, não "copiloto" nem "CFO". "Assessor inteligente" fica como destino.
- **Camada sobre o ERP, nunca substituto.** A dependência do dado se reduz porque a pasta e o extrato são do condomínio e chegam pelo síndico.
- **O retorno só pela economia é fino** (1,35× no cenário conservador, 3,75× com mão de obra). A proposta precisa cobrir mão de obra terceirizada e vender também tempo e prova de diligência.
- **Preço por condomínio em faixas (R$ 390 a R$ 890/mês, hipótese), mais 20% da economia realizada só em renegociação.** Nunca dinheiro de fornecedor.
- **Entrada pelo "diagnóstico de entrada"** quando o síndico assume um condomínio; meta de 12 meses de 40 condomínios e cerca de R$ 20 mil de receita mensal. O beachhead tem teto de cerca de R$ 10 milhões por ano.

### Três decisões que preciso de você

1. **Categoria (R8):** aceita "controladoria independente do condomínio" como posicionamento de entrada, com "assessor inteligente" como visão de longo prazo? Isso orienta toda a Fase 3 (marca).
2. **Monetização:** aceita como hipótese de trabalho a assinatura por faixa mais taxa só sobre economia realizada em renegociação, com proibição permanente de receita de fornecedor?
3. **Ambição:** o objetivo é um negócio próprio e rentável no nicho, ou uma tese para captar? A resposta muda a Fase 6: no primeiro caso, o foco é o beachhead; no segundo, é preciso provar cedo a receita de expansão (renegociação e mão de obra).

### Principais riscos

- **Retorno insuficiente para mudar hábito.** Se a taxa de achados ficar perto de 0,6% da despesa, o cliente empata e não renova.
- **O comprador é auditado pelo próprio produto.** Mesmo com o diagnóstico de entrada, a conferência mensal passa a mostrar o que o síndico aprovou. Parte dos síndicos vai recusar por isso; é um filtro, e pode ser grande.
- **Acesso aos documentos.** Administradora que atrasa ou dificulta a pasta trava o ciclo de venda.
- **Ticket baixo com venda cara.** Sem a carteira, o custo de aquisição não fecha.
- **Termo "auditoria".** Pode esbarrar em regulação profissional; a comunicação precisa de revisão jurídica antes de ir a público.
- **Cópia pelos ERPs.** A profundidade técnica é copiável; a independência não. Tudo que depender só de técnica tem prazo de validade.

---

## 10. Divergências acrescentadas nesta fase

| # | Divergência | Documento interno | Esta análise |
|---|-------------|-------------------|--------------|
| R8 | Categoria | "Assessor inteligente de gestão condominial" (Especificação Mestra §1.2) | "Controladoria independente" na entrada; assessor como destino |
| R9 | Momento de precificar | Plano D-12: aberta até G5 | Testar disposição a pagar já, com tabela-hipótese; fechar preço só após medir |
| R10 | Indicador principal | Especificação §17.1: % de demandas resolvidas sem o síndico (Operate) e economia líquida realizada (Optimize) | Para o beachhead, só o segundo faz sentido agora. Detalhar na Fase 6 |

As divergências R1 a R7 estão na Fase 1. R2 (comprador) foi resolvida por D88. R1 (dor central: coordenação ou controle da despesa) segue aberta; esta fase assume controle da despesa.

## 11. Fontes novas desta fase

- Honorários do síndico profissional: https://www.sindiconet.com.br/informese/remuneracao-do-sindico-profissional-administracao-sindico-profissional e https://jornalcontabil.com.br/noticia/carreira-sindico-profissional-cobra-ate-r-7-000-para-administrar-condominios/
- Preço de auditoria preventiva (antigo): https://www.sindiconet.com.br/informese/auditoria-em-condominios-noticias-administracao
- Cobrança de 50% sobre a economia (2016): https://www.sindiconet.com.br/informese/economia-sem-esforco-mercado-coluna-de-olho-no-mercado
- Poderes do síndico para contratar: https://www.sindiconet.com.br/informese/contratacao-de-servicos-e-assembleia-de-condominio-colunistas-zulmar-koerich e https://condominiosc.com.br/jornal-dos-condominios/financas/1752-despesa-sem-autorizacao-da-assembleia-pode-complicar-vida-do-sindico
- Demais números: ver `fase-1-mercado-personas-dores.md`, seção 10.

Não verificado nesta fase: preço atual de auditoria preventiva, taxa de administração das administradoras, preço dos ERPs e dos apps, e o enquadramento regulatório do termo "auditoria".
