# Reconcepção do CondoOS — Fase 6: MVP, roadmap e validação

Data: 11/11/2026 · Estado: **aguardando validação do Marcio** (Fase 7 não iniciada).

Parte das respostas à Fase 5 (D92): mapa de módulos confirmado; próxima capacidade depois da carteira do síndico profissional é a **comparação de propostas**; cláusula de uso anônimo de preços desde os primeiros contratos; e **a dor central é o controle da despesa**, não a coordenação.

Marcação: **[FATO]** (do repositório ou de fonte citada nas fases anteriores), **[CÁLCULO]**, **[HIPÓTESE]**, **[PREMISSA]**. Li `docs/product-roadmap.md`, `docs/pilot-protocol.md` e `docs/backlog.md` para esta fase. Metas e limiares são propostas minhas; nenhum foi medido.

**O que mudou em relação às fases anteriores.** Duas coisas.

1. A Fase 5 recomendou validar mão de obra terceirizada antes de qualquer outra capacidade; você escolheu comparação de propostas. Sigo a sua escolha. A consequência: o retorno "forte" da Fase 2 (3,75×) continua dependendo de uma base de despesa que o produto ainda não confere. Para não perder a informação, o piloto coleta os contratos de mão de obra e mede o que seria conferível, sem construir nada.
2. Ao ler o backlog, encontrei o fato que organiza esta fase: **quase tudo o que foi planejado está entregue, e o gate G0 (piloto real, baseline, direitos de uso) continua aberto** [FATO]. O produto está à frente do mercado. O risco deixou de ser "falta construir" e passou a ser "continuar construindo em vez de ir a campo".

---

## 1. O MVP atual: manter, ajustar ou trocar

**Manter a conferência de despesas como cunha. Ajustar quem a opera e como ela é entregue. Parar de ampliar.**

| Aspecto | Hoje | Ajuste |
|---------|------|--------|
| Capacidade central | 12 regras, casamento com extrato e contrato, evidência, trilha | Manter |
| Quem opera a fila de exceções e valida | Analista e gerente da administradora | **Revisor CondoOS** (papel já existe, D79). A administradora deixa de ser operadora |
| Quem recebe | Síndica de um condomínio | **Síndico profissional com vários condomínios**: falta a visão de carteira |
| Forma de entrada | Cadastro do condomínio e envio de documentos | **Diagnóstico de entrada**: 12 meses anteriores, quando o síndico assume um condomínio |
| Entrega mensal | Achados e relatório | Manter, mais uma linha honesta sobre o que não pôde ser conferido |
| Além da cunha | Assuntos, oportunidades, briefing, pedidos de ação, kill switch | Manter como está; não ampliar |

**A cunha de menor dado e integração:** contratos, notas do mês e extrato, enviados pelo síndico. Sem API de ERP, sem acesso bancário, sem dado de morador. Já é o que o protocolo de piloto pede [FATO, `docs/pilot-protocol.md` §5].

**Crítica direta.** O "MVP" tem 44 tabelas, cinco fatias verticais entregues e zero uso real. Isso não é erro: a base de segurança e trilha é o que sustenta a marca. Mas daqui em diante cada semana de código sem cliente compra menos do que uma semana de campo. Proponho um **congelamento de funcionalidades**: nos próximos três meses, só entra código que destrave o piloto.

---

## 2. Escopo do MVP de piloto

