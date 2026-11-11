# Reconcepção do CondoOS — Fase 4: experiência e paradigma de interação

Data: 11/11/2026 · Estado: **aguardando validação do Marcio** (fases 5 a 7 não iniciadas).

Parte das respostas à Fase 3 (D90): finalistas de nome Confere, Ciente e Lastro; agente sem nome próprio; linguagem visual pelas referências em `docs/reconcepcao/referencias/`. Os exemplos abaixo usam "CondoOS" enquanto o nome não muda.

Marcação: **[FATO]**, **[HIPÓTESE]**, **[PREMISSA]**. Quase tudo nesta fase é desenho, portanto hipótese até ser usado por um síndico. Os valores em reais dos exemplos são fictícios.

Cada item traz o **estado no produto**: *existe*, *parcial*, *não existe* ou *colide com decisão*. Inspecionei a lista de telas e componentes do aplicativo (`web/app/(sindico)`, `web/components/condoos`) e as decisões D82 a D85; não abri cada tela.

**O que mudou em relação às fases anteriores.** Nada foi invalidado. Mas a tese do prompt, levada ao pé da letra, colide com o comprador escolhido em três pontos, e eu recuaria neles (seção 9): voz, interface gerada livremente e WhatsApp como canal de aprovação.

---

## 1. Princípios de experiência

| # | Princípio | Consequência prática |
|---|-----------|----------------------|
| 1 | **Começa pelo que precisa de decisão.** | A primeira tela é o briefing do dia, ordenado por valor em risco e prazo. |
| 2 | **Silêncio é o estado normal.** | Mês sem divergência gera uma linha: "84 pagamentos conferidos, nada a apontar". |
| 3 | **Toda afirmação abre a prova.** | Número, trecho do documento e conta a um toque de distância. |
| 4 | **A pessoa decide; o sistema prepara.** | Cada cartão termina em escolhas; a ação sugerida já vem redigida. |
| 5 | **O dado entra pelo hábito que já existe.** | Encaminhar e-mail, enviar PDF, fotografar. Formulário é exceção. |
| 6 | **Perguntar é a navegação.** | Qualquer registro se acha perguntando; o menu é o que sobra. |
| 7 | **Uma interrupção custa caro.** | Há um limite semanal por pessoa, e cada aviso precisa justificar o gasto. |
| 8 | **Diz o que não sabe.** | "Não recebi o extrato de setembro" aparece antes de qualquer conclusão sobre setembro. |
| 9 | **O que serviu a uma decisão fica guardado.** | A análise aberta na conversa pode sumir da tela, mas a versão que embasou a decisão vai para a trilha. |
| 10 | **O mesmo fato, na medida de quem lê.** | Síndico, administradora e condômino recebem versões diferentes do mesmo registro, em momentos diferentes. |

---

## 2. Superfícies

| Superfície | Para quê | Quem | Frequência | O que **não** deve existir nela | Estado no produto |
|------------|----------|------|-----------|--------------------------------|-------------------|
| **Briefing ("Hoje")** | O que decidir hoje, em ordem | Síndico | Diária, 2 minutos | Gráficos, indicadores de vaidade, lista completa de achados, mais de 5 itens | *Existe* (D82): um por pessoa, condomínio e dia, só dentro do app |
| **Conversa** | Perguntar, pedir análise, pedir que prepare uma ação | Síndico, conselho | Algumas vezes por semana | Resposta sem citação; número que o código não conferiu; execução direta de ação | *Existe* (chat com 9 ferramentas de leitura). Só texto |
| **Cartão de decisão** | Aprovar, recusar, delegar, pedir evidência | Síndico | Quando houver | Mais de uma decisão por cartão; texto longo; aprovação por silêncio | *Existe* (cartão de achado, barra de decisão, pedido de ação D83) |
| **Tela de evidência** | Ver o documento e a conta | Síndico, conselho, administradora | Sob demanda | Edição do documento original | *Existe*; é o que a referência 02 mostra |
| **Análise sob demanda** | Comparativo, série, tabela, quando a conversa pede | Síndico, conselho | Ocasional | Painel permanente; desenho livre feito pelo modelo | *Não existe* |
| **Visão de carteira** | Exceções de todos os condomínios do síndico profissional | Síndico profissional | Diária | Uma linha por condomínio sem nada a decidir; indicadores médios | *Parcial*: existe para a administradora (Carteira). **Para o síndico profissional é o que falta, e ele é o comprador (D88)** |
| **WhatsApp** | Receber o resumo, encaminhar documento | Síndico | Diária | Aprovação de valor; conversa em grupo; dado de morador | *Não existe*. Especificação: só canal oficial, prioridade P1, depois do core estável |
| **Página do condômino** | Ver a prestação de contas explicada | Condômino | Mensal | Achado em aberto; nome de pessoa; chat aberto | *Não existe*. Proponho começar pelo relatório mensal com link, sem portal |
| **Modo assembleia** | Preparar a prestação de contas anual | Síndico, conselho | 1 ou 2 vezes por ano | Votação, quórum, ata | *Parcial*: relatório em PDF e planilha. **Eu não faria o resto agora** |

