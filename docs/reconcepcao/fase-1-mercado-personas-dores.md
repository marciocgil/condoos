# Reconcepção do CondoOS — Fase 1: mercado, personas e dores

Data: 11/11/2026 · Origem: "Prompt Mestre — Reconcepção do CondoOS" · Estado: **respondida pelo Marcio em 11/11/2026 (D88)**; as três decisões da seção 7 foram: sim, sim, e seguir para a Fase 2 validando em paralelo.

Este documento é análise, não decisão. Nada aqui altera `docs/decisions.md`, o roadmap ou o código. Onde a análise contraria uma decisão já tomada, a divergência está registrada na seção 8.

Marcação usada: **[FATO]** tem fonte na seção 10; **[CÁLCULO]** é conta minha sobre fatos, com a conta à vista; **[HIPÓTESE]** precisa de validação em campo; **[PREMISSA]** foi assumida para seguir.

Limite desta análise: usei o repositório (código, `docs/`, `docs/condoos-planning/`) e pesquisa pública feita hoje. Não tenho acesso a conversas de outras sessões. O business plan, o modelo de monetização e o GTM citados no prompt não estão no repositório (a busca só encontra hipóteses de preço na Especificação Mestra §22.4). Se existirem em arquivo, vale anexar antes da Fase 2.

---

## 0. As cinco perguntas que mais mudariam as conclusões

| # | Pergunta | Por que muda tudo | Premissa usada sem a resposta |
|---|----------|-------------------|-------------------------------|
| 1 | Qual é a cidade inicial e quantos síndicos profissionais e administradoras você alcança por relacionamento em 60 dias? | O mercado é local e vendido por confiança. A rede define o beachhead mais que o tamanho do mercado. | [PREMISSA] São Paulo capital. |
| 2 | Você terá pastas reais de prestação de contas (12 meses, com autorização) de ao menos 5 condomínios? | Sem dado real, a taxa de achados por condomínio é desconhecida, e ela é a variável que decide se o negócio existe. | [PREMISSA] Sim, no piloto (`docs/pilot-protocol.md`). |
| 3 | Qual preço e qual forma de cobrança estão no business plan? | O teto de preço calculado na seção 1.4 é baixo. Se o plano supõe mais, um dos dois está errado. | [PREMISSA] Preço ainda aberto. |
| 4 | A posição "o condomínio é o cliente; a administradora é colaboradora opcional" (D73) é definitiva? | Em 2026 os dois maiores ERPs lançaram auditor por IA para a administradora (seção 2). Isso reforça D73, mas fecha a porta de vender o auditor à administradora. | [PREMISSA] D73 vale. |
| 5 | Qual o fôlego (meses de caixa, tamanho do time) e a meta de 12 meses? | Define se dá para sustentar venda consultiva de ticket baixo ou se é preciso um canal que multiplique (síndico profissional). | [PREMISSA] Fundador solo com agentes de código, sem captação. |

---

## 1. Mapa do mercado

### 1.1 Tamanho

| Indicador | Valor | Tipo | Observação |
|-----------|-------|------|------------|
| Condomínios ativos no Brasil | 327.248 | [FATO] Censo Condominial 2025/26 (uCondo, sobre IBGE e Receita) | Fonte setorial, não oficial. Outras contagens: 130.099 CNPJs no CNAE 8112-5/00 (LeadJet, set/2026) e "mais de 520 mil" (INCC, citado pela Group). Faixa real: 130 mil a 520 mil. Uso 327 mil como centro. |
| Moradores em condomínios | cerca de 39 milhões | [FATO] mesmo censo | |
| Endereços dentro de condomínios | 13,3 milhões (12,4% dos endereços) | [FATO] IBGE/CNEFE, Censo 2022 | Conta endereços, inclui não residenciais. |
| População em apartamentos | 12,5% | [FATO] IBGE, Censo 2022 | Em "casa de vila ou condomínio": 2,4% (era 1,6% em 2010). |
| Unidades por condomínio (média Brasil) | cerca de 41 | [CÁLCULO] 13,3 mi ÷ 327 mil | A média esconde a cauda: a maioria é pequena. |
| São Paulo capital: condomínios | 31,1 mil (92% residenciais) | [FATO] Mapa dos Condomínios 2025, Lello | Eram 23 mil em 2014 (+34,8%). |
| São Paulo capital: movimentação | R$ 25 bilhões/ano | [FATO] Lello | |
| São Paulo capital: cota média | R$ 983/mês | [FATO] Lello | |
| Minas Gerais | mais de 51 mil condomínios, 2º estado | [FATO] Censo Condominial | O número do estado de SP não apareceu na pesquisa. |
| Cota média Brasil | R$ 516 (uCondo) ou R$ 828 (Superlógica) | [FATO] duas bases, metodologias diferentes | Alta de 24,9% em três anos (uCondo); reajuste de 6,8% em 2025, acima da inflação. |
| Inadimplência | 6,28% média em 2025 (Superlógica); 11,95% no 1º sem. de 2025 (uCondo) | [FATO] | Não comparáveis entre si. Prejuízo estimado: R$ 7 bi/ano (Superlógica). |
| Condomínios com síndico profissional | cerca de 20% (ABRASSP); 13% a 14% entre associados da AABIC em SP | [FATO] estimativas de associação | Era 6% em 2014. |
| Administradoras | 31 mil a 48 mil CNPJs no CNAE 6822-6/00 | [FATO] bases comerciais | O CNAE inclui imobiliárias e gestão de imóveis. **Não achei contagem confiável de administradoras de condomínio.** |

