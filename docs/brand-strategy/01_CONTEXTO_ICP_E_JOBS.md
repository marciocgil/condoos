# 01 — Contexto, ICP, personas e Jobs-to-be-Done

Pesquisa de 08/11/2026. Legenda: **F** fato com fonte · **I** inferência · **H** hipótese a validar · **NV** não verificado. Fontes completas em `10_REGISTRO_DE_FONTES.md`. **Nenhuma entrevista foi realizada nesta etapa**: tudo o que se refere a comportamento individual é inferência sobre fontes públicas ou hipótese.

## 1. Brief de marca (Fase 0)

### 1.1 O que o produto é hoje (estado real do código, 07/11/2026)

Fonte: `CLAUDE.md`, `docs/roadmap-status.md`, `docs/02-gap-matrix.md`.

| Situação | Capacidades | Pode ser comunicado como presente? |
|---|---|---|
| **Existe e está testado** (MVP auditor, Marcos 1–6, e fatias VS-01, 03, 04, 05) | Leitura de documentos (NF, boleto, contrato, extrato OFX/CSV/CNAB); conferência de cada despesa contra contrato reajustado, CNPJ, extrato e histórico (12 regras); achados priorizados por valor em risco, com evidência; decisão humana registrada; chat com citação sobre contratos, convenção e atas; relatório PDF/XLSX ao conselho; Assuntos com tarefas e evidência; Oportunidades de economia com revisão interna e estágios estimada → contratada → realizada; briefing "Hoje"; pedido de ação com aprovação e kill switch (nada é enviado) | Sim, **com a ressalva de que não houve piloto real** (gate G0 aberto). Linguagem: "o produto faz", não "condomínios economizaram" |
| **Em desenvolvimento / parcial** | Proveniência completa, avaliação ao vivo do chat e acurácia com LLM (falta chave de API), onboarding repetível | Não como promessa; só como "em construção" em conversas de piloto |
| **Aspiração (roadmap M4–M5)** | Operate (OS, fornecedores, WhatsApp, automações), Procurement (cotações, compras), portal de zelador/fornecedor/morador | **Não.** Pode aparecer como visão em pitch para investidor, nunca em site ou proposta |

**Diferenciais comprováveis hoje (F, pelo código e testes):** conferência determinística com evidência; linguagem de indício, nunca acusação; pessoa sempre decide; o sistema não move dinheiro; isolamento por condomínio (RLS); economia medida por estágio, com documento.

**Diferenciais ainda não provados (H):** que a conferência encontra valor relevante em condomínios reais; que o síndico economiza tempo; que a economia realizada paga a assinatura.

### 1.2 Tensões de posicionamento

| Tensão | Lado A | Lado B | Leitura (I) |
|---|---|---|---|
| Software × serviço | Assinatura SaaS | Revisão humana interna obrigatória no Optimize (D74, D77) | O produto é "software com revisão humana". A marca deve permitir os dois sem prometer consultoria |
| Síndico × conselho | Síndico usa e decide (67% decidem sozinhos as finanças, Datafolha 2025) | Conselho fiscaliza (CC art. 1.356) e pode barrar | Mensagem dupla: tranquilidade para o síndico, prova para o conselho |
| Economia × operação | Optimize é a porta de entrada | Advisor/Operate é a retenção | Liderar com o que existe e prova valor (conferência e economia), deixar operação como expansão |
| IA autônoma × supervisão | Mercado fala em "agentes que fazem" (Vantaca, Sindia) | Nosso produto nega por padrão e não move dinheiro | A supervisão é diferencial, não limitação |
| Independência × integração | Verificar a administradora | Depender dos dados que ela envia | Posicionar como "segunda conferência a favor do condomínio", nunca como fiscal contra a administradora |

### 1.3 Mapa de papéis na compra

| Papel | Quem | O que precisa ouvir |
|---|---|---|
| Paga | O condomínio (caixa comum), aprovado pelo síndico dentro da alçada ou em assembleia (F: D73) | "O custo se justifica pelo que foi conferido e economizado" |
| Usa | Síndico (morador ou profissional); conselheiros em leitura | "Menos trabalho, menos risco pessoal" |
| Influencia | Conselho fiscal, condôminos ativos, síndico profissional que recomenda | "Mais transparência com prova" |
| Pode barrar | Assembleia (despesa nova), conselho, administradora que se sente fiscalizada | "Não substitui ninguém; não é acusação" |
| Precisa cooperar com dados | Administradora (pasta, balancete, NF, extrato) | "Menos pedidos repetidos e menos discussão sobre status" |

