# Proposta: menu organizado por propósito

Data: 09/11/2026. **Aguardando validação do Marcio.** Nada foi implementado.

## 1. Por que mudar

| Hoje | Problema |
|---|---|
| Desktop: 16 itens soltos, numa lista só | Não diz para que cada item serve; itens de rotina da equipe (Fila, Validação, Métricas) aparecem para todos |
| Celular (síndico): 5 abas (Hoje, Achados, Assuntos, Contratos, Histórico) | 6 telas do síndico ficam fora das abas: Agenda, Aprovações, Oportunidades, Pedidos, Conformidade e Enviar documentos. Só se chega a elas pelo Hoje ou por Ajustes |
| Nomes técnicos | "Fila de exceções", "Validação" e "Pendências" não dizem o propósito para quem não é da equipe |

## 2. Referências usadas

- **Especificação Mestra §7.1 e §7.2:** "o primeiro bloco responde 'o que precisa de mim?'"; "mobile-first nas ações rápidas, desktop-first em análises"; navegação recomendada com Hoje, Assuntos, Agenda, Aprovações, Operação, Contratos e fornecedores, Financeiro/Optimize, Documentos, Relatórios e Configurações. A proposta agrupa esses itens; não remove nenhum.
- **Nielsen Norman Group:** quando há muitos itens sem nomes padronizados, usar dois níveis (grupos curtos no topo, itens dentro), ordenar pela importância e não por ordem alfabética, e validar com teste de árvore.
- **Material Design (barra inferior do celular):** de 3 a 5 destinos, ícone com texto curto, sem "Mais" como último item; o excedente vai para dentro das seções.

## 3. Desktop: grupos com título

Itens sem grupo no topo (o que se abre todo dia), depois os grupos na ordem de uso.

| Grupo | Itens | Para quê |
|---|---|---|
| (topo) | **Hoje** · **Carteira**¹ · **Agenda** | O que precisa de mim agora; todos os condomínios; tudo o que vence |
| **Gestão financeira** | Achados · Aprovações · Oportunidades · Pendências² · Relatórios³ | Conferir o dinheiro, decidir sobre os achados, aprovar acima da alçada, economizar, prestar contas |
| **Gestão operacional** | Assuntos · Conformidade · Pedidos de documentos | Acompanhar o que está em andamento, manter documentos obrigatórios em dia, pedir o que falta |
| **Contratos e documentos** | Contratos · Fornecedores · Enviar documentos | O que o condomínio contratou, com quem, e entrada de documentos |
| **Qualidade dos dados**² | Fila de exceções · Conflitos de dados (hoje "Validação") | Corrigir leituras e resolver divergências entre documentos |
| **Cadastro e configurações** | Dados do condomínio (hoje "Configurações") · Métricas do piloto² | Cadastro, corpo diretivo, acessos, alçadas; indicadores do piloto |
| (rodapé, como hoje) | Pergunte à IA | Perguntas com fonte |

1. Só para quem tem mais de um condomínio.
2. Só para quem trabalha nisso (equipe CondoOS e administradora). O síndico não vê.
3. Novo atalho: relatório do mês, trilha de decisões e dossiês de conformidade, que hoje ficam espalhados na Carteira e nas telas.

**Regra geral:** cada pessoa vê só os itens que o seu papel usa. Hoje o menu do desktop é igual para todos.

## 4. Celular (síndico): 4 abas com seções dentro

| Aba | Abre em | Seções dentro da aba (seletor no topo) |
|---|---|---|
| **Hoje** | Briefing | Prioridades, decisões, próximos vencimentos (como hoje) |
| **Finanças** | Achados | Achados · Despesas (hoje "Histórico") · Aprovações · Oportunidades · Relatório do mês |
| **Rotina** | Assuntos | Assuntos · Agenda · Conformidade · Pedidos |
| **Documentos** | Contratos | Contratos · Enviar documentos |

- **Ajustes** continua no ícone de engrenagem do topo; **Pergunte ao CondoOS** continua como botão flutuante.
- Cada aba mostra um contador quando há algo para o síndico (ex.: Finanças com 2 aprovações aguardando).
- Nenhuma tela some: todas as 13 telas do síndico ficam a no máximo dois toques.

## 5. Como saber se funciona

Teste de árvore rápido com a Karla e um conselheiro no início do piloto (10 minutos, no papel ou numa tela simples): "onde você veria quando vence o seguro?", "onde aprova uma despesa acima da alçada?", "onde manda a nota que chegou no seu e-mail?". Se alguém errar a mesma tarefa, o nome ou o grupo muda antes de implementar.

## 6. Esforço

Só telas: o menu do desktop, a barra do celular e três telas de entrada (Finanças, Rotina, Documentos) com o seletor de seções. Sem mudança no banco nem na API; os endereços atuais continuam valendo (links antigos e e-mails não quebram). Os testes de ponta a ponta que clicam no menu são atualizados junto.

## 7. Decisões que preciso

1. **Grupos do desktop** como na seção 3 (recomendo), ou outros nomes? (Ex.: "Gestão financeira" ou "Dinheiro"; "Gestão operacional" ou "Rotina".)
2. **Celular com 4 abas e seções dentro** (recomendo), ou manter 5 abas e criar um item "Mais"?
3. **Esconder do menu os itens que o papel não usa** (recomendo)?
4. **Criar o atalho "Relatórios"** no grupo financeiro (recomendo)?
5. Renomear **"Validação" para "Conflitos de dados"** e **"Configurações" para "Dados do condomínio"** (recomendo)?