**Arrecadação nacional.** [CÁLCULO] 13,3 mi de endereços × cota média × 12 = R$ 82 bi/ano (com R$ 516) a R$ 132 bi/ano (com R$ 828). As cifras de "R$ 250 bi" (Finsiders) e "R$ 300 bi" (INCC) circulam na imprensa sem método publicado e não consigo reproduzi-las. Eu trabalharia com **R$ 80 a 130 bi/ano**.

**Síndicos profissionais.** [CÁLCULO] 327 mil × 20% = 65 mil condomínios; ÷ 8 condomínios por síndico profissional (Datafolha) = **cerca de 8 mil síndicos profissionais no Brasil**. Em São Paulo capital: 31,1 mil × 13,5% ÷ 8 = **cerca de 500**. [HIPÓTESE] O número é pequeno, e isso é uma boa notícia: são poucas centenas de compradores que controlam, cada um, oito orçamentos.

### 1.2 O condomínio médio, em reais

| | São Paulo capital | Brasil |
|---|---|---|
| Receita anual por condomínio | R$ 804 mil [CÁLCULO] R$ 25 bi ÷ 31,1 mil | R$ 250 mil a 400 mil [CÁLCULO] R$ 82–132 bi ÷ 327 mil |
| Unidades | cerca de 68 [CÁLCULO] R$ 804 mil ÷ 12 ÷ R$ 983 | cerca de 41 |

### 1.3 Para onde vai o dinheiro

Composição da despesa (Lello, 2025) [FATO]: folha e encargos **48%**, concessionárias (água, luz, gás) **21%**, contratos de conservação e manutenção **17%**, seguros e despesas administrativas **10%**.

```
Condôminos ──cota (boleto/Pix)──► Conta do condomínio ──► Folha própria ou terceirizada (48%)
   │  inadimplência 6–12%            ▲        │          ├► Concessionárias (21%)
   │                                 │        │          ├► Contratos de manutenção e conservação (17%)
   └── garantidora antecipa ─────────┘        │          ├► Seguros e administrativo, inclui a taxa da administradora (10%)
       (cobra taxa sobre a receita)           │          └► Fundo de reserva e obras
                                              │
        Quem ordena o pagamento: administradora (opera) + síndico (aprova)
        Quem confere depois: conselho fiscal (voluntário, por amostragem) e assembleia (uma vez por ano)
```

O ponto estrutural: **quem opera o pagamento é quem prepara a prestação de contas.** A conferência independente é voluntária, mensal por amostragem e feita por leigos. Pela pesquisa Datafolha/Superlógica, 67% dos síndicos dizem ser os únicos responsáveis pelas decisões financeiras [FATO].

### 1.4 Quanto dinheiro o auditor consegue alcançar (e o teto de preço)

Onde o auditor atual atua: contratos (17%) e administrativo/seguros (10%) = 27% da despesa. A folha entra quando é terceirizada (vira contrato); concessionárias quase não são negociáveis.

| Cenário, condomínio médio de SP (R$ 804 mil/ano) | Base alcançável | Economia a 3% da base | Economia a 5% da base |
|---|---|---|---|
| Só contratos e administrativo (27%) | R$ 217 mil | R$ 6,5 mil/ano | R$ 10,9 mil/ano |
| Com mão de obra terceirizada (75%) | R$ 603 mil | R$ 18,1 mil/ano | R$ 30,2 mil/ano |

[HIPÓTESE] Os 3% a 5% são suposição minha: **não existe medição publicada da taxa de achados com valor em condomínios**. É o número mais importante do negócio e hoje ninguém o conhece.

[CÁLCULO] Se o cliente aceita pagar 20% a 30% do valor entregue, o preço cabe em **R$ 110 a R$ 750 por mês por condomínio médio de São Paulo**, ou R$ 1,60 a R$ 11 por unidade/mês. No condomínio médio do Brasil (receita de um terço disso), o teto cai para R$ 35 a R$ 250 por mês.

Conclusões que eu tiro:

1. **Venda direta a condomínio pequeno não fecha a conta.** Um ticket de poucas centenas de reais não paga venda consultiva.
2. **O alvo precisa ter orçamento acima de cerca de R$ 1 milhão por ano** (100 unidades ou mais em capital, ou padrão alto), onde 3% são R$ 20 mil ou mais.
3. **A mão de obra terceirizada é onde está o dinheiro** (48% da despesa) e o auditor atual quase não olha para ela. Isso pesa na Fase 6.
4. **O canal tem de multiplicar**: um síndico profissional traz oito condomínios numa venda só.

---

## 2. Panorama competitivo

