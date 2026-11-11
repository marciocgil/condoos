# Reconcepção do CondoOS — Fase 7: ataque à proposta e síntese

Data: 11/11/2026 · Última fase. Parte das respostas à Fase 6 (D93): congelamento de funcionalidades por três meses, roadmap novo no lugar da sequência a partir de C7, piloto com 5 a 10 condomínios de síndicos profissionais, critérios de parada e métrica norte aprovados.

Marcação: **[FATO]**, **[CÁLCULO]**, **[HIPÓTESE]**, **[PREMISSA]**, com as fontes nas fases 1 e 2. Nesta fase não há pesquisa nova; os números vêm das anteriores.

**O que mudou em relação às fases anteriores.** Ao atacar a proposta, duas objeções ficaram sem resposta boa (3 e 8 abaixo). Elas não invalidam o plano, mas mudam o que observar no primeiro trimestre, e entraram nos próximos 30 dias.

---

## 1. As dez objeções mais fortes

Força da resposta: **forte** (há fato ou mecanismo), **média** (há plano, falta prova), **fraca** (só o campo responde).

### Investidor cético

**1. "O mercado que você consegue servir é minúsculo."**
É verdade para a cunha: cerca de 1,7 mil condomínios e R$ 10 milhões por ano de teto em São Paulo capital [CÁLCULO, Fase 2]. A resposta não é discutir o tamanho, é a ambição escolhida: negócio próprio e rentável (D89), que não precisa de mercado de bilhão. Com 40 condomínios a R$ 500 e margem de 70%, cobre um fundador e um revisor. O que continua frágil: a expansão para além do síndico profissional é hipótese. *Força: média.*

**2. "Superlógica e Group têm o dado e 130 mil condomínios. Copiam isso em um ano."**
A parte técnica eles copiam, e a Group já tem um auditor de fechamento [FATO]. O que não copiam é o lado: o cliente deles é a administradora, e um produto que mostra ao condomínio os erros da administradora ameaça a própria receita. Enquanto venderem para a administradora, a independência é estrutural. O risco real é outro: oferecerem ao síndico um "selo de conferido" gratuito, bom o bastante para tirar a urgência. *Força: forte na lógica, média no tempo.*

**3. "Você tem um produto pronto e zero conversas com cliente. Isso é um engenheiro evitando vender."**
Não há defesa. É o que o repositório mostra: 44 tabelas, backlog quase todo entregue, gate de piloto aberto [FATO]. A única resposta é comportamento: congelamento de código (D93) e 70% do tempo em campo. Se em 30 dias não houver dez conversas feitas, a objeção está confirmada. *Força: fraca; só os próximos 30 dias respondem.*

**4. "Ticket de R$ 500 por mês com venda consultiva não fecha."**
Fecha só com a carteira: um síndico traz de 4 a 8 condomínios numa venda [FATO sobre a carteira média; HIPÓTESE sobre ele levar todos]. Se cada condomínio exigir aprovação separada do conselho, a venda volta a ser unitária e o custo de aquisição estoura. É o critério H5 das entrevistas e o primeiro a testar. *Força: média.*

### CEO de administradora concorrente

**5. "Vocês vivem da pasta que a minha administradora produz. Eu atraso, mudo o formato ou cobro, e vocês param."**
A pasta e o extrato pertencem ao condomínio, e o síndico tem o dever legal de prestar contas [FATO, Código Civil, art. 1.348]. Administradora que dificulta entrega de documento ao próprio cliente expõe-se a perdê-lo. Mas atraso e má vontade não são ilegais e travam um piloto. Mitigação: extrato direto do banco, e escolher condomínios cuja administradora já entrega pasta digital. *Força: média.*

**6. "No primeiro falso positivo que constranger um fornecedor ou a minha equipe, o síndico desliga vocês."**
É o risco operacional mais sério. As defesas existem: revisão humana antes de o achado chegar ao síndico, linguagem de "indício" e "divergência" imposta por código, evidência e conta em cada cartão, e parada automática se a precisão cair abaixo de 50% (K8). O que falta é a medida: a precisão em documentos reais é desconhecida. *Força: média até haver dados.*