Três leituras:

1. **O que falta para o comprador escolhido é a carteira do síndico profissional.** As outras superfícies centrais já existem em alguma forma.
2. **Página do condômino e modo assembleia saem do escopo próximo.** Coerente com a Fase 1 (assembleia e comunicação com nota baixa).
3. **O aplicativo do síndico tem hoje 11 seções** (resumo, achados, agenda, ajustes, aprovações, assuntos, contratos, enviar, histórico, oportunidades, pergunte). Para uma tese "sem menus", é muito. A seção 8 propõe a redução.

---

## 3. Anatomia do cartão

Ordem fixa: **valor → o que diverge → evidência → conta → certeza → ação sugerida → prazo → decisão → trilha.**

```
┌──────────────────────────────────────────────────────────────┐
│ ▲ DIVERGÊNCIA · Contrato            Jardim das Acácias       │
│                                                              │
│ R$ 3.744 em 12 meses                                         │
│ Reajuste dos elevadores acima do índice do contrato          │
│                                                              │
│ Evidência                                                    │
│  • Contrato, cláusula 7.2: "reajuste anual pelo IPCA"   [ver]│
│  • IPCA acumulado em 12 meses: 4,60% (Banco Central)    [ver]│
│  • NF 1842, out/2026: R$ 6.588,00                       [ver]│
│                                                              │
│ Conta    R$ 6.000,00 × 1,046 = R$ 6.276,00 (devido)          │
│          R$ 6.588,00 − R$ 6.276,00 = R$ 312,00 por mês       │
│                                                              │
│ Certeza  Alta: cláusula, índice e nota lidos sem dúvida      │
│ Sugestão Pedir correção ao fornecedor (mensagem pronta)      │
│ Prazo    Antes do pagamento de novembro, em 12 dias          │
│                                                              │
│ [ Pedir correção ]  [ Aceitar como está ]  [ Mais evidência ]│
│ [ Delegar ]                                                  │
│                                                              │
│ Trilha: detectado em 08/11 · você viu em 09/11               │
└──────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────┐
│ ◆ INDÍCIO · Pagamento                Mirante do Vale         │
│                                                              │
│ R$ 2.180,00                                                  │
│ Dois pagamentos iguais ao mesmo fornecedor em 6 dias         │
│                                                              │
│ Evidência                                                    │
│  • Extrato, 03/10: Pix R$ 2.180,00 para Hidro Serviços  [ver]│
│  • Extrato, 09/10: Pix R$ 2.180,00 para Hidro Serviços  [ver]│
│  • Só uma nota no mês: NF 0457, R$ 2.180,00             [ver]│
│                                                              │
│ Conta    2 pagamentos − 1 nota = 1 pagamento sem nota        │
│                                                              │
│ Certeza  Média: pode haver uma segunda nota que não recebi   │
│ Sugestão Perguntar à administradora se existe outra nota     │
│ Prazo    Sem prazo. Valor já pago.                           │
│                                                              │
│ [ Perguntar à administradora ]  [ Foi serviço em dobro ]     │
│ [ Enviar a nota que falta ]     [ Delegar ]                  │
│                                                              │
│ Trilha: detectado em 10/10                                   │
└──────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────┐
│ ● PRAZO · Contrato                   Jardim das Acácias      │
│                                                              │
│ R$ 148.800 por ano em jogo                                   │
│ Portaria: renovação automática em 47 dias                    │
│                                                              │
│ Evidência                                                    │
│  • Contrato, cláusula 12: renova por 12 meses se não         │
│    houver aviso com 30 dias de antecedência             [ver]│
│  • Valor mensal atual: R$ 12.400,00                     [ver]│
│                                                              │
│ Conta    Aviso até 28/11 (30 dias antes de 28/12)            │
│          R$ 12.400,00 × 12 = R$ 148.800,00                   │
│                                                              │
│ Certeza  Alta na data. Não tenho preço de comparação.        │
│ Sugestão Decidir até 21/11 se renova ou pede propostas       │
│ Prazo    17 dias para avisar o fornecedor                    │
│                                                              │
│ [ Pedir propostas ]  [ Deixar renovar ]  [ Lembrar em 7 dias]│
│ [ Delegar ]                                                  │
│                                                              │
│ Trilha: previsto na agenda desde 02/09                       │
└──────────────────────────────────────────────────────────────┘
```

