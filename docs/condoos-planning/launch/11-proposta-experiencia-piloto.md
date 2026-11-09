# Launch — proposta: experiência do síndico no piloto (LB-080..LB-086)

Data: 09/11/2026. **Aprovada pelo Marcio em 09/11/2026 com as recomendações (Q-L07..Q-L10) e implementada (D108).**

## 1. Por que esta fatia, antes da LF6

O Marcio perguntou se o sistema já guia o síndico passo a passo na implantação e na operação. Para responder, o app foi percorrido no celular (390 px) em 09/11/2026, numa stack local sem Docker, em dois casos: o Bosque dos Ipês recém-cadastrado (`docs/pilot/onboarding-bosque-dos-ipes.json`, síndica Helena) e o Jardim das Acácias do seed, com 12 meses de dados (síndica Ana).

O que já funciona (LF2–LF4): objetivo inicial, no máximo três próximos passos com motivo e o que liberam, "Fazer depois", "O que já fiz por você", o cartão de primeiro valor e "Decisões aguardando você" no Hoje.

O que impede chamar isso de guia:

| # | O que se viu | Causa no código |
|---|---|---|
| 1 | Não há "passo X de N". Ao tocar no passo, o síndico vai para a tela genérica de envio, que não lembra o que foi pedido. | `steps.py` devolve só os passos pendentes; `enviar/page.tsx` não recebe o passo |
| 2 | O contrato enviado fica em conferência, os marcos não andam e Contratos diz "Nenhum contrato cadastrado. Envie os contratos em PDF…", sem botão. | O contrato só existe depois da revisão (D59); `contratos/page.tsx` olha só `contract` |
| 3 | Depois da implantação não há roteiro do mês. No Acácias, com 12 meses de dados, o cartão ainda pergunta "Por onde quer começar?". | O cartão depende só de `goal` e `dismissed` (`JourneyCard.tsx`) |
| 4 | "Auditoria do mês" mostra R$ 0 em risco (setembro) logo abaixo de 6 decisões pendentes de outubro. | O resumo usa o último mês **fechado** (`findings.py::month_summary`), e a tela não diz isso |
| 5 | Para um condomínio novo, o Hoje abre com "0 decisão(ões); 0 risco(s)" e o alerta "nenhum documento novo há mais de 35 dias (nenhum ainda)". | Texto do briefing (`app/briefing/`) igual para "atrasado" e "ainda não começou" |
| 6 | Na lista de achados a severidade é só uma bolinha colorida. Um achado de R$ 22.401 "baixo" parece menos importante que um de R$ 6.000 "médio", sem explicação. | `InsightCard.tsx`: o texto da severidade fica só no `aria-label`. Contraria a regra "status sempre com texto e ícone" |
| 7 | O link de volta de Enviar diz "Resumo"; a aba se chama "Hoje". | `enviar/page.tsx` |
| 8 | "Pergunte ao CondoOS" aparece em todas as telas mesmo quando o chat não responde (sem chave, 503) e cobre parte do conteúdo. | Botão fixo sem consultar a prontidão do chat |
| 9 | O detalhe do achado não diz o que acontece depois de Confirmar, Contestar ou Ignorar e, depois de decidir, não leva ao próximo. | `DecisionBar` só registra a decisão |

Esses pontos atrasam a primeira sessão do piloto e a rotina de cada mês. A LF6 (monitores, troca de síndico, alertas internos) melhora o que a equipe CondoOS vê, mas não muda o que o síndico vê. Por isso a recomendação é fazer esta fatia primeiro.

Referências: prompt do Launch §2 ("no máximo 3–5 ações, uma principal", "celebrar resultados", "Centro de Evolução") e §3.1 (porquê de cada pergunta; estados de carregamento, sucesso e erro); Especificação FR-032 (briefing) e FR-033 (próxima ação com motivo); blueprint §5 (modo "Faça comigo").

## 2. Proposta