| Entra (existe) | Entra (a construir, pequeno) | Feito à mão por trás, no início | Fica de fora |
|----------------|------------------------------|---------------------------------|--------------|
| Envio de documentos e e-mail | **Carteira do síndico profissional**: exceções de todos os condomínios dele numa ordem só | Separar a pasta mensal (um PDF grande) em documentos | WhatsApp, voz |
| Extração com fila de exceções | **Resumo de entrada**: o resultado dos 12 meses numa tela e num PDF | Revisão da fila de exceções e validação dos achados (você ou um revisor) | Página do condômino, assembleia |
| 12 regras, achados, evidência | Linha "não conferido" no relatório | **Comparação de propostas**: feita em planilha por você nos primeiros casos, para aprender o formato antes de programar | Cobrança, manutenção de ativos, obrigações legais |
| Contratos, prazos, agenda | Política pública de erro (texto e contagem visível) | Cadastro inicial do condomínio e dos contratos | Mão de obra (só coleta e medição) |
| Briefing, conversa, trilha | | Pedido de documento faltante (você pede ao síndico) | Referência de preços (só a cláusula e a coleta) |
| Oportunidade e economia medida | | Mensagens ao fornecedor (o síndico envia) | Redução da navegação e troca de cores: depois de uso real |
| Relatório em PDF e planilha | | | Qualquer envio externo pelo sistema |

A comparação de propostas feita à mão primeiro é deliberada: você ainda não viu dez propostas reais de portaria lado a lado. Programar antes disso é adivinhar o formato.

---

## 3. Roadmap

Relação com o que existe: `docs/product-roadmap.md` ordena os marcos M0 a M5 do Plano Diretor. Com D92, **M4 (Operate) e boa parte de M5 deixam de ser o caminho**; M0 (fechar o gate G0) vira a prioridade única. O roadmap abaixo substitui a sequência a partir de C7 e só passa a valer se você aprovar esta fase. Não alterei aquele arquivo além de um aviso no topo.

### 0 a 3 meses — provar que há o que achar

| | |
|---|---|
| **Pergunta** | Em pastas reais, o que o sistema encontra vale mais do que custa? |
| **Campo** | 24 entrevistas da primeira onda (Fase 1), com o teste de nome (Fase 3). 5 pastas reais de 12 meses, de 2 ou 3 síndicos profissionais, em modo sombra: nada chega ao síndico sem revisão |
| **Pré-condições (G0)** | Termo de piloto e base legal revisados por advogado, com a cláusula de uso anônimo de preços. Revisão dos termos do executável embutido (D54). Chave de API e as duas medições pendentes: acurácia da extração e avaliação da conversa. Ambiente de piloto separado, com backup testado |
| **Código** | Só o da coluna "a construir, pequeno" da seção 2, e correções que as pastas reais exigirem |
| **Marco** | Cinco diagnósticos de entrada entregues |
| **Critério de passagem** | Achados confirmados de 1,5% ou mais da despesa em pelo menos 3 das 5 pastas. Precisão de 70% ou mais (confirmados ÷ apontados). 60% ou mais dos documentos reais lidos sem revisão. Pelo menos 3 síndicos pedem para continuar depois do diagnóstico. Zero falha de isolamento |

### 3 a 6 meses — provar que pagam

| | |
|---|---|
| **Pergunta** | O síndico coloca o condomínio para pagar, e usa todo mês? |
| **Campo** | 5 a 10 condomínios em conferência mensal. Teste de preço com a tabela da Fase 2. Primeiras renegociações acompanhadas, com comparação de propostas feita à mão |
| **Código** | Comparação de propostas no produto, depois de 5 casos manuais. Redução da navegação para quatro destinos, com teste de uso. Troca dos tokens visuais (D90), com contraste conferido |
| **Marco** | Primeiro condomínio pagante; primeira economia contratada com documento |
| **Critério de passagem** | 5 ou mais condomínios pagantes, de pelo menos 2 síndicos. 60% ou mais dos itens do briefing viram decisão. Revisão humana de até 2 horas por condomínio por mês. Nenhum cancelamento por falta de valor. Um caso documentado, com números |

### 6 a 12 meses — provar que repete

