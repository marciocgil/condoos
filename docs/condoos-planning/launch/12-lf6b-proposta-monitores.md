# Launch LF6-b — proposta: monitores diários, alertas internos e Centro de Evolução (LB-060, LB-062, LB-063)

Data: 09/11/2026. **Aprovada pelo Marcio em 09/11/2026 com as recomendações (Q-L11..Q-L14) e implementada (D110).** A LF6-a (troca de síndico, histórico das capacidades e rollback) já foi entregue sem migração (D109).

## 1. O que falta da LF6 e por que pede decisão

O prompt do Launch (§3.8 e Fase 6) pede que o CondoOS perceba sozinho quando os dados deixam de valer: canal parado, contrato aditado, revisor removido, síndico trocado. Pede também que avise a equipe "sem poluir a caixa do síndico" e que sugira o próximo ajuste quando surgir uma demanda real (Centro de Evolução).

Hoje parte disso já aparece, mas só quando alguém abre a tela certa:
- a prontidão mostra o que falta;
- o histórico (D109) mostra quando uma capacidade caiu;
- a saúde do e-mail de entrada mostra a última mensagem (D101).

Nada junta esses sinais num lugar que a equipe CondoOS acompanhe, com dono e conclusão.

Duas escolhas são difíceis de desfazer e por isso vêm para você: **onde guardar os alertas** (migração) e **quem os vê**.

## 2. Monitores (LB-060)

Um job diário, o mesmo `launch.health` da D109, roda detectores determinísticos, versionados e idempotentes, no padrão da D93. Cada detector abre um alerta quando a condição aparece e o marca como "superado" quando ela some, se ninguém agiu nele.

| Monitor | Condição | Para quem importa |
|---|---|---|
| Canal parado | E-mail de entrada ativo e nenhum documento por nenhum canal há mais de 35 dias, havendo contrato que espera nota | Equipe |
| Contrato aditado | Aditivo novo desde a última verificação, com valor ou prazo diferente do contrato | Equipe (conferir regras e agenda) |
| Revisor ausente | Nenhuma revisora CondoOS ativa, com C4 ou C9 dependendo dela | Equipe |
| Síndico sem acesso | Síndico no corpo diretivo sem acesso ativo ao CondoOS, ou acesso de síndico vencendo em até 7 dias | Equipe |
| Ações paradas | Ação aprovada e entregue a uma pessoa há mais de 7 dias sem execução registrada | Equipe e síndico |

Nenhum monitor muda permissão. O que cada função pode fazer continua vindo da prontidão e da política.

## 3. Onde ficam os alertas (LB-062): a decisão principal

| Opção | Como | A favor | Contra |
|---|---|---|---|
| **A (recomendada)** | Reaproveitar `data_issue` com tipos novos e uma coluna `audiencia` (`condominio` ou `equipe`). **Migração 0024**: amplia a lista de tipos e acrescenta a coluna (padrão `condominio`, o que já existe não muda). | Ciclo pronto (aberto, resolvido, descartado, superado), histórico só de inclusão, dono e motivo, Central de Validação e visão da carteira já existentes | Alerta não é bem "conflito entre documentos"; o nome `data_issue` fica mais largo do que a D93 descreveu |
| B | Tabela nova `health_alert` com o mesmo ciclo. Migração 0024 com tabela, RLS e eventos | Separação limpa entre conflito e alerta | Duplica ciclo, telas e testes que já existem |
| C | Sem guardar: alertas calculados a cada leitura | Sem migração | Sem dono, sem "resolvido", sem histórico; a mesma coisa reaparece todo dia |

Com a opção A, a Central de Validação continua mostrando ao síndico só o que é do condomínio (`audiencia = condominio`). Os alertas internos aparecem para a equipe CondoOS na Carteira (coluna "Alertas") e em Configurações. A gerente da administradora vê os alertas do condomínio que acompanha.

## 4. Centro de Evolução (LB-063)

Sugestões calculadas a partir dos dados, sem tabela nova. "Agora não" e "Já resolvi" usam o `launch_state.postponed`, que já existe. Cada sugestão diz o que se observou, o que muda se for feita e um botão.

| Sinal observado | Sugestão |
|---|---|
| Notas de um fornecedor em 2 meses ou mais, sem contrato cadastrado | Envie o contrato desse fornecedor |
| Documentos só por envio manual há 60 dias, com e-mail de entrada configurado | Encaminhe as notas para o e-mail do condomínio |
| 3 pedidos de documento compartilhados à mão | O CondoOS pode enviar o e-mail do pedido com sua aprovação (D103) |
| 2 meses sem extrato bancário com despesas lançadas | Envie o extrato para conferir os pagamentos |
| Alçada não configurada e uma ação com custo pedida | Configure a alçada |

O síndico vê as sugestões em Ajustes e a equipe em Configurações. São no máximo 3 por vez, e cada uma só aparece quando a demanda já existe.

## 5. Fora do escopo

- Envio de alerta por e-mail ou WhatsApp: tudo fica dentro do app, como o briefing (D82).
- Leitura de ata de eleição para detectar troca de síndico (fica para quando houver ata real no piloto).
- Score de saúde: a prontidão continua binária por capacidade.
- LF7.

## 6. Testes previstos

- Teste positivo e negativo de cada monitor, com o seed sem falso positivo (como na D93).
- Alerta que some vira "superado"; o que uma pessoa resolveu fica.
- O síndico não vê alerta da equipe, nem na Central de Validação nem na API; outro condomínio responde 404.
- A migração 0024 é testada de ida e volta.
- Cada sugestão do Centro de Evolução aparece só com o sinal, e "Agora não" a esconde pelo prazo.
- E2E: a equipe vê o alerta na Carteira e o resolve; o síndico vê a sugestão em Ajustes.

## 7. Perguntas para o Marcio

| # | Pergunta | Recomendação se não houver resposta |
|---|---|---|
| Q-L11 | Onde guardar os alertas internos: A (`data_issue` com `audiencia`), B (tabela nova) ou C (sem guardar)? | A, com a migração 0024 |
| Q-L12 | Quem vê os alertas internos: só a equipe CondoOS, ou também a gerente da administradora do condomínio? | Equipe CondoOS e gerente; o síndico só vê os de `audiencia = condominio` |
| Q-L13 | Prazos: canal parado em 35 dias, acesso vencendo em 7 dias e ação parada em 7 dias? | Esses três |
| Q-L14 | O Centro de Evolução aparece também para o síndico, ou só para a equipe no piloto? | Para os dois, no máximo 3 sugestões |