| Grupo | Exemplos | Proposta | Receita | Forças | Lacunas |
|-------|----------|----------|---------|--------|---------|
| ERP de administradora | **Superlógica** (130 mil condomínios, 6,3 mi de unidades; lançou o Nexus em ago/2026, "ecossistema AI-native" de agentes), **Group Software** (GIA: agentes de atendimento por WhatsApp, documentos, assembleia e **"Auditor de Fechamento"**, out/2026; Group Pay busca NF por CNPJ) | Sistema de registro da administradora, agora com agentes | Assinatura da administradora + serviços financeiros (conta, boleto, crédito) | Têm o dado, a distribuição e o caixa. Superlógica diz atender mais da metade do mercado endereçável | O cliente é a administradora. A IA serve à eficiência dela: fechar a pasta mais rápido. Não confere preço de mercado, reajuste contratual nem a própria administradora |
| Apps para condomínio e síndico | **uCondo** (7 mil condomínios; assistente Móra por WhatsApp resolve 66% das dúvidas, segundo a empresa), TownSq, Condomob, Acolweb | Comunicação, reservas, boletos, prestação de contas no app | Assinatura por condomínio ou unidade | Canal direto com síndico e morador | Sistema de registro e atendimento. "Detecção de anomalia" aparece em material de venda, sem evidência |
| Administradoras com tecnologia própria | **Lello** (maior do país; IA classifica contas com mais de 90% de acerto, segundo ela) | Serviço completo | Taxa de administração | Marca, dados (Data Lello) | Mesmo conflito: confere o próprio trabalho |
| Fintechs | **CondoConta** (13 mil condomínios, 690 administradoras parceiras, crédito), PJBank (Superlógica), garantidoras de receita | Conta, crédito, antecipação da inadimplência | Tarifa, juros, taxa sobre a receita garantida | Resolvem dor de caixa com ROI imediato | Não olham a despesa. Inadimplência já é mercado disputado |
| Cotações e marketplaces | **CoteiBem** (SíndicoNet: 5 mil fornecedores, 360 especialidades), oHub | Pedido de cotação a fornecedores cadastrados | **Pago pelo fornecedor** (planos a partir de R$ 84/mês no CoteiBem) | Base de fornecedores | Quem paga é quem vende: não há incentivo a baixar preço nem referência de preço justo |
| Auditoria tradicional | Escritórios de auditoria condominial (ex.: Finacc) | Parecer sobre as contas, pontual | Honorário por trabalho | Independência e assinatura de contador | Caro, pontual, depois do fato; não acompanha contrato nem reajuste |
| IA genérica | ChatGPT, Claude, Gemini | Síndico envia o balancete e pergunta | Assinatura pessoal | Custo quase zero, já é hábito | Sem memória dos contratos, sem cruzamento com extrato, sem trilha, sem garantia numérica |

Não verifiquei preços de nenhum concorrente (nenhum publica). Garantidoras e TownSq/Condomob ficaram sem números atuais.

### O espaço em branco

**Controle independente e contínuo da despesa, do lado do condomínio**: cada pagamento conferido contra contrato, nota, extrato e índice, com economia medida e trilha. Ninguém ocupa isso porque todos os grandes vendem para a administradora, e administradora não compra ferramenta para ser auditada.

Três ressalvas sérias:

1. **O "auditor por IA" como recurso deixou de ser diferencial em 2026.** O Auditor de Fechamento da Group já roda verificadores de duplicidade e de despesa fora do padrão de 12 meses, com veredito "pronto para publicar / com ressalvas / não publicar" [FATO]. O que continua exclusivo é a **independência** (de que lado o auditor está) e a **profundidade** (contrato, reajuste, CNPJ, preço), não a existência de IA.
2. **Espaço vazio pode ser espaço sem comprador.** O condomínio não tem linha de orçamento para "auditoria contínua", o síndico orgânico troca a cada um ou dois anos e a decisão passa por assembleia ou conselho.
3. **Quem tem o dado é o concorrente.** A tese "os dados entram sozinhos" depende de exportar do ERP da administradora ou de Open Finance. Hoje o CondoOS recebe por upload e e-mail.

---

## 3. Personas