**7. "O conselho fiscal já confere, de graça."**
Confere por amostragem, uma vez por mês, como voluntário [HIPÓTESE H1, a validar]. A proposta não substitui o conselho: entrega a ele a conferência completa para dar o parecer. Bem conduzido, o conselheiro vira aliado na venda. *Força: média; depende das entrevistas.*

### Síndico desconfiado

**8. "Vocês vão me auditar. Por que eu pagaria por isso?"**
É a objeção sem boa resposta. O diagnóstico de entrada contorna o primeiro mês, porque olha o período anterior à gestão dele. Do segundo mês em diante, o sistema mostra o que ele próprio aprovou. O argumento é que o síndico que confere se protege, e pode provar diligência quando for questionado. Isso convence o síndico que quer ser bem visto; afasta o que prefere não ser olhado. Parte do mercado vai recusar, e não sei de que tamanho é essa parte. *Força: fraca; é o que as entrevistas precisam medir primeiro.*

**9. "Não vou mandar documento do condomínio para uma inteligência artificial."**
Resposta concreta: os dados são isolados por condomínio no banco, com teste; nada de morador é pedido; o sistema não acessa conta bancária nem move dinheiro; há retenção definida e exportação a qualquer momento; e um termo assinado com o condomínio como dono do dado [FATO sobre o produto; o termo ainda depende de advogado]. Falta um documento de uma página que diga isso em linguagem simples. *Força: forte no produto, média na comunicação.*

**10. "E se vocês errarem e eu decidir errado por causa disso?"**
O sistema nunca decide: aponta, mostra a prova e a conta, e a decisão é dele, registrada. Todo apontamento diz o grau de certeza e o que faltou conferir. A política de erro (achado descartado conta como erro nosso; correção comunicada) está no plano, ainda não publicada. O que não se pode prometer: ausência de erro. *Força: média.*

**Leitura do conjunto.** As objeções com resposta fraca (3 e 8) são de comportamento e de mercado, não de produto. Nenhuma se resolve com código.

---

## 2. Riscos e mitigação

| Categoria | Risco | Probabilidade | Impacto | Mitigação | Sinal de alerta |
|-----------|-------|:-:|:-:|-----------|-----------------|
| Mercado | Taxa de achados não paga o produto | Desconhecida | Fatal | Medir em 5 pastas antes de vender (K1, K2) | Abaixo de 0,5% da despesa |
| Mercado | Síndico recusa ser conferido | Média a alta | Alto | Diagnóstico de entrada; venda como proteção; conselho como segundo comprador | Menos de 3 pastas em 30 abordagens (K3) |
| Adoção | Decisão por condomínio, e não por carteira | Média | Alto | Preço e conta por carteira; aval do conselho dentro da verba administrativa | H5 abaixo de 60% |
| Adoção | Entrada de documento exige hábito novo | Alta | Médio | Encaminhar o e-mail que ele já recebe; WhatsApp para captura depois | Pastas chegando com mais de 15 dias de atraso |
| Adoção | Fundador como gargalo | Alta | Alto | Congelamento de código; revisor em meio período no segundo semestre | Diagnóstico parado esperando revisão |
| Regulatório | Uso de "auditoria" esbarrar em profissão regulada | Desconhecida | Médio | Posicionar como "controladoria" e "conferência"; revisão jurídica antes de publicar | — |
| Regulatório | LGPD e confidencialidade de contratos | Baixa a média | Alto | Termo com o condomínio como controlador; nada de morador; cláusula de preços desde o início | — |
| Técnico | Leitura de pasta real muito pior que a do corpus | Média a alta | Alto | Medir com chave de API e documentos reais; separar a pasta à mão no início | Abaixo de 40% sem revisão (K5) |
| Técnico | Falso positivo | Média | Alto | Revisão proporcional ao risco; parada automática (K8) | Precisão abaixo de 70% |
| Técnico | Carga de revisão não cai | Média | Alto | Subir a leitura automática; rever escopo ou preço (K6) | Mais de 2 horas por condomínio por mês |
| Conflito de interesse | Tentação de receita de fornecedor ou indicação paga | Baixa hoje, cresce com a escala | Fatal para a marca | Proibição em contrato e em D89; sem exceção | Primeira proposta de "parceria" com fornecedor |
| Conflito de interesse | Taxa sobre economia incentivar a inflar números | Média | Alto | Só sobre economia realizada, medida por método publicado e revisada por papel separado | Contestação de uma medição |
| Dependência | Administradora dificulta a pasta | Média | Alto | Extrato direto; escolher condomínios com pasta digital | Atraso recorrente |
| Dependência | ERPs oferecem conferência gratuita ao síndico | Média, em 12 a 24 meses | Alto | Independência como marca; referência de preços; relação direta com o síndico | Anúncio de portal do síndico com "auditoria" |
| Dependência | Fornecedor único de IA e termos do executável embutido | Baixa | Médio | Cliente único de IA já isola a troca; revisão jurídica de D54 | Mudança de preço ou de termos |
| Dependência | WhatsApp, quando entrar | Baixa hoje | Médio | Só canal oficial; nunca caminho único | — |