Regras: o rótulo diz o grau ("divergência", "indício", "prazo") com ícone e texto; a linha "Certeza" sempre diz o que falta; nenhum botão executa nada fora do sistema. "Pedir correção" abre a mensagem pronta e registra que a pessoa a enviou (D83).

---

## 4. Orçamento de atenção

Dois tipos de contato: o **briefing**, que a pessoa abre quando quer, e a **interrupção**, que chega sem ser pedida. O orçamento vale para a interrupção.

| Regra | Padrão proposto [HIPÓTESE] |
|-------|----------------------------|
| Limite | **3 interrupções por semana por pessoa**, somando todos os condomínios dela. Para o síndico profissional com 8 condomínios o limite não se multiplica |
| Interrompe | Valor em risco acima de R$ 1.000 **e** prazo de até 7 dias; ou prazo legal ou contratual em até 15 dias; ou pedido da própria pessoa ("me avise quando…") |
| Agrupa | Tudo que tem valor mas não tem prazo curto vai para o briefing do dia seguinte |
| Adia | Itens abaixo de R$ 1.000 sem prazo entram no resumo semanal |
| Silencia | Itens abaixo de R$ 100; repetição de item já visto; item que depende de documento ainda não recebido (vira um pedido de documento, uma vez) |
| Estourou o limite | O excedente entra no briefing, ordenado por valor. Só prazo legal fura o limite |
| Fechamento do mês | Uma mensagem, mesmo sem divergência: "tudo conferido" ou "faltou conferir X" |

**Como a pessoa calibra:**

- Em cada cartão: "menos avisos como este" e "quero saber sempre".
- Em Ajustes: os três valores (R$ 1.000, R$ 100, 3 por semana) e os horários.
- Adiar com data ("lembrar em 7 dias").
- O sistema mostra o próprio gasto: "esta semana interrompi você 2 vezes; 1 virou decisão". Aviso que nunca vira decisão é candidato a silêncio.

Estado no produto: *parcial*. O briefing diário existe e é só dentro do app (D82); não há interrupção por canal externo, logo não há o que limitar ainda. O orçamento passa a importar no dia em que houver notificação ou WhatsApp.

---

## 5. Níveis de autonomia

O prompt usa L0 a L4; a Especificação Mestra usa L1 a L5 (§9.1). Equivalência: L0 informa = L1 observar; L1 recomenda = L2 preparar; L2 executa com aprovação = L4 execução condicional; L3 executa e reporta = L3 rotina leve; L4 autônomo na alçada não tem equivalente e é vedado hoje.

| Tipo de ação | Exemplos | Padrão proposto | Teto | Estado |
|--------------|----------|:-:|:-:|--------|
| Ler, conferir, calcular, classificar | Extração, regras, cruzamentos | L3 (faz e mostra) | L4 | *Existe* |
| Avisar a pessoa dentro do app | Briefing, agenda | L3 | L4 | *Existe* |
| Pedir documento que falta | "Falta a nota de setembro" | L1 (recomenda; a pessoa pede) | L3, depois de validado | *Não existe* como envio |
| Redigir mensagem a fornecedor ou administradora | Pedido de correção, pedido de proposta | L1: redige; a pessoa envia e registra | L2 | *Existe* (D83: o despacho não envia) |
| Enviar mensagem em nome do condomínio | O mesmo, enviado pelo sistema | **Desligado** | L2 com aprovação, por tipo, no futuro | *Colide com D83* |
| Pedir cotações | Solicitar propostas | L1 | L2 | *Não existe* |
| Negociar | Contraproposta | L1: prepara argumentos e números | L1 | *Não existe* |
| Pagar, contratar, rescindir, multar, alterar dado bancário | — | **Nunca** | **Nunca** | Vedado sempre (D83) |
| Comunicar a condôminos | Aviso, resposta | L1 | L2 | *Não existe* |

**Alçadas** (valores de exemplo [HIPÓTESE]; os reais vêm da convenção e das alçadas versionadas do condomínio, D85):