| Persona | Contexto | Objetivo | Pelo que é cobrado | Ferramentas hoje | Nível digital | Medos |
|---------|----------|----------|--------------------|------------------|---------------|-------|
| **Síndico profissional** | Cerca de 8 condomínios, mais de 750 unidades, 32 h/semana [FATO, Datafolha]. 70% começaram como síndico morador | Reter e ganhar contratos; não ter conta reprovada | Reeleição, taxa sem aumento, ausência de crise | Portal da administradora, WhatsApp, planilha, Google e YouTube como fonte (93% e 74%) | Médio a alto | Responder com patrimônio próprio; perder o prédio na assembleia; depender de uma administradora que não controla |
| **Síndico orgânico (morador)** | 1 ou 2 condomínios, cerca de 103 unidades, 19 h/semana além do emprego [FATO] | Passar o mandato sem problema | Vizinhos, informalmente | WhatsApp, portal da administradora, papel | Baixo a médio | Ser acusado; assinar o que não entende; conflito com vizinho |
| **Gerente de carteira** | Atende dezenas de condomínios [HIPÓTESE: 15 a 40; não achei fonte] | Fechar todas as pastas no prazo | Prazo de fechamento, reclamações, perda de cliente | ERP (Superlógica, Group), e-mail, WhatsApp | Médio | Erro que vira perda do condomínio; mais uma ferramenta para alimentar |
| **Dono ou diretor de administradora** | Margem apertada, taxa por condomínio, receita financeira crescente | Crescer a carteira sem crescer a folha | Churn, margem por condomínio, condomínios por gerente | ERP, BI, banco | Médio | Ferramenta que exponha falhas ao cliente; ser desintermediado |
| **Conselho fiscal** | Voluntário, confere a pasta uma vez por mês, por amostragem | Dar o parecer sem se comprometer | Parecer anual (Código Civil, art. 1.356) | Pasta em PDF ou papel | Baixo a médio | Assinar algo errado; atrito com o síndico |
| **Condômino** | Paga a cota; olha o boleto, não o balancete | Pagar o justo e saber para onde vai | — | Boleto, grupo de WhatsApp | Variado | Aumento e rateio extra; ser passado para trás |
| **Zelador ou gerente predial** | Executa, recebe fornecedor, conhece o prédio | Prédio funcionando | Chamados resolvidos | WhatsApp, caderno | Baixo | Ser culpado; perder o emprego na terceirização |
| **Fornecedor** | Vende ao síndico por relacionamento; recebe com atraso | Renovar sem concorrência | Receita recorrente | WhatsApp, e-mail, NF | Baixo a médio | Cotação aberta que derruba preço; calote |

Dois ajustes às premissas do prompt:

- **O síndico tem em média 42 anos, não 65** [FATO, Datafolha/Superlógica; amostra de 350, pesquisa encomendada por um concorrente, então serve como indício]. O "síndico de 65 anos" existe, mas não é o centro da distribuição. Isso pesa no teste de nome da Fase 3.
- **74% já usam alguma plataforma de gestão** [FATO, mesma pesquisa], e os recursos mais usados são prestação de contas, boletos e lançamento de despesas. "Baixa maturidade digital" descreve a ponta (zelador, fornecedor, parte dos conselheiros), não o comprador.

O que os documentos internos dizem sobre personas e público está na seção 8.

---

## 4. Mapa de dores (JTBD)

| # | Dor (hipótese do prompt) | Quem sente | "Quando…, quero…, para…" | Veredito | Por quê |
|---|--------------------------|-----------|---------------------------|----------|---------|
| 1 | Despesas sem conferência, duplicidades, notas incoerentes | Síndico, conselho | Quando aprovo os pagamentos do mês, quero saber quais não batem com contrato, nota e extrato, para não assinar erro | **Manter**, reescrita | O sistema nunca diz "desvio" ou "fraude" (regra do produto). A dor vendável é "aprovei sem conseguir conferir" |
| 2 | Contratos acima do mercado, reajustes não questionados | Síndico, conselho | Quando um contrato reajusta ou renova, quero saber se o índice e o preço estão certos, para negociar com base | **Manter** | Reajuste errado é verificável por conta (regra já existe). "Acima do mercado" exige referência de preço que ainda não existe |
| 3 | Inadimplência | Síndico, condômino adimplente | Quando o caixa aperta, quero receber sem brigar com o vizinho | **Manter como dor, descartar como alvo inicial** | Dor real (6% a 12%), mas já tem garantidoras, fintechs e o próprio ERP. Exige dado e operação de cobrança |
| 4 | Prestação de contas opaca | Condômino, conselho | Quando recebo o balancete, quero entender em dois minutos, para confiar | **Manter**, como efeito | Ninguém paga por transparência em si; paga-se por não ser contestado |
| 5 | Manutenção reativa, ativos sem histórico | Zelador, síndico | Quando um equipamento quebra, quero o histórico e o contrato | **Adiar** | Dado não existe em formato nenhum; ROI difícil de provar |
| 6 | Obrigações vencendo (AVCB, laudos, seguro) | Síndico | Quando um prazo legal se aproxima, quero ser avisado com antecedência | **Manter, pequeno** | Baixa frequência, alto medo. Bom complemento (a Agenda já cobre parte), não é a cunha |
| 7 | Assembleias improdutivas | Síndico | — | **Descartar por ora** | Uma ou duas vezes por ano; Group e apps já fazem edital e ata |
| 8 | Comunicação caótica | Todos | — | **Descartar** | Alta frequência, disposição a pagar quase nula, terreno dos apps |
| 9 | Consumo de água, energia e gás | Síndico | Quando a conta sobe, quero saber se é consumo, tarifa ou vazamento | **Manter como hipótese** | 21% da despesa; a conta chega em PDF e a leitura é barata. Subestimada no prompt |
| 10 | Sobrecarga do gerente de carteira | Gerente, dono da administradora | Quando fecho 30 pastas, quero ver só as exceções | **Real, mas é a dor que os ERPs estão resolvendo** | Nexus e GIA miram exatamente isso. Entrar aqui é disputar com quem tem o dado |
| 11 | Responsabilidade pessoal do síndico | Síndico | Quando eu sair do cargo, quero provar que fui diligente | **Manter, promover** | É o motivo emocional de compra. A trilha de decisão já existe no produto |
| 12 | **(nova) Mão de obra sem gestão**: postos, horas extras, encargos, terceirização | Síndico, conselho | Quando pago a terceirizada, quero saber se o que foi faturado é o que foi contratado e entregue | **Adicionar** | 48% da despesa. Maior linha do orçamento e a menos conferida |
| 13 | **(nova) Perda de memória na troca de síndico** | Síndico novo, conselho | Quando assumo, quero saber quais contratos, prazos e pendências herdei | **Adicionar como hipótese** | Rotatividade alta apaga o histórico; o "gêmeo digital" resolve como subproduto |
| 14 | **(nova) Dependência da administradora** | Síndico, conselho | Quando a administradora me manda a pasta, quero uma segunda opinião que não seja dela | **Adicionar** | É a razão de existir do espaço em branco |