### 1.4 Hipóteses prioritárias de valor

- **H1.** A dor que justifica pagamento é **responsabilidade pessoal pelas contas** (CC arts. 1.348–1.349: prestar contas, risco de destituição), mais do que falta de tempo.
- **H2.** "Prova" (achado com evidência, economia medida) vale mais do que "IA" para síndico e conselho.
- **H3.** O síndico profissional é o canal mais eficiente (8 condomínios em média, F Datafolha 2025) e o síndico morador de condomínio de 60–200 unidades é o comprador mais fácil de fechar.
- **H4.** A administradora coopera se a ferramenta reduzir pedidos e não for vendida como fiscal.
- **H5.** Preço de R$ 299–899 só se sustenta com diagnóstico gratuito ou pago do primeiro mês mostrando valor em risco.

### 1.5 Questões abertas

1. Quem assina a compra na prática: síndico dentro da alçada ou assembleia? (lacuna de pesquisa primária)
2. A palavra "assessor" é ouvida como serviço humano caro ou como apoio? Há risco regulatório (ver §4.3)?
3. O síndico aceita achados gerados por IA como base para cobrar a administradora ou um fornecedor?
4. O nome "CondoOS" pode ser defendido? (ver `06_TRIAGEM_MARCAS_DOMINIOS.md`)

## 2. Mercado (Fase 1)

| Dado | Valor | Fonte e qualidade |
|---|---|---|
| Endereços dentro de condomínios no Brasil | 13,3 milhões (12,4% dos endereços) | IBGE CNEFE/Censo 2022, via SíndicoNet 18/06/2024 · alta (dado), média (via) |
| População em apartamento | 12,5% em 2022 (8,5% em 2010); Sudeste 16,7% | IBGE Agência de Notícias, fev/2024 · alta (confirmar na fonte) |
| Condomínios no Brasil | 327.248 "ativos e com gestão estruturada" (uCondo, 2026) **ou** "mais de 520 mil" (SíndicoNet/Folha 2024, sem fonte nomeada) | média / baixa. **Não comparáveis**; usar faixa e citar critério |
| Condomínios na cidade de SP | ~31 mil (92% residenciais); média de 75 apartamentos | Lello, Mapa dos Condomínios 2025 · média |
| Orçamento anual médio em SP | R$ 779.150; cota média R$ 983/mês (2024) | Lello 2025 · média |
| Composição da despesa em SP | Folha 48%; água e energia 21%; **contratos de conservação e manutenção 17%**; seguros e administrativas 10% | Lello 2025 · média |
| Boleto médio nacional | R$ 516 (1º sem. 2025), +24,9% desde 2022 | InfoMoney/Censo uCondo, 29/12/2025 · média |
| Síndicos profissionais | 46% dos síndicos se dizem profissionais; 8 condomínios em média; 32 h/semana (morador: 19 h, 1–2 condomínios) | Datafolha para Superlógica, 350 entrevistas, 04/12/2025 · média |
| Síndico decide finanças sozinho | 67% | idem |
| Uso de plataforma de gestão | 74% dos síndicos | idem |
| Número de administradoras | — | **NV**: não há contagem pública |

**Ordem de grandeza útil (I, cálculo):** um condomínio de SP com orçamento médio de R$ 779 mil/ano gasta ~R$ 132 mil/ano (17%) em contratos de conservação e manutenção. Uma assinatura de R$ 499/mês (R$ 5.988/ano) equivale a ~0,8% do orçamento total ou ~4,5% da linha de contratos. **É conta de ordem de grandeza, não promessa de economia.**

**Maturidade digital (I):** 74% já usam plataforma; a IA cresce rápido entre administradoras e devagar entre síndicos moradores (dado de 71% de baixo uso é **NV**). O síndico já tem "um sistema"; não quer outro sistema, quer um resultado.