| Valor da decisão | Quem decide |
|------------------|-------------|
| Até R$ 2.000 | Síndico |
| De R$ 2.000 a R$ 10.000 | Síndico, com ciência do conselho |
| Acima de R$ 10.000, ou contrato acima de 12 meses | Síndico e um conselheiro (aprovação dupla) |
| Fora do orçamento aprovado | Assembleia; o sistema só prepara o material |

Regras que não se relaxam: sem aprovação por silêncio; a aprovação vale para a versão que a pessoa viu e expira em 7 dias (já é D83); subir o nível de um tipo de ação é decisão registrada, com autor e motivo.

**Onde eu discordo do prompt:** "L4, autônomo dentro de alçada" não deve existir para nada que saia do sistema, em nenhum horizonte que eu consiga planejar. O produto vende independência e prova de diligência; um envio errado em nome do condomínio custa mais do que todas as horas que a autonomia pouparia.

---

## 6. Jornadas

Notação: **S** = síndico; **C** = CondoOS; `[cartão]` = cartão de decisão; `[análise]` = análise sob demanda.

### 6.1 Entrada em 15 minutos

> **C:** Para começar preciso de três coisas: a pasta de prestação de contas dos últimos meses, os contratos e o extrato. Pode encaminhar os e-mails da administradora para `acacias@…` ou enviar os arquivos aqui.
> **S:** *(encaminha 12 e-mails e envia 9 PDFs)*
> **C:** Recebi 12 pastas mensais, 9 contratos e nenhum extrato. Já consigo conferir contratos contra notas. Sem o extrato não confirmo o que foi pago. Quer enviar agora ou sigo sem ele?
> **S:** Sigo sem.
> **C:** Em até 48 horas mostro o que encontrei. Enquanto isso: identifiquei 14 fornecedores e 9 contratos. Dois contratos estão sem data de reajuste legível. `[cartão: confirmar duas datas]`

Honestidade: 15 minutos é o **tempo do síndico**. A leitura leva horas, e parte dos documentos cai na fila de revisão. A promessa correta é "15 minutos seus, 48 horas nossas". *Estado: existe (envio, e-mail, extração, cadastro de condomínio); o diálogo guiado não existe.*

### 6.2 Primeiro resultado em 48 horas

> **C:** Conferi 12 meses do Jardim das Acácias: 1.012 pagamentos, 9 contratos. Encontrei 3 pontos com valor, somando R$ 9.420, e 2 prazos nos próximos 60 dias. O maior é o reajuste dos elevadores. `[cartão 1 de 3]`
> **S:** E o resto?
> **C:** 1.007 pagamentos bateram com contrato e nota. Não consegui conferir 38, por falta de nota. Lista aqui.

*Estado: existe em partes (regras, achados, briefing). O resumo de entrada como momento único não existe. Depende de revisão humana proporcional ao risco (D74), o que consome as 48 horas.*

### 6.3 Despesa fora do padrão

> **C:** `[cartão: dois pagamentos iguais, R$ 2.180]`
> **S:** Foi serviço em dobro mesmo, teve vazamento duas vezes.
> **C:** Registrado como justificado por você em 11/11, com esse motivo. Se quiser anexar a segunda nota, o registro fica completo. Não aviso mais sobre este par.

*Estado: existe (achado, decisão com motivo, trilha).*

### 6.4 Contrato acima do mercado

> **S:** A portaria está cara?
> **C:** Não tenho preço de comparação confiável para portaria na sua região: hoje conheço poucos contratos parecidos. O que consigo afirmar: o valor subiu 31% em três anos, contra 15% do índice do contrato. `[análise: valor pago × valor pelo índice, 36 meses]`
> **S:** Quero propostas.
> **C:** Preparei o pedido com o escopo do contrato atual (4 postos, 24 horas). Você envia aos fornecedores que escolher; eu comparo as propostas quando chegarem e calculo a economia estimada. `[cartão: pedido de proposta pronto]`

Dois limites declarados: **não há referência de preço de mercado** (Fase 2: defesa ainda nula) e **o sistema não envia nem negocia**. A economia só é dita depois de calculada por código e revisada (D81). *Estado: parcial (oportunidade, estágios de economia); pedido de proposta e comparação não existem.*

### 6.5 Obrigação ou prazo vencendo

> **C:** `[cartão: renovação automática da portaria em 47 dias]`
> **S:** Lembrar em 7 dias.
> **C:** Combinado: volto em 18/11, dez dias antes do limite do aviso.