| | |
|---|---|
| **Pergunta** | Dá para vender e entregar sem você em cada etapa? |
| **Campo** | Crescer por indicação e pela carteira dos síndicos atuais até 40 condomínios. Primeiro revisor em meio período. Caso publicado. Associações e eventos |
| **Código** | WhatsApp para resumo e captura de documento, como teste (exige rever D82). Referência de preços em três categorias, se houver 30 condomínios ou mais com a cláusula. Decisão sobre mão de obra com base no que foi coletado |
| **Marco** | 40 condomínios e cerca de R$ 20 mil de receita mensal (hipótese da Fase 2) |
| **Critério de passagem** | Margem bruta de 70% ou mais. Retorno confirmado mediano de 3× a assinatura. Custo de aquisição pago em até 6 meses. Um diagnóstico de entrada sai sem você tocar nele |

Divisão do seu tempo que eu sugeriria [HIPÓTESE]: 70% campo e 30% produto no primeiro trimestre. É o inverso do que o repositório mostra até aqui.

---

## 4. Métricas

**Métrica norte: retorno confirmado do condomínio.**

> (divergências corrigidas em R$ + economia realizada e medida em R$) ÷ valor pago ao CondoOS, por condomínio, em 12 meses.

É o número que o síndico leva à assembleia e o que responde se o cliente renova. Os dois termos do numerador são sempre mostrados separados, cada um com o nome próprio; estimativa e potencial não entram. A regra do projeto de nunca somar estágios de economia (D81) continua valendo: aqui se soma economia **realizada** com divergência **corrigida**, que são fatos de natureza diferente, e por isso a fórmula precisa da sua aprovação antes de aparecer em qualquer tela.

Diverge da Especificação Mestra, que tem duas métricas norte: demandas resolvidas sem o síndico (operação) e economia líquida realizada (§17.1). Com D92, só a segunda permanece, ampliada com as divergências corrigidas.

| Métrica de apoio | Fórmula | Meta proposta | Existe no produto? |
|------------------|---------|:-:|:-:|
| Taxa de achados | achados confirmados em R$ ÷ despesa total | 1,5% ou mais | Parcial (valor em risco dos confirmados) |
| Precisão | confirmados ÷ decididos | 70% ou mais | Sim |
| Tempo até o primeiro resultado | da entrega dos documentos ao resumo de entrada | até 48 horas úteis | Não |
| Itens que viram decisão | decididos ÷ mostrados no briefing | 60% ou mais | Parcial |
| Leitura sem revisão | documentos sem correção ÷ processados | 60% no piloto, 75% depois | Sim (40% sem chave) |
| Revisão por condomínio | horas de revisor por mês | até 2 h | Não |
| Cobertura | pagamentos conferidos ÷ pagamentos do mês | 90% ou mais | Não |
| Custo de IA por condomínio | soma das chamadas | até R$ 30 por mês | Sim |
| Uso | dias com acesso do síndico por semana | 2 ou mais | Parcial |
| Retenção | condomínios ativos após 6 meses | 90% ou mais | Não |
| Indicação | "indicaria a outro síndico", de 0 a 10 | 8 ou mais em mediana | Não |
| Segurança | acessos entre condomínios; ações fora da política | zero | Sim |

"Aprovações por semana", sugerida no prompt, eu não usaria: mede atividade, e a tese diz que silêncio é sucesso.

---

## 5. Plano de piloto

O protocolo atual prevê até 3 condomínios de portes diferentes (pequeno, médio, grande) [FATO]. Com o comprador definido em D88, proponho trocar a amostra:

| | Protocolo atual | Proposta |
|---|---|---|
| Quantos | Até 3 | **5 a 10 condomínios, de 2 a 4 síndicos profissionais** |
| Perfil | Pequeno, médio e grande | Residencial, São Paulo capital, despesa acima de R$ 1 milhão por ano, com administradora que entrega pasta digital |
| Momento | Qualquer | Preferência por condomínio assumido nos últimos 6 meses, ou com contrato grande a renovar |
| Fases | V0 a V5 | As mesmas; V2 (modo sombra) passa a cobrir 12 meses |