---

## 3. Uma página

**Problema.** O dinheiro do condomínio é de todos e quase ninguém o confere. Quem opera os pagamentos (a administradora) é quem prepara a prestação de contas; o síndico aprova sem tempo; o conselho fiscal é voluntário e olha por amostragem. Em São Paulo capital, um condomínio médio movimenta cerca de R$ 804 mil por ano [CÁLCULO].

**Solução.** Conferência contínua de cada pagamento contra contrato, nota, extrato e índice. Só o que diverge chega à pessoa, com o documento, a conta e o valor. A pessoa decide; o sistema nunca paga, contrata ou envia.

**Posicionamento.** Para o síndico profissional que responde por vários condomínios, a controladoria independente do condomínio: todo pagamento conferido, por alguém que só trabalha para o condomínio. Diferente do sistema da administradora, que confere o próprio trabalho.

**Marca.** Guardião com método: preciso, calmo, sem acusar. "Indício" e "divergência", nunca "fraude". O agente fala como a marca, sem nome de pessoa. Nome em teste nas entrevistas: Confere, Ciente e Lastro contra CondoOS. Visual escuro com acento verde-esmeralda, documento original em claro.

**Experiência.** Briefing do dia como entrada; cartão de decisão com ordem fixa (valor, divergência, evidência, conta, certeza, ação, prazo); conversa com citação; quatro destinos de navegação; no máximo 3 interrupções por semana por pessoa. Silêncio quando tudo bate.

**Arquitetura.** Esteira determinística com IA em pontos delimitados: 12 regras em código, IA na leitura de documentos e na conversa, números sempre conferidos por código. Seis módulos: Ingestão, Registro do condomínio, Conferência, Contratos e Renegociação, Prazos, Prioridade. Isolamento por condomínio no banco, trilha que não se apaga, política que nega ação externa por padrão. Já construído.

**Modelo de negócio.** Assinatura por condomínio em faixas de despesa (hipótese: R$ 390 a R$ 890 por mês), mais 20% da economia realizada e medida em renegociação. Nunca receita de fornecedor ou de administradora. Custo de IA estimado em R$ 18 por condomínio por mês; o custo que pesa é a revisão humana. Margem bruta estimada de 66% hoje e 83% na meta [CÁLCULO com premissas].

**Roadmap.** 0 a 3 meses: provar que há o que achar (5 pastas reais, 24 entrevistas, código congelado). 3 a 6: provar que pagam (5 a 10 condomínios; comparação de propostas). 6 a 12: provar que repete (40 condomínios, cerca de R$ 20 mil por mês).

**Métricas.** Norte: retorno confirmado do condomínio, isto é, divergências corrigidas mais economia realizada, sobre o valor pago. Apoio: taxa de achados (meta de 1,5% da despesa), precisão (70%), leitura sem revisão (60% e depois 75%), horas de revisão por condomínio (até 2), retenção em 6 meses (90%).

**O que não se sabe.** A taxa de achados em pastas reais. Quantos síndicos aceitam ser conferidos. Se a decisão é por carteira. Como o sistema lê uma pasta real. Nenhum desses quatro se responde com código.

---

## 4. Próximos 30 dias