## 3. Segmentos, dores e JTBD

| Segmento | Dores funcionais | Dores emocionais/sociais | Alternativa atual | Gatilho de compra (H) | Objeção principal (H) | Job-to-be-Done |
|---|---|---|---|---|---|---|
| **Síndico morador** (ICP principal, 60–200 un.) | Conferir a pasta do mês sem saber contabilidade; cobrar administradora; achar contrato | Medo de errar e responder pessoalmente; conflito com vizinhos; trabalho não remunerado | Confiar na administradora; planilha; conselheiro "que entende" | Assembleia de contas próxima; conta que subiu; denúncia de condômino; posse recente | "Mais um sistema"; "quanto custa e quem aprova" | "Quando a pasta do mês chega, quero saber o que está fora do normal e o que fazer, para assinar as contas tranquilo." |
| **Síndico profissional** (canal) | 8 prédios, ~4 h/prédio/semana; padronizar conferência; mostrar valor ao cliente | Reputação; renovação de mandato (89% não passam de 2 anos, NV) | Equipe própria; ERP da administradora | Captar/renovar condomínio; disputa com outro profissional | Custo por condomínio; mais uma tela | "Quero mostrar ao conselho, todo mês, que conferi tudo e onde economizei, sem gastar mais horas." |
| **Conselheiro / conselho fiscal** | Dar parecer sobre contas (CC 1.356) sem acesso fácil a documentos | Não querer ser cúmplice; desconfiança | Pedir pasta; contador amigo; auditoria pontual | Suspeita; troca de gestão | "Quem garante que a IA está certa?" | "Quero assinar o parecer com base em evidência, não em confiança." |
| **Condomínio-clube / grande** (>200 un.) | Volume de contratos; obras | Pressão política de muitos condôminos | Gerente predial; auditoria contratada | Obra grande; sinistro | Já tem estrutura | Fora do ICP inicial; ver depois |
| **Administradora regional** | Pedidos repetidos do síndico; disputa sobre status | Medo de ser fiscalizada; perder cliente | ERP (Superlógica, Group…) | Diferenciar-se; reter síndico exigente | Conflito de interesse; "vai me expor" | "Quero que o síndico confie no meu trabalho sem eu responder a mesma pergunta dez vezes." (canal futuro; D73 diz que é colaboradora opcional) |
| **Administradora grande** | — | — | Produto próprio (Lello, Hubert) | — | Já tem tudo | Não é público; pode ser concorrente de discurso |

**Indivíduo × condomínio (I):** ao síndico, a proposta é **tranquilidade e menos trabalho** ("assine as contas tranquilo"). Ao condomínio (conselho, assembleia), é **prova e economia** ("cada despesa conferida, economia medida"). A marca precisa sustentar as duas sem prometer economia.

## 4. Voz do cliente e linguagem

### 4.1 Expressões reais encontradas (fontes públicas)

| Expressão | Onde |
|---|---|
| "prestação de contas", "falta de transparência na prestação de contas" | Títulos de reclamações no Reclame Aqui contra administradoras, 2024–2026 |
| "pasta de despesas" | Reclame Aqui, 2025 |
| "não disponibiliza notas fiscais" | Reclame Aqui |
| "falta de controle e transparência das contas" | Reclame Aqui |
| "falta de retorno", "não respondem e-mails" | Reclame Aqui |
| "boa gestão", "transparência, proatividade e planejamento" | Raio-X SíndicoNet 2026 (2.120 participantes, autosselecionados) |
| "prestar contas… quando exigidas", "não administrar convenientemente" | Código Civil arts. 1.348–1.349 (vocabulário de assembleia) |

**Limite:** quem reclama no Reclame Aqui é sobretudo o condômino. Isso mostra a pressão que o síndico sofre, não a fala do síndico. Termos como "pasta de balancete", "sobrecarga" e "responsabilidade civil do síndico" são comuns em conteúdo do setor, mas **não foram confirmados como falas de clientes**.

### 4.2 Linguagem interna que não deve ir para o cliente

"Achado", "regra R04", "Optimize", "Operate", "Advisor", "Launch", "Data Readiness", "kill switch", "outbox", "tenant". Substituir por: "ponto de atenção", "conferência", "economia", "acompanhamento", "implantação".