**Oferta ao síndico.** Diagnóstico de entrada gratuito de um condomínio da carteira, seguido de três meses de conferência mensal sem custo. Em troca: os documentos, uma hora por mês de conversa, e o direito de publicar o caso sem identificar o condomínio. Ao fim dos três meses, proposta com a tabela de preço.

**Termo de piloto** (redação por advogado; itens que eu levaria):

1. Quem assina: o condomínio, pelo síndico, com ciência do conselho.
2. Autorização de uso dos documentos só para a conferência; CondoOS como operador de dados; prazo de retenção e devolução ou exclusão ao fim.
3. O que não é pedido: dados de moradores, acesso bancário, grupos de mensagens.
4. O sistema não paga, não contrata e não envia nada; os apontamentos são indícios para decisão do síndico.
5. Cláusula de uso anônimo e agregado de preços de contrato (D92).
6. Gratuidade por prazo definido; sem exclusividade; saída a qualquer momento.
7. Independência: o CondoOS não recebe de fornecedor nem de administradora.

**Coleta de evidência**, por condomínio: despesa total do período; achados apontados, confirmados e descartados, com valor e motivo; horas de revisão; documentos faltantes; tempo de cada etapa; o que o síndico fez com cada achado; contratos de mão de obra e o que neles seria conferível; propostas recebidas em renegociações. Resultado em `docs/pilot/`, sem dados pessoais.

**Caso.** Uma página por condomínio: situação inicial, o que foi encontrado em reais, o que foi corrigido, o que foi economizado e medido, quanto tempo levou, uma frase do síndico. Só com números confirmados.

**Limite a respeitar:** nenhum dado real entra no sistema antes do termo assinado (regra do projeto).

---

## 6. Critérios de parada e de mudança de rumo

| # | Sinal | Limiar | Consequência |
|---|-------|--------|--------------|
| K1 | Taxa de achados nas 5 pastas | Abaixo de 0,5% da despesa em 4 ou mais | **Parar a cunha.** A conferência de despesas não paga o produto. Avaliar K-alt abaixo |
| K2 | Taxa de achados intermediária | Entre 0,5% e 1,5% | Iterar: medir o que mão de obra e consumo acrescentariam antes de vender |
| K3 | Acesso aos documentos | De 30 síndicos abordados, menos de 3 entregam uma pasta | Trocar o comprador: conselho fiscal ou síndico morador de condomínio grande |
| K4 | Conversão | De 10 diagnósticos com valor encontrado, menos de 3 viram pagante em 60 dias | Refazer oferta e preço uma vez; se repetir, mudar para diagnóstico avulso pago |
| K5 | Leitura de documentos reais | Abaixo de 40% sem revisão depois de um ciclo de ajuste | Pausar vendas: a margem não fecha |
| K6 | Carga de revisão | Acima de 3 horas por condomínio por mês no mês 9 | O modelo não escala; rever preço ou escopo |
| K7 | Tração em 12 meses | Menos de 15 condomínios pagantes ou menos de R$ 7 mil de receita mensal | Encerrar ou reposicionar |
| K8 | Falso positivo | Precisão abaixo de 50% por dois meses seguidos | Parar de mostrar achados novos até corrigir as regras |
| K9 | Segurança | Qualquer acesso entre condomínios, ou texto ao cliente com "fraude" ou "desvio" | Parar tudo até corrigir (já é regra do protocolo) |

**Alternativas se a cunha falhar (K-alt), em ordem:**

1. **Diagnóstico avulso pago** na troca de síndico ou antes da assembleia: mesmo motor, sem assinatura.
2. **Ferramenta do conselho fiscal**: mesmo motor, outro comprador, sem o conflito de o comprador ser o auditado.
3. **Marca branca para administradoras pequenas** que queiram se diferenciar dos grandes ERPs. Contraria D73 e só entra com decisão nova.