| Semana | O que fazer | Feito quando |
|--------|-------------|--------------|
| 1 | Listar 30 síndicos profissionais de São Paulo que você alcança (rede, indicações, associações) | Lista com nome, carteira estimada e caminho de contato |
| 1 | Contratar o advogado: termo de piloto, LGPD, cláusula de preços, termos do executável embutido (D54), uso de "auditoria" | Escopo e prazo combinados |
| 1 | Chave de API em ambiente de piloto separado | Medição de acurácia da extração e avaliação da conversa rodadas, com resultado registrado |
| 1 a 2 | Uma página em linguagem simples: o que fazemos com os seus documentos | Texto aprovado pelo advogado |
| 1 a 4 | **Dez entrevistas** com o roteiro da Fase 1 e o teste de nome da Fase 3, começando por síndicos profissionais | Dez registros, com as respostas às hipóteses H1 a H8 |
| 2 a 4 | Em cada entrevista, observar primeiro: ele entregaria a pasta? Decide sozinho pela carteira? Como reage à ideia de ser conferido? | Contagem das três respostas |
| 2 a 4 | Pedir a primeira pasta de 12 meses (condomínio recém-assumido) | Uma pasta recebida, com termo assinado |
| 3 a 4 | Código, só o necessário: carteira do síndico e resumo de entrada | Um diagnóstico apresentável |
| 4 | Revisão: quantas conversas, quantas pastas, o que as entrevistas disseram sobre as objeções 3 e 8 | Decisão registrada: seguir, ajustar o comprador ou ajustar a oferta |

Marco dos 30 dias: **dez entrevistas feitas, uma pasta real recebida e as duas medições pendentes rodadas.** Se as dez entrevistas não acontecerem, o problema não é o produto.

---

## 5. Fechamento

### Resumo

- **Dez objeções, duas sem boa resposta**: "você tem produto e nenhuma conversa com cliente" e "por que eu pagaria para ser auditado". As duas só se respondem em campo.
- **A defesa que se sustenta é a independência**: os ERPs não podem conferir o próprio cliente. Tudo o que é técnico é copiável.
- **O risco fatal é a taxa de achados**, e ela se mede em semanas, com cinco pastas.
- **A proposta inteira cabe em uma página** (seção 3) e termina em quatro incógnitas que código não resolve.
- **Os próximos 30 dias têm um marco simples**: dez entrevistas, uma pasta real, duas medições.

### Decisões

Não há decisão nova pendente nesta fase. As decisões de D88 a D93 estão em `docs/decisions.md`; o roadmap e o protocolo de piloto foram atualizados para refleti-las.

Ficam abertas, para quando houver dados: o nome (depois de 20 entrevistas), o preço (depois de medir o valor) e a decisão sobre mão de obra (depois do que o piloto coletar).

### O que eu descartaria, em uma lista

Voz. Interface gerada livremente. Autonomia para ação externa. Aprovação por WhatsApp. Portal do condômino. Modo assembleia. Cobrança e inadimplência. Concierge. Manutenção de ativos. Marketplace e qualquer receita de fornecedor. "Multiagentes" como arquitetura. "CFO do condomínio" e "copiloto" como categoria. E, pelos próximos três meses, qualquer funcionalidade nova que não destrave o piloto.

---

## 6. Índice da reconcepção

| Fase | Arquivo | Decisão |
|------|---------|---------|
| 1. Mercado, personas e dores | `fase-1-mercado-personas-dores.md` | D88 |
| 2. Posicionamento e estratégia | `fase-2-posicionamento-estrategia.md` | D89 |
| 3. Marca | `fase-3-marca.md` | D90 |
| 4. Experiência | `fase-4-experiencia.md` | D91 |
| 5. Módulos e arquitetura | `fase-5-sistema.md` | D92 |
| 6. MVP, roadmap e validação | `fase-6-mvp-roadmap-validacao.md` | D93 |
| 7. Ataque e síntese | este arquivo | — |

As divergências R1 a R20 com os documentos de planejamento estão listadas ao fim de cada fase. Resolvidas: R1, R2, R3, R4, R5, R6, R8, R9, R10, R11, R17, R19, R20. Abertas, sem urgência: R7 (telas da administradora), R12 e R13 (nome), R14 (carteira do síndico, a construir), R15 (condômino e assembleia, adiados), R16 (vocabulário), R18 (tabelas propostas, sem migração).