*Estado: existe (agenda, prazos de aviso lidos do contrato). Obrigações legais como AVCB e laudos dependem de cadastro que não existe.*

### 6.6 Inadimplência

Fora do alvo (Fase 1). O que cabe:

> **S:** Como está a inadimplência?
> **C:** Não recebo os dados de cobrança; eles ficam no sistema da administradora. Pelo extrato, a arrecadação de outubro foi 7% menor que a média de 12 meses. Se quiser, preparo a pergunta para a administradora.

Sem priorização de devedores e sem régua de cobrança: dado pessoal de condômino, terreno de garantidoras e escritórios. *Estado: não existe; proponho não fazer.*

### 6.7 Prestação de contas e assembleia

> **S:** Assembleia dia 15. O que eu levo?
> **C:** Montei o pacote do ano: despesas por categoria contra o orçamento, os 7 pontos apontados e o que foi decidido em cada um, R$ 5.300 de economia realizada e medida, e 2 contratos a decidir. `[relatório em PDF]` Faltam 3 notas de agosto para o ano fechar sem ressalva.

*Estado: existe para o mês (PDF, planilha, trilha); o pacote anual não existe. Edital, votação e ata ficam de fora.*

### 6.8 Condômino questiona uma despesa

> **S:** O morador do 142 perguntou por que a manutenção dos elevadores subiu.
> **C:** Resposta para você enviar: "O contrato prevê reajuste anual pela inflação. Em outubro o fornecedor aplicou um percentual acima do previsto; o síndico pediu a correção e o valor foi ajustado em novembro. O contrato está na prestação de contas do mês." Quer que eu inclua o valor?

O condômino não fala com o sistema; o síndico responde, com texto e prova prontos. *Estado: não existe como fluxo; o chat já consegue produzir a resposta.*

---

## 7. Análise sob demanda: o que "interface gerada" deve significar aqui

A tese fala em telas geradas. Eu restringiria: **o modelo escolhe e preenche um entre poucos componentes fixos; não desenha interface.**

| Componente | Quando aparece |
|------------|----------------|
| Tabela comparativa | Propostas lado a lado; contrato × fatura |
| Série no tempo | Evolução de um contrato ou categoria contra o índice |
| Composição | Despesa por categoria no período |
| Trecho de documento | Cláusula ou linha da nota em destaque |
| Linha do tempo | O que aconteceu com um contrato ou assunto |

Motivos: todo número precisa ser conferido por código (já é regra do chat); componente fixo é testável e acessível; e a linguagem visual das referências se aplica uma vez só. "Aparece e some" vale para a tela. Se a análise embasou uma decisão, a versão vista fica na trilha.

---

## 8. Achar as coisas sem menu

| Modo | Como | Estado |
|------|------|--------|
| Perguntar | "Quanto pagamos de elevador este ano?" | *Existe* |
| Buscar | Nome de fornecedor, número de nota, valor | *Parcial* (busca em documentos) |
| Comandar | "Prepare o pedido de correção", "lembre em 7 dias" | *Parcial* (lembrete e pedido de ação existem por tela) |
| Histórico | Tudo que foi decidido, por data | *Existe* |

**Navegação mínima proposta: quatro destinos.**

| Destino | Por que não dá para tirar |
|---------|---------------------------|
| **Hoje** | Ponto de entrada: briefing, decisões pendentes e o campo de pergunta. Absorve Achados, Aprovações, Oportunidades, Assuntos e Agenda como filtros do mesmo fluxo |
| **Registros** | Contratos, fornecedores e documentos. A pessoa precisa poder conferir o que o sistema "sabe" sem depender de pergunta: é condição de confiança, e é onde se corrige um dado errado |
| **Histórico** | A trilha é o produto para quem quer provar diligência. Precisa de endereço fixo |
| **Enviar** | A entrada de documento tem de estar sempre a um toque |

Mais: seletor de condomínio (para a carteira) e Ajustes, fora da barra principal.

Hoje são 11 seções no aplicativo do síndico; a Especificação Mestra recomenda 12 itens de menu (§7.2). A proposta reduz para 4 sem remover função: o que hoje é seção vira filtro dentro de "Hoje" ou resultado de pergunta. É uma reorganização, e precisa de decisão sua antes de qualquer mudança (R6).

---

## 9. Onde eu recuaria da tese do prompt