Todos os itens reaproveitam `app/launch/`, `app/briefing/` e os componentes existentes. **Sem migração.** As mudanças de API só **acrescentam** campos.

### LB-080 — Guia em passos ("Faça comigo") · M

- O cartão mostra **um passo em foco** e o progresso do objetivo: "Passo 2 de 4 · Envie as notas do último mês". Os demais ficam numa linha recolhida ("Depois: convenção, pedido de documentos").
- O total vem da ordem do objetivo (`steps.ORDER`); os passos feitos são calculados dos dados, como hoje. Nada é gravado e o progresso nunca vale como permissão (D89).
- O passo leva à tela com contexto: `enviar?passo=enviar_contrato` mostra "Você está enviando: um contrato de serviço contínuo" e o motivo, e recebe qualquer arquivo, como hoje.
- Depois do envio, o cartão de primeiro valor (ou a lista do lote) traz **"Continuar o guia"**, que volta ao Hoje com o próximo passo em foco. Ao concluir um passo, o cartão diz o que foi liberado ("Leitura de contratos: pronta"), sem contar cliques nem arquivos (prompt §2).
- API: `GET /launch` ganha `progress: {done, total}` e o passo em foco.

### LB-081 — "Em conferência" visível · P

- Enquanto um documento enviado pelo condomínio espera a revisão, o cartão e o Hoje mostram: "Contrato Brilho Total: em conferência pela equipe CondoOS desde 09/11, 14:26". Isso é feito a partir de `document` (status da extração) e de `pending.py::arrivals` (D102).
- Contratos sem contrato cadastrado mas com contrato em conferência: "1 contrato em conferência. Ele aparece aqui assim que a equipe CondoOS confirmar." Sem nenhum: o texto atual mais o botão **"Enviar contrato"**.
- Nenhum prazo é prometido sem decisão (pergunta Q-L07).

### LB-082 — Roteiro do mês no Hoje · M

Quando LM3 está concluído, o cartão de implantação vira uma linha ("Implantação: 3 de 5 marcos · ver") e o topo do Hoje passa a ser **"Seu mês: outubro de 2026"**. São no máximo três itens, montados por código só a partir de registros (como o briefing, D82):

1. **Documentos do mês:** "5 de 7 contratos com nota recebida" (cobertura, D92/D102), com o botão "Enviar" ou "Pedir a quem tem".
2. **Suas decisões:** "6 pontos de atenção aguardando você · R$ 35.801" e o botão "Decidir o primeiro" (o de maior valor).
3. **Fechamento:** "Aguardando a conferência de 2 documentos" ou "Pronto para fechar" (só leitura para o síndico; fechar continua com quem já pode).

Item sem pendência some. Com os três vazios: "Nada pendente neste mês." O objetivo inicial ("Por onde quer começar?") deixa de aparecer depois de LM3, mesmo sem objetivo escolhido.

### LB-083 — Hoje sem mensagens que se contradizem · P

- O bloco "Auditoria do mês" passa a dizer qual mês é e por quê: **"Último mês fechado: setembro de 2026"**. Quando há mês aberto com pontos pendentes, aparece a linha "Outubro de 2026 (em aberto): 6 aguardando decisão", com link. O padrão do resumo (último mês fechado) **não muda**: é a visão do relatório.
- O briefing separa "ainda não começou" de "atrasado". Num condomínio sem nenhum documento: "Ainda não recebemos documentos. Assim que chegarem, eu aviso aqui." (tom informativo, sem a borda de alerta). O critério de "dados parciais" do D82 continua igual; muda só o texto quando a fonte nunca recebeu nada.
- Frases sem "(ões)" e sem zeros: "6 decisões aguardam você." Contagem zero é omitida.
- O link de volta de Enviar passa a dizer "Hoje".

### LB-084 — Severidade com texto e prioridade explicada · P