---

## 5. Matriz de priorização

Notas de 1 a 5 (5 é melhor). São julgamento meu [HIPÓTESE], para serem corrigidas com as entrevistas.

| Dor | Frequência | Intensidade | Disposição a pagar | Facilidade de provar ROI | Dados disponíveis | Total |
|-----|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 Despesas sem conferência | 5 | 3 | 3 | 5 | 5 | **21** |
| 2 Contratos e reajustes | 3 | 4 | 4 | 5 | 4 | **20** |
| 3 Inadimplência | 5 | 5 | 4 | 4 | 2 | **20** |
| 10 Sobrecarga do gerente | 5 | 4 | 4 | 3 | 3 | **19** |
| 12 Mão de obra sem gestão | 5 | 4 | 3 | 3 | 3 | **18** |
| 4 Prestação de contas opaca | 4 | 4 | 3 | 2 | 4 | 17 |
| 9 Consumo | 4 | 3 | 3 | 4 | 3 | 17 |
| 6 Obrigações vencendo | 2 | 5 | 3 | 3 | 3 | 16 |
| 11 Responsabilidade do síndico | 2 | 5 | 4 | 2 | 3 | 16 |
| 14 Dependência da administradora | 3 | 4 | 3 | 2 | 3 | 15 |
| 13 Troca de síndico | 2 | 4 | 2 | 1 | 4 | 13 |
| 5 Manutenção reativa | 3 | 4 | 2 | 2 | 1 | 12 |
| 8 Comunicação caótica | 5 | 3 | 1 | 1 | 1 | 11 |
| 7 Assembleias | 1 | 3 | 2 | 1 | 2 | 9 |

### As cinco primeiras, com leitura crítica

1. **Despesas sem conferência (21).** Dado disponível, ROI contável em reais, é o que o MVP já faz. Fraqueza: intensidade média. Ninguém acorda pensando nisso até aparecer um caso.
2. **Contratos e reajustes (20).** Maior valor por achado e prova matemática. É a ponte natural para a economia medida.
3. **Inadimplência (20).** Nota alta, e mesmo assim **eu não atacaria**: mercado ocupado por quem tem balanço e licença, dado preso no ERP e no banco. Fica como informação no briefing, não como produto.
4. **Sobrecarga do gerente de carteira (19).** Dor real com comprador que tem orçamento, mas é o campo de batalha de Superlógica e Group, e contraria D73. Tratar como **canal a testar**, não como produto.
5. **Mão de obra sem gestão (18).** A aposta nova: é metade do orçamento. Precisa validar se o dado (escala, ponto, medição do contrato) chega ao síndico em formato utilizável.

**Par que eu levaria à Fase 2:** dores 1 e 2 como cunha, 11 e 14 como argumento de venda ("prova de diligência, por alguém que não é a administradora"), 12 como primeira expansão a validar.

**O que eu descartaria agora:** assembleias, comunicação, concierge do condômino e manutenção de ativos. Somam nota baixa, não têm dado e já têm dono.

---

## 6. Plano de validação

### 6.1 Roteiro de entrevista (30 a 40 minutos, sem apresentar o produto)

Regra: perguntar sobre o passado e o concreto, nunca "você usaria?".

1. Conte como foi o último fechamento de mês do condomínio, do começo ao fim.
2. Quem olhou cada despesa antes de pagar? E depois de paga?
3. Quanto tempo você gastou com a pasta de prestação de contas no mês passado?
4. Quando foi a última vez que encontrou algo errado numa conta ou nota? O que aconteceu depois?
5. E a última vez que soube de um erro que ninguém tinha visto? Como descobriu?
6. Quais são os três maiores contratos do condomínio? Quando foi o último reajuste de cada um e quem conferiu o índice?
7. Quando foi a última vez que você trocou ou renegociou um fornecedor? O que motivou?
8. Como você sabe se um preço está caro?
9. Qual foi a despesa do último ano que mais lhe custou explicar ao conselho ou à assembleia?
10. O que tira o seu sono nessa função? (aberta, sem sugerir)
11. Você já pagou do próprio orçamento do condomínio por auditoria, consultoria ou segunda opinião? Quanto, e quem aprovou?
12. Que ferramentas você abre toda semana para cuidar do condomínio? Qual abandonou e por quê?
13. Como chegam a você os documentos (notas, boletos, contratos)? Por onde você os encaminharia hoje, sem mudar de hábito?
14. Se algo novo custasse R$ X por mês ao condomínio, quem precisaria aprovar e quanto tempo levaria?
15. Sobre o que eu não perguntei e deveria?