Os limiares são propostas. O que importa é fixá-los **antes** de ver os dados, para que a decisão não seja negociada depois.

---

## 7. O que só você pode destravar

1. **Chave de API** em ambiente de piloto, para rodar as duas medições pendentes.
2. **Advogado**: termo de piloto, LGPD, cláusula de preços, termos do executável embutido (D54) e o uso da palavra "auditoria". Não tenho estimativa de custo.
3. **Os primeiros síndicos profissionais**: a lista de quem você alcança em 60 dias (pergunta 1 da Fase 1, ainda sem resposta).
4. **Um ambiente de piloto** separado do de desenvolvimento.

---

## 8. Fechamento da Fase 6

### Resumo

- **Manter a conferência de despesas como cunha, operada por um revisor CondoOS e entregue ao síndico profissional**; a entrada é o diagnóstico de 12 meses de um condomínio recém-assumido.
- **Congelar funcionalidades.** O backlog está quase todo entregue e o gate de piloto real continua aberto. Em três meses só entram a carteira do síndico, o resumo de entrada, a linha "não conferido" e a política de erro.
- **Três perguntas, uma por trimestre**: há o que achar (5 pastas reais), pagam (5 a 10 condomínios), repete (40 condomínios e cerca de R$ 20 mil por mês).
- **Métrica norte: retorno confirmado do condomínio**, divergências corrigidas mais economia realizada sobre o valor pago, com os dois termos sempre separados.
- **Nove critérios de parada com limiar fixado antes dos dados**; o primeiro é taxa de achados abaixo de 0,5% da despesa.

### Três decisões que preciso de você

1. **Congelamento:** aceita que, pelos próximos três meses, só entre código que destrave o piloto, e que o roadmap acima substitua a sequência atual a partir do ciclo C7, retirando a operação (M4) do caminho?
2. **Piloto:** aceita trocar a amostra do protocolo para 5 a 10 condomínios de 2 a 4 síndicos profissionais, com diagnóstico e três meses gratuitos?
3. **Critérios de parada e métrica norte:** aceita os limiares da seção 6 e a fórmula da seção 4, ou quer ajustar algum antes de os dados chegarem?

### Principais riscos

- **Não conseguir as 5 pastas.** Tudo depende de síndicos entregarem documentos a um desconhecido. Sem a sua rede, o primeiro trimestre não acontece.
- **Pré-condições jurídicas atrasarem o campo.** Termo, LGPD e D54 podem levar semanas.
- **Diagnóstico gratuito virar hábito.** Dez diagnósticos sem conversão consomem dezenas de horas de revisão.
- **Fundador como gargalo.** Venda, revisão, cadastro e produto na mesma pessoa; o critério "sai sem você tocar" existe por isso.
- **A escolha por comparação de propostas** antes de mão de obra deixa a maior linha de despesa sem conferência por mais tempo. Se a taxa de achados vier fraca (K2), é o primeiro lugar a olhar.
- **Congelar funcionalidades é difícil de sustentar** quando construir é mais confortável do que vender.

---

## 9. Divergências desta fase

| # | Divergência | Estado |
|---|-------------|--------|
| R1 | Dor central | **Resolvida em D92: controle da despesa** |
| R3 | Tamanho do piloto: 3 condomínios × 5 a 10 | Aguardando decisão 2 |
| R10 | Métrica norte: duas (Especificação §17.1) × uma | Aguardando decisão 3 |
| R17 | Operate e Procurement da Especificação | Com D92, saem do caminho; formalização aguardando decisão 1 |
| R19 | `docs/product-roadmap.md`, ciclos C7 em diante | Substituídos pelo roadmap da seção 3 se a decisão 1 for sim; arquivo só recebeu um aviso |
| R20 | Mão de obra antes de propostas (recomendação da Fase 5) × propostas primeiro (D92) | Decidido pelo Marcio; mitigação: coletar e medir no piloto |