- Lista de achados: o selo de severidade com texto e ícone ("Grave", "Médio", "Baixo"), como no detalhe (`SeverityBadge`).
- No detalhe, uma linha curta explica o que a severidade mede (a regra), separada do valor em risco, para que um valor alto com severidade baixa faça sentido. O texto vem da regra (`docs/rules.md`), sem números novos.

### LB-085 — "Pergunte ao CondoOS" só quando responde · P

- O botão fixo aparece só quando a prontidão do chat está pronta (a mesma verificação de `readiness.py`, chave e modo do LLM). Sem chat, some e a rota `/pergunte` explica "Indisponível no momento".
- Ele deixa de cobrir conteúdo: as telas reservam o espaço do botão no fim da página.

### LB-086 — Depois de decidir, o próximo · P

- Acima de Confirmar, Contestar e Ignorar, uma linha diz o que cada um faz (texto fixo por ação, vindo de `findings/decisions.py`; a interface continua mostrando só `allowed_actions`).
- Depois da decisão: "Decisão registrada" e o botão **"Próximo ponto de atenção"** (o de maior valor ainda pendente), ou "Tudo decidido neste mês", com volta ao Hoje.

## 3. Fora do escopo

- Guia conversacional por chat (prompt §3.1, "chat integrado ao fluxo"): depende do LLM em cada sessão. Os cartões cobrem o piloto sem custo de IA; o chat continua como ajuda à parte.
- Tour de primeira visita, dicas sobrepostas e mudança das abas de baixo.
- Esconder telas (Oportunidades, Aprovações, Pedidos) do síndico: ver a pergunta Q-L09.
- LF6 e qualquer item de LF7.
- Migração, permissão nova, envio externo.

## 4. Testes e aceite

- **Backend:** progresso do guia por objetivo e estado dos dados (tabela de casos em `test_launch.py`); roteiro do mês com teste positivo e negativo de cada item (`test_launch.py` ou `test_briefing.py`); "ainda não começou" × "atrasado" no briefing, mantendo o teste do D82; conselheiro e outro condomínio continuam 403/404.
- **E2E** (`launch.spec.ts`, `findings.spec.ts`):
  - (a) a Helena (condomínio novo) escolhe "Economizar dinheiro", envia o contrato pela tela com contexto, toca em "Continuar o guia" e volta ao Hoje com "Passo 2 de N";
  - (b) a Ana (Acácias) vê "Seu mês", decide um ponto de atenção e chega ao próximo;
  - (c) a lista de achados mostra a severidade em texto.
- **Capturas antes e depois** dos mesmos dois roteiros, no celular, em `docs/screens/`.
- **Aceite da fatia:** nos dois roteiros acima, o síndico não precisa sair do caminho indicado pela tela para concluir a tarefa, e nenhuma tela mostra informação que contradiga outra. `make test`, `make lint` e `make e2e` passando no docker.

Registros ao fim: `decisions.md` (D108), `00-status-e-proximos-passos.md`, `05-backlog.md`, `docs/roadmap-status.md` e `docs/traceability.md` (FR-032, FR-033).

## 5. Perguntas para o Marcio

| # | Pergunta | Recomendação se não houver resposta |
|---|---|---|
| Q-L07 | Mostrar ao síndico um prazo de conferência da equipe CondoOS (ex.: "até 1 dia útil")? Isso vira compromisso de serviço no piloto. | Não mostrar prazo; só "em conferência desde <data e hora>" |
| Q-L08 | No Hoje, o bloco de auditoria deve continuar no último mês fechado (visão do relatório) ou passar para o mês aberto? | Manter o mês fechado, com o nome explícito e a linha do mês aberto (LB-083) |
| Q-L09 | Esconder do síndico do piloto as telas que ele não usará no começo (Oportunidades, Aprovações)? | Não esconder: elas já ficam fora das abas e só aparecem por link |
| Q-L10 | Fazer esta fatia antes da LF6? | Sim: LB-080, LB-081, LB-083 e LB-084 primeiro (maior efeito na primeira sessão), depois LB-082, LB-085 e LB-086 |