Variações: para gerente e dono de administradora, trocar 11 e 14 por "quantos condomínios por gerente", "qual etapa do fechamento mais atrasa" e "o que acontece quando o cliente pede acesso aos dados para um terceiro". Para fornecedor, perguntar como ganha e perde contratos.

### 6.2 Critério por hipótese

| Hipótese | Validada se | Refutada se |
|----------|-------------|-------------|
| H1. Ninguém confere a despesa de forma sistemática | 70% ou mais descrevem conferência por amostragem ou nenhuma (perguntas 2 e 3) | Mais da metade descreve conferência linha a linha feita por alguém |
| H2. Erros com valor acontecem e são lembrados | 50% ou mais contam um caso concreto dos últimos 24 meses, com valor (4 e 5) | Menos de 20% lembram de um caso |
| H3. Reajuste não é conferido | 60% ou mais não sabem dizer quem conferiu o último índice (6) | A maioria confere ou a administradora comprova |
| H4. Existe disposição a pagar do orçamento do condomínio | 30% ou mais já pagaram por auditoria ou segunda opinião, ou citam valor e caminho de aprovação sem hesitar (11 e 14) | Menos de 10%, ou "só com assembleia" como regra |
| H5. Síndico profissional decide sozinho e replica | 60% ou mais dos profissionais dizem contratar ferramenta por conta própria para toda a carteira | A decisão é sempre condomínio a condomínio |
| H6. O medo de responsabilização é motivo de compra | Aparece espontaneamente na pergunta 10 em 40% ou mais | Aparece em menos de 15% |
| H7. Mão de obra é dor percebida | 40% ou mais citam folha ou terceirização em 6, 9 ou 10 | Ninguém cita sem ser induzido |
| H8. A administradora coopera com acesso aos dados | 50% ou mais das administradoras dizem já exportar ou dar acesso a terceiros | A maioria recusa ou cobra |
| H9. A taxa de achados com valor paga o produto (teste com dados, não entrevista) | Em 5 pastas reais de 12 meses, achados confirmados somam 1,5% ou mais da despesa | Menos de 0,5% |

### 6.3 Quantas entrevistas

| Persona | Mínimo | Prioridade |
|---------|:-:|:-:|
| Síndico profissional | 8 | 1ª onda |
| Síndico orgânico | 6 | 1ª onda |
| Conselheiro fiscal | 5 | 1ª onda |
| Dono ou diretor de administradora | 5 | 1ª onda |
| Gerente de carteira | 5 | 2ª onda |
| Fornecedor | 4 | 2ª onda |
| Condômino | 4 | 2ª onda |
| Zelador ou gerente predial | 3 | 2ª onda |

Primeira onda: 24 entrevistas em três a quatro semanas. Parar uma persona antes do mínimo só se as três últimas não trouxerem nada novo. H9 corre em paralelo e vale mais que todas as entrevistas juntas.

---

## 7. Fechamento da Fase 1

### Resumo

- **O mercado é grande em reais e pequeno por cliente**: cerca de 327 mil condomínios e R$ 80 a 130 bi/ano [CÁLCULO], mas o condomínio médio de São Paulo gira R$ 804 mil/ano e o do Brasil, um terço disso.
- **O teto de preço é baixo**: com economia de 3% a 5% da base alcançável [HIPÓTESE], cabem R$ 110 a R$ 750 por mês por condomínio médio de São Paulo. Só fecha com condomínios acima de R$ 1 milhão/ano e com canal que multiplique.
- **"Auditor por IA" virou recurso de ERP em 2026** (Group GIA, Superlógica Nexus), sempre a serviço da administradora. O que sobra de exclusivo é a independência e a profundidade (contrato, reajuste, preço).
- **O comprador mais promissor é o síndico profissional**: cerca de 8 mil no país e 500 em São Paulo [CÁLCULO], oito condomínios cada, decide finanças sozinho e teme responder pessoalmente.
- **Cunha recomendada**: despesas e contratos (dores 1 e 2), vendidos como prova de diligência independente (11 e 14); mão de obra (12) é a expansão a validar. Inadimplência, comunicação, assembleia e manutenção ficam fora.

### Três decisões que preciso de você

1. **Beachhead**: confirma São Paulo capital e o síndico profissional (carteira de 5 ou mais condomínios, orçamento médio acima de R$ 1 milhão/ano) como primeiro comprador a validar? Alternativa: sua cidade ou rede, se for outra.
2. **Administradora**: mantém D73 (condomínio é o cliente) e trata a administradora só como fonte de dados e canal a testar, sabendo que isso significa não vender o auditor a ela?
3. **Ordem do trabalho**: antes da Fase 2, roda H9 (cinco pastas reais de 12 meses) e a primeira onda de entrevistas, ou segue para a Fase 2 com as premissas e valida em paralelo? Eu rodaria H9 primeiro: ela pode invalidar o teto de preço para cima ou para baixo.