### 4.3 Palavras sensíveis

- **"Assessoria/assessor":** no setor designa serviço humano (jurídico, contábil). Consultoria e assessoria **jurídicas** são privativas da advocacia (Lei 8.906/94, art. 1º, F) e a OAB-GO publicou em 2026 cartilha sobre exercício ilegal da advocacia em relações condominiais (conteúdo lido só por resumo, NV). **Risco (I):** "assessor" sozinho pode sugerir serviço humano/jurídico. Se usado, qualificar: "assessor de gestão", nunca "assessoria jurídica/contábil".
- **"Auditoria":** carrega custo, prazo e suspeita; também é atividade regulada quando contábil formal (NV quanto à extensão). Preferir "conferência" no produto; "auditoria contínua" só como descritor de categoria com cuidado.
- **"IA":** condôminos valorizam IA **com** atendimento humano (42,2%, baixa qualidade). Usar IA como meio, não como promessa.

## 5. Mapa de objeções

| Objeção | Quem levanta | Resposta (detalhes em `08_BRANDBOOK_E_MENSAGENS_V01.md`) |
|---|---|---|
| "Já temos administradora" | Síndico, conselho | Não substitui: confere o que chega dela, a favor do condomínio |
| "Já temos software" | Síndico | O sistema da administradora registra; este confere e mostra o que merece atenção |
| "Não quero outro sistema" | Síndico morador | Você recebe um resumo e decide; não precisa lançar nada |
| "A IA pode errar" | Conselho | Cada ponto vem com o documento; regra conferível; pessoa decide; economia revisada por pessoa antes de chegar |
| "Quem fornece os dados?" | Todos | A pasta que a administradora já envia; extrato do banco; contratos |
| "Quanto custa?" | Síndico, assembleia | Faixa fixa + diagnóstico inicial; êxito só sobre economia realizada e medida (H) |
| "Quem aprova as ações?" | Conselho | O síndico, dentro da alçada; nada sai sem aprovação; o sistema não paga nem envia |
| "Vão expor a administradora?" | Administradora | Linguagem de indício, nunca acusação; ela vê e responde |

## 6. Jornada de compra (H, a validar)

1. **Gatilho:** assembleia de contas, conta que subiu, troca de síndico, reclamação de condômino.
2. **Busca:** Google (93%), YouTube (74%), Instagram (67%) são os canais de informação do síndico (Datafolha 2025, F); indicação de síndico profissional e grupos de síndicos.
3. **Avaliação:** demonstração com dados do próprio condomínio (diagnóstico do mês).
4. **Justificativa:** conselho e, se acima da alçada, assembleia. Precisa de documento simples: o que é, quanto custa, o que encontrou no diagnóstico, quem decide.
5. **Decisão e implantação:** coleta de documentos com a administradora.
6. **Prova contínua:** relatório mensal ao conselho; economia por estágio.

## 7. Mensagens candidatas por interlocutor (para teste, não validadas)

| Interlocutor | Mensagem |
|---|---|
| Síndico morador | "Todo mês, cada despesa do condomínio conferida. Você recebe só o que merece atenção, com a prova, e decide." |
| Síndico profissional | "Conferência mensal padronizada em todos os seus condomínios, com relatório pronto para o conselho." |
| Conselho | "Parecer sobre as contas com evidência: contrato, nota, extrato e histórico lado a lado." |
| Administradora | "Menos pedidos repetidos e menos discussão sobre status: o síndico vê o que você já entregou." |

## 8. Lacunas que só pesquisa primária fecha

1. Disposição a pagar e quem paga (caixa do condomínio × síndico profissional; limite sem assembleia).
2. Fluxo real da conferência mensal (tempo, formatos, atraso da administradora; reação da administradora).
3. Preço e frequência atuais de auditoria e consultoria por êxito (não há dado público 2023–2026).
4. Confiança em achado de IA e reação às palavras "assessor", "auditoria", "IA".
5. Tamanho real do segmento-alvo em SP e taxa de troca de síndico.

Plano para fechar: `07_TESTES_COM_CLIENTES.md`.