| Tese | Minha posição | Motivo |
|------|---------------|--------|
| Voz | **Adiar.** No máximo ditado no campo de pergunta | Conferência de contas é tarefa de ler número e documento. Não há sinal de demanda, e voz dobra o trabalho de teste |
| Interface gerada livremente | **Restringir** a componentes fixos (seção 7) | Número conferido por código, acessibilidade, custo |
| WhatsApp como canal nativo de aprovação | **Só resumo e captura de documento**; aprovação continua no app, com a prova à vista | Aprovar valor numa conversa sem evidência contraria "toda afirmação abre a prova"; a identidade de quem aprova é mais fraca; e D82 mantém o briefing dentro do app |
| Autonomia até L4 | **Não**, para ação externa (seção 5) | Risco maior que o ganho, para este comprador |
| Sem menus | **Quatro destinos** (seção 8) | Confiança exige poder inspecionar os registros sem perguntar |
| Portal do condômino e modo assembleia | **Adiar** | Fora da cunha (Fases 1 e 2) |

WhatsApp merece nota à parte: é o hábito dominante do setor, e eu não o ignoraria. Encaminhar documento pelo WhatsApp e receber o resumo do dia por lá são os dois usos de maior valor e menor risco. Custam integração com a plataforma oficial e mudança de D82. É a primeira coisa a testar depois que houver clientes usando o app.

---

## 10. Fechamento da Fase 4

### Resumo

- **A experiência central já existe em boa parte**: briefing do dia, conversa com citação, cartão de decisão, tela de evidência, trilha. O trabalho é de foco e redução, mais do que de construção.
- **O que falta para o comprador escolhido é a visão de carteira do síndico profissional**: exceções de todos os condomínios dele num lugar só, com um único orçamento de atenção.
- **O cartão tem ordem fixa** (valor, divergência, evidência, conta, certeza, sugestão, prazo, decisão, trilha) e nunca executa nada fora do sistema.
- **Orçamento de atenção: 3 interrupções por semana por pessoa**, com limites de R$ 1.000 e R$ 100 ajustáveis; o resto vai para o briefing ou para o resumo semanal.
- **Recuo em quatro pontos da tese**: voz, interface gerada livremente, aprovação por WhatsApp e autonomia L4. Navegação reduzida de 11 seções para 4 destinos.

### Três decisões que preciso de você

1. **Navegação (R6):** aceita como direção reduzir o aplicativo do síndico a quatro destinos (Hoje, Registros, Histórico, Enviar), com o restante virando filtro ou pergunta? É reorganização de telas existentes; só entra em roadmap se você aprovar.
2. **WhatsApp (R4):** aceita o recorte "resumo do dia e captura de documento, sem aprovação", a ser testado depois dos primeiros clientes, sabendo que isso exigirá rever D82? Ou prefere manter tudo dentro do app por ora?
3. **Recuos:** confirma voz adiada, interface gerada só por componentes fixos e nenhuma autonomia L4 para ação externa?

### Principais riscos

- **Redução de menu que esconde função.** Quem hoje acha "Contratos" numa aba pode se perder se tiver de perguntar. Precisa de teste com usuários antes de consolidar.
- **Orçamento de atenção calibrado no escuro.** Os três números são palpite; errar para mais gera abandono, errar para menos esconde valor.
- **A promessa de 48 horas depende de revisão humana.** Com poucos clientes funciona; com 40 condomínios vira gargalo de pessoas.
- **Sem WhatsApp, a entrada de documentos depende de o síndico mudar de hábito** (encaminhar e-mail, enviar arquivo). É o maior risco de adoção desta fase.
- **Carteira do síndico profissional ainda não inspecionada no código.** Sei que existe para a administradora; não verifiquei quanto se aproveita.

---

## 11. Divergências desta fase

| # | Divergência | Estado |
|---|-------------|--------|
| R4 | WhatsApp, voz e Open Finance no centro (prompt) × D82 e ordem do Plano | Proposta: WhatsApp só resumo e captura, depois dos primeiros clientes; voz adiada. Aguardando decisão 2 |
| R5 | "Sistema que age", L0–L4 (prompt) × D83 e L1–L5 da Especificação | Proposta: manter D83 integralmente; sem L4 externo. Aguardando decisão 3 |
| R6 | Sem menus (prompt) × 12 itens (Especificação §7.2) × 11 seções (app) | Proposta: 4 destinos. Aguardando decisão 1 |
| R14 | Carteira para o síndico profissional | Existe para a administradora; vira prioridade com D88. Detalhar na Fase 6 |
| R15 | Página do condômino e modo assembleia (prompt) | Proposta: adiar; relatório com link e pacote anual em PDF |

R1 (dor central) segue aberta. R11 foi decidida em D90.