### Principais riscos

- **Taxa de achados desconhecida.** Se ficar abaixo de 0,5% da despesa, não há ROI que sustente preço. É o risco número um e é barato de medir.
- **Acesso ao dado.** A pasta está no ERP da administradora, que não tem interesse em ser auditada. Sem exportação ou Open Finance, a "ingestão passiva" vira upload manual, que é o anti-padrão da tese.
- **Comprador sem orçamento e com mandato curto.** Síndico orgânico troca; a decisão pode exigir conselho ou assembleia; churn por eleição.
- **Incumbentes com dado e distribuição.** Superlógica e Group podem aprofundar o auditor e oferecê-lo "de graça" dentro do ERP. A defesa é a independência, que eles não conseguem copiar.
- **Fontes fracas.** Quase todo número do setor vem de empresas com interesse comercial (uCondo, Superlógica, Lello). Os cálculos acima herdam essa fragilidade.

---

## 8. O que os documentos internos já dizem, e onde esta análise diverge

Leitura feita em 11/11/2026 sobre a Especificação Mestra ("Spec"), o Plano Diretor ("Plano"), `docs/03-decisions-register.md`, `docs/pilot-protocol.md`, `docs/product-roadmap.md` e D73–D77 de `docs/decisions.md`. As seções técnicas da Spec (§10, §11, §13, §14, §16, §20, §21) foram só consultadas por busca.

### 8.1 O que os documentos internos não têm (e esta fase acrescenta)

- **Nenhum dimensionamento de mercado**: sem número de condomínios, TAM, preço, ticket ou meta de economia. A Spec recusa meta de economia "anterior ao diagnóstico" (§17.6) e declara que não é "comprovação de viabilidade de mercado".
- **Nenhum concorrente nomeado** em todo o repositório.
- **Nenhum business plan, plano de GTM ou modelo de monetização fechado.** Há só hipóteses na Spec §22.4 (taxa sobre economia realizada, fee de diagnóstico ou híbrido; assinatura por condomínio) e a decisão aberta "Plano D-12: medir valor antes de precificar", prevista para o gate G5.
- **KPIs por persona** não existem (há por capacidade e por pilar).
- O único dado quantitativo da Spec, 19 h/semana do síndico morador e 32 h do profissional (§2.3), aparece lá sem fonte. **A fonte é a pesquisa Datafolha/Superlógica** citada na seção 3.

### 8.2 Onde esta análise confirma o que já estava decidido

| Tema | Documento interno | Esta análise |
|------|-------------------|--------------|
| Cliente é o condomínio; administradora é colaboradora opcional | D73; Spec §1.5; Plano §1.3 | Confirma, e acrescenta o motivo competitivo: os ERPs lançaram auditor para a administradora em 2026 |
| Sem comissão oculta de fornecedor, sem ranking pago | Spec §22.4 | Confirma: o marketplace pago pelo fornecedor (CoteiBem) é o modelo a não copiar |
| Economia só conta quando medida, estágios separados | D76, D81, D84 | Confirma: a taxa de achados com valor (H9) é a variável que falta |
| "Integrar antes de substituir"; não é ERP | Spec §1.4, §4.2 | Confirma |
| Linguagem: "indício", nunca "fraude" ou "desvio" | Regra do produto | A dor 1 foi reescrita por isso |

### 8.3 Divergências, para você decidir (nada foi alterado)

| # | Divergência | Documento interno | Esta análise | Peso |
|---|-------------|-------------------|--------------|------|
| R1 | **Qual é a dor central** | Spec §1.1 e hipótese H-01: a dor é **coordenação** (descobrir, cobrar, verificar, prestar contas), a validar por shadowing | A matriz da seção 5 põe **controle da despesa** no topo e joga comunicação, assembleia e manutenção para baixo. Coordenação tem frequência alta, mas ROI difícil de provar e dado indisponível | Alto: muda a ordem do roadmap (Operate antes ou depois de Optimize) |
| R2 | **Comprador** | Spec §19.1: "condomínio médio com documentação organizada e síndico acessível"; §23.2 deixa aberto morador, profissional ou conselho | **Síndico profissional com carteira**, condomínios acima de R$ 1 milhão/ano, pela conta do teto de preço (seção 1.4) | Alto |
| R3 | **Tamanho do piloto e das entrevistas** | `pilot-protocol`: até 3 condomínios, 8 a 12 entrevistas | O prompt pede 5 a 10 condomínios; proponho 24 entrevistas na primeira onda e 5 pastas reais para H9 | Médio |
| R4 | **Canais da tese do prompt** | WhatsApp só oficial e tardio (FR-035, P1, depois do core estável); briefing só dentro do app (D82); não há canal de voz; Open Finance é "evolutivo", e o piloto não pede acesso bancário | A tese do prompt põe WhatsApp, voz e Open Finance no centro. A Fase 1 não decide isso, mas a Fase 4 vai colidir com D82 e com a ordem do Plano | Alto, na Fase 4 |
| R5 | **"O sistema age"** | D83: nenhuma ação externa; o despacho não envia nada; pagar, contratar e multar sempre com pessoa | A tese do prompt fala em "sistema de ação" e autonomia até L4. A escala do prompt (L0–L4) também difere da Spec (L1–L5) | Alto, na Fase 4 |
| R6 | **Navegação** | Spec §7.2 recomenda 12 itens de menu, ao lado da diretriz "action-first" | O prompt proíbe menus como centro. A própria Spec já se contradiz aqui | Médio, na Fase 4 |
| R7 | **Telas da administradora** | O MVP construído tem a administradora (gerente, analista) como operadora central | Com D73 e com os ERPs ocupando esse lugar, essas telas atendem a um usuário que não é o comprador | Médio, na Fase 6 |

R1 e R2 são as que precisam de resposta antes da Fase 2. R4 a R7 ficam registradas para as fases 4 e 6.

---

## 9. O que não foi verificado

- Número de administradoras de condomínio (só o CNAE amplo) e condomínios por gerente de carteira.
- Preços de qualquer concorrente; números atuais de TownSq, Condomob e garantidoras.
- Número de condomínios do estado de São Paulo.
- Relatório completo do Censo Condominial e da pesquisa Datafolha (li a cobertura da imprensa, não os originais).
- Qualquer taxa de erro, duplicidade ou sobrepreço em contas de condomínio: não achei estudo.

## 10. Fontes

- IBGE, Censo 2022, características dos domicílios: https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/39239-censo-2022-cerca-de-oito-a-cada-dez-pessoas-moravam-em-casas-mas-cresce-proporcao-de-moradores-em-apartamentos
- IBGE/CNEFE, endereços em condomínios (via SíndicoNet): https://www.sindiconet.com.br/informese/condominios-cnefe-censo-2022-noticias-mercado
- Censo Condominial 2025/26 (uCondo), via Estado de Minas: https://www.em.com.br/economia/economia-digital/2025/12/7317738-economia-digital-redefine-gestao-de-condominios-com-ia-e-dados-estrategicos.html e InfoMoney: https://www.infomoney.com.br/consumo/taxa-de-condominio-sobe-25-no-brasil-e-atinge-media-de-r-516-em-2025/
- Group Software, mercado condominial (327 mil, INCC 520 mil e R$ 300 bi): https://www.groupsoftware.com.br/blog/mercado-condominial/
- Mapa dos Condomínios 2025, Lello: https://www.sindiconet.com.br/informese/mapa-dos-condominios-2025-noticias-radar-lello e https://jovempan.com.br/noticias/brasil/zona-sul-concentra-maior-numero-de-condominios-em-sao-paulo-aponta-levantamento.html
- Composição das despesas (Lello, 2025): https://www.sindiconet.com.br/informese/taxa-de-condominio-noticias-administracao-6
- Inadimplência e cota média (Superlógica): https://www.sindiconet.com.br/informese/taxa-condominial-noticias-mercado e https://diariodocomercio.com.br/economia/taxa-condominio-brasil-aumento-inflacao/
- Superlógica, 130 mil condomínios e Nexus: https://www.sindiconet.com.br/informese/superlogica-nexus-inteligencia-artificial-noticias-administracao
- Group Software, GIA e Auditor de Fechamento: https://www.groupsoftware.com.br/blog/inteligencia-artificial-para-administradoras-de-condominios/ e Group Pay: https://www.groupsoftware.com.br/blog/group-pay/
- uCondo, 7 mil condomínios e Móra: https://www.em.com.br/economia/economia-digital/2026/04/7405308-gestao-digital-de-condominios-avanca-e-movimenta-rs-800-milhoes.html
- Datafolha/Superlógica, Perfil do Síndico Brasileiro: https://www.sindiconet.com.br/informese/quase-a-metade-dos-sindicos-brasileiros-ja-sao-profissionais-noticias-administracao
- Síndico profissional, ABRASSP e AABIC: https://diariodocomercio.com.br/opiniao/artigo/sindico-profissional-carreira-alta-mercado-condominial/ e https://www.ucondo.com.br/blog/cresce-a-demanda-por-sindicos-profissionais-no-brasil
- CondoConta: https://www.sindiconet.com.br/informese/condoconta-detalha-planos-para-alcancar-breakeven-noticias-mercado e "mercado de R$ 250 bi": https://finsidersbrasil.com.br/reportagem-exclusiva-fintechs/condominios-um-mercado-de-r-250-bi-na-mira-das-fintechs
- CoteiBem: https://www.sindiconet.com.br/informese/fornecedores-de-condominios-ganham-ferramenta-no-coteibem-noticias-espaco-coteibem
- CNAE 6822-6/00 e 8112-5/00: https://oportunidados.com.br/cnae/6822600-gestao-e-administracao-da-propriedade-imobiliaria e https://leadjet.com.br/cnae-para-administracao-de-condominios/
- Auditoria tradicional (exemplo): https://www.finacc.com.br/auditoria-condominio
