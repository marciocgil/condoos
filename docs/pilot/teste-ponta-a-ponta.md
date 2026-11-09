# Teste de ponta a ponta antes do piloto

Roteiro para percorrer o CondoOS inteiro com dados fictícios, do jeito que o piloto vai acontecer:

1. a equipe CondoOS cadastra o condomínio e dá o acesso à síndica;
2. a síndica entra e pede documentos à administradora;
3. a administradora envia os arquivos por um link, sem criar conta;
4. a equipe CondoOS confere a leitura;
5. a síndica acompanha os resultados.

Ensaiado do começo ao fim na stack local em 09/11/2026 (seção 9). As capturas de tela estão em `docs/screens/teste-ponta-a-ponta/`.

**Tempo:** cerca de 1 hora. **Dados:** só fictícios: os documentos do corpus de teste e um condomínio inventado.

---

## 1. Quem faz o quê

São quatro papéis. Uma pessoa só consegue fazer todos, mas **cada papel precisa de uma sessão própria**: um navegador diferente, ou um perfil diferente do Chrome.

| Papel | Onde | Como entra |
|---|---|---|
| **Admin CondoOS** (você) | Chrome, janela normal | Link de acesso no seu e-mail |
| **Revisora CondoOS** | Chrome, uma única janela anônima | Link de acesso num segundo e-mail seu |
| **Síndica** | Celular, ou outro navegador (Edge, Safari, Firefox) | Link de acesso num terceiro e-mail seu |
| **Administradora** | Sem login; de preferência outro navegador | **Sem conta**: só o link do pedido |

**Atenção:** todas as janelas anônimas do mesmo navegador dividem uma só sessão. Duas janelas anônimas no Chrome fazem a segunda entrar logada como a primeira, e "Sair" numa derruba as duas. Use no máximo uma janela anônima por navegador, ou perfis separados do Chrome, um por papel.

**E-mails em produção:** use endereços reais seus. O Gmail entrega `seu-email+sindica@gmail.com`, `seu-email+revisora@gmail.com` e `seu-email+administradora@gmail.com` na sua própria caixa, e cada um vale como uma pessoa diferente no CondoOS. Não use `@example.com` em produção: a Amazon devolve a mensagem e o link nunca chega (D105).

**Limite:** cada e-mail pode pedir até 5 links de acesso por hora.

## 2. Arquivos que a administradora vai enviar

Os arquivos estão em `api/tests/fixtures/corpus/`. São fictícios, todos em nome do condomínio de **CNPJ 49.788.750/0001-69**, que é o que você vai cadastrar.

| Arquivo | O que é | Para que serve no teste |
|---|---|---|
| `20_contrato.pdf` | Contrato de limpeza (Brilho Total), R$ 9.200,00 por mês, IPCA, vigência até 31/12/2026 | Leitura de contrato, agenda e vencimento |
| `02_nfse.pdf` | NFS-e de outubro da mesma empresa de limpeza | Nota ligada ao contrato |
| `01_nfse.pdf` | NFS-e de portaria, R$ 17.156,53 líquido | Fica acima da alçada de R$ 5.000 |
| `03_nfse.pdf` | NFS-e de manutenção de elevadores | Nota sem contrato |
| `17_recibo.pdf` | Recibo de conserto do portão | Recibo de pessoa física |
| `21_nfe.xml` | NF-e de material (lâmpadas) | Leitura de XML |
| `26_foto_nfse.jpg` | Foto da **mesma** NFS-e do `01` | O sistema não pode contar a mesma nota duas vezes |

Não há extrato bancário no corpus. Por isso as notas aparecem como "Nota sem pagamento registrado", e isso é o comportamento esperado.

## 3. Preparação (só em produção)

Faça isto no servidor, como o usuário `condoos`, dentro de `~/condoos`. O roteiro segue o teste de fumaça de `docs/deploy.md` (9.9): tudo o que o teste criar é apagado no fim pela restauração do backup.

Abreviação usada nos comandos:

```bash
C="docker compose -f docker-compose.prod.yml --env-file deploy/.env.production"
```

1. Faça um backup e **anote o nome do arquivo**:

   ```bash
   deploy/backup.sh
   ```

2. Desligue a consulta de CNPJ. Os CNPJs do corpus são inventados e podem existir de verdade:

   ```bash
   SUPPLIER_PROVIDER=offline docker compose -f docker-compose.prod.yml --env-file deploy/.env.production up -d api worker
   ```

3. Cadastre a revisora, um segundo e-mail seu:

   ```bash
   $C exec api python -m app.platform add-person seu-email+revisora@gmail.com "Revisora Teste"
   ```

   ```bash
   $C exec api python -m app.platform grant-role seu-email+revisora@gmail.com condoos_reviewer "Teste de ponta a ponta"
   ```

Na stack local, use `make reset`, depois `make up`, e os mesmos comandos com `docker compose exec api python -m app.platform ...`. Ali os e-mails chegam no Mailpit (`http://localhost:8025`). Atenção: na stack local o seed já usa o CNPJ do corpus. Num banco com seed, cadastre outro CNPJ, e os documentos irão para a fila com o motivo "CNPJ do tomador não é o do condomínio".

---

## 4. Passo a passo

### Etapa A: o Admin CondoOS cadastra o condomínio e dá o acesso à síndica

1. Entre como Admin. Em **Carteira**, clique em **Novo condomínio**.
2. Preencha:
   - **Nome:** `Condomínio Teste Ponta a Ponta (fictício)`
   - **CNPJ:** `49.788.750/0001-69`
   - **Endereço curto:** `teste-ponta-a-ponta`
   - **Endereço:** `Rua Fictícia do Teste, 100 — Cidade Modelo/SP`
   - **Unidades:** `48`
   - **Alçada do síndico (R$):** `5.000,00`
   - **Síndico, nome completo:** `Síndica Teste`
   - **Síndico, e-mail:** `seu-email+sindica@gmail.com`
   - **Início do mandato:** `01/01/2026`

   Captura: `01-admin-novo-condominio.png`.
3. Clique em **Cadastrar condomínio**. Você cai em **Configurações** desse condomínio.
4. Confira:
   - em **Pessoas com acesso** aparecem Síndica Teste e você;
   - em **O que já funciona**, "Ações com sua aprovação" está em **Análise parcial**, com o motivo "Nenhum síndico com acesso ativo entrou no CondoOS". É esperado: a síndica ainda não entrou (D109).
5. Em **Equipe CondoOS**, clique em **Atribuir** e preencha:
   - **E-mail:** o da revisora
   - **Papel:** Revisão CondoOS
   - **Motivo:** "Teste de ponta a ponta"

   Clique em **Atribuir**. A revisora aparece como **Ativa**. Captura: `02-admin-configuracoes.png`.

**Confira:** o condomínio aparece na Carteira, a síndica tem acesso e a revisora está atribuída.

### Etapa B: a síndica entra pela primeira vez

1. No celular, abra `https://app.condoos.ia.br`, digite o e-mail da síndica e toque em **Receber link de acesso**.
2. Abra o e-mail "CondoOS" e toque no link. Ele vale 15 minutos e serve uma vez só.
3. A tela **Hoje** mostra o cartão **Implantação do seu assessor**: "Sou seu assessor CondoOS…" e **Por onde quer começar?**. Captura: `03-sindica-primeiro-acesso.png`.
4. Toque em **Organizar pendências**. O cartão passa a mostrar **Passo 1 de N** com um passo em foco.

**Confira:**
- não há senha nem cadastro: a síndica entra só pelo link;
- o cartão mostra um passo por vez;
- o resumo do dia aparece como "Começando", e não como erro.

### Etapa C: a síndica pede os documentos à administradora

1. Abra o pedido por uma destas telas:
   - **Enviar** (a partir do Hoje), tocando em **Não está com você? Peça a quem tem os documentos**;
   - ou **Pedidos**, depois **Novo pedido**.
2. Preencha:
   - **Para quem:** `Administradora Exemplo (fictícia)`
   - **Quem é:** Administradora
   - **Outro documento:** escreva e toque em **Incluir**, um de cada vez:
     - `Contrato de limpeza em vigor`
     - `Notas fiscais de outubro de 2026`
     - `Recibos de outubro de 2026`
   - **Prazo:** deixe o sugerido (7 dias)
   - **Observação:** `Teste do CondoOS com documentos fictícios.`

   Captura: `04-sindica-novo-pedido.png`.
3. Toque em **Preparar pedido**. O pedido abre como **Autorizado**, com os três itens pendentes.
4. Escolha como mandar. Faça a opção **a** pelo menos uma vez, porque é o único envio externo do sistema (D103).
   - **a) O CondoOS envia por e-mail:**
     1. No cartão **Enviar por e-mail pelo CondoOS**, toque em **Preparar e-mail**.
     2. Em **E-mail de quem vai enviar os documentos**, informe `seu-email+administradora@gmail.com`.
     3. Toque em **Ver o e-mail antes de enviar**. A prévia mostra o remetente, "responder para" com o e-mail da síndica, o assunto e o texto (captura `05-sindica-email-previa.png`).
     4. Toque em **Aprovar e enviar**.
   - **b) A síndica manda pelo WhatsApp:** toque em **Gerar link e texto**, depois em **Copiar texto** ou **Compartilhar**, e por fim em **Já enviei**. Gerar de novo invalida o link anterior.
5. Recarregue a tela.
   - O pedido mostra "O CondoOS enviou por e-mail em …".
   - Embaixo aparece **Aceito pelo servidor de e-mail**, com o endereço mascarado (`a***@…`). Isso não significa "entregue". Captura: `06-sindica-pedido-enviado.png`.
   - No **Hoje**, o quadro **Pedidos de documentos** mostra o pedido em **Com outros**.

**Confira:**
- a prévia é exatamente o e-mail que chega;
- nada é enviado sem a aprovação da síndica;
- o endereço da administradora fica mascarado depois do envio.

### Etapa D: a administradora envia os arquivos pelo link

1. Na caixa `+administradora`, abra o e-mail "Pedido de documentos do Condomínio Teste…" e clique no link. Use outro navegador, sem login.
2. A página **Envio de documentos** mostra o condomínio, o prazo e os três itens pedidos. Captura: `07-administradora-pagina-de-envio.png`.
3. Clique em **Escolher arquivos** e selecione os 7 arquivos da seção 2, todos de uma vez.
4. Cada arquivo aparece como **Recebido**. Captura: `08-administradora-envio-concluido.png`.
5. **Teste de segurança (opcional):** envie um PDF protegido por senha. Ele tem de ser recusado com o motivo.

**Confira:**
- a administradora não cria conta;
- o link só serve para enviar: ela não vê nada do condomínio;
- a página diz até quando o link vale.

### Etapa E: a síndica confere o que chegou e conclui o pedido

1. No **Hoje** da síndica, o quadro **Pedidos de documentos** mostra em **Com você**: "Conferir os arquivos recebidos". Captura: `09-sindica-hoje-arquivos-chegaram.png`.
2. Toque no pedido. Em **Arquivos recebidos** aparecem os 7 arquivos, com o tipo que o CondoOS reconheceu (Contrato, NFS-e, NF-e, Recibo…). Captura: `10-sindica-arquivos-recebidos.png`.
3. Em **O que foi pedido**, toque em **Recebido** em cada um dos três itens.
4. O pedido muda para **Concluído**. Captura: `11-sindica-pedido-concluido.png`.
5. Abra o link da administradora de novo: ele deve dizer **Link inválido ou fora do prazo**.

**Confira:**
- o pedido só conclui quando a síndica confirma os itens;
- depois de concluído, o link para de funcionar.

### Etapa F: a equipe CondoOS confere a leitura

1. Entre como **revisora** no computador. Depois de 1 ou 2 minutos (o worker lê os arquivos), abra **Fila de exceções**. Captura: `12-revisora-fila.png`.
   - **Em produção** (com Docling e IA), a maior parte dos documentos é lida sozinha. O que cair na fila vem com o motivo: "baixa confiança", "não encontrado", "foto sem texto legível".
   - **Na stack local** (sem IA), quase tudo cai na fila.
2. Para cada item da fila, clique em **Corrigir**:
   1. Confira o tipo do documento.
   2. Preencha os campos marcados "não encontrado" ou "baixa confiança" olhando o documento. Cada campo lido mostra o trecho e a página de origem.
   3. Clique em **Salvar correção**.

   Captura: `13-revisora-corrigir-contrato.png`. Valores certos do contrato:
   - CNPJ da contratada `92.728.617/0001-46`
   - Razão social `Brilho Total Conservação e Limpeza Ltda`
   - Objeto `limpeza e conservação das áreas comuns do condomínio`
   - Valor mensal `9.200,00`
   - Índice IPCA, mês-base janeiro
   - Início `01/01/2023`, fim `31/12/2026`
3. **A foto `26_foto_nfse.jpg`** é a mesma nota da `01` (NFS-e 2037). Depois de corrigida, ela **não pode virar uma segunda despesa**: no fim devem existir **5 despesas**, não 6.
4. Com a fila vazia, abra **Validação** e filtre pelo condomínio de teste.
   - Não deve haver divergência entre documentos.
   - Pode haver **Alertas de saúde** (D110). Exemplo: sem revisora atribuída aparece "Sem revisora CondoOS atribuída", e você já atribuiu uma na Etapa A.
5. Em **Carteira**, o condomínio aparece com os achados abertos e a coluna **Alertas**.

**Confira:**
- nenhum valor é "chutado": campo incerto vai para a fila com o motivo;
- a correção fica registrada;
- a duplicata não vira despesa nova.

### Etapa G: a síndica acompanha os resultados

1. **Hoje:**
   - **Seu mês: outubro de 2026** mostra as decisões que esperam por ela e o fechamento ("Aguardando a conferência…" ou "Pronto para fechar"). Captura: `14-sindica-hoje-resultados.png`.
   - O cartão de implantação vira uma linha ("Implantação: 4 de 5 marcos…").
   - O resumo do dia já mostra os documentos recebidos: ele é refeito sozinho quando chega registro novo (D111).
2. **Contratos:** o contrato da Brilho Total, com valor mensal de R$ 9.200,00, índice IPCA, próximo reajuste em 01/2027, fim em 31/12/2026 e o selo **Vence em N dias**. Captura: `15-sindica-contratos.png`.
3. **Achados:** a lista mostra cada ponto com o selo de severidade em texto. Captura: `16-sindica-achados.png`. Esperado com estes arquivos:
   - **Nota sem pagamento registrado** (Baixo) para as notas e o recibo, porque não foi enviado extrato;
   - **Despesa acima da alçada sem aprovação** (Médio) para a portaria, de R$ 17.156,53 contra a alçada de R$ 5.000,00.
4. **Detalhe de um achado:**
   1. Abra um achado.
   2. Confira "Por que foi apontado", as evidências e a linha que explica a severidade.
   3. Toque em **Confirmar**, **Contestar** (exige motivo) ou **Ignorar**. Cada botão diz antes o que faz.
   4. Depois de decidir aparecem **Próximo ponto de atenção** e **Voltar ao Hoje**.
5. **Agenda:** a nota prevista do contrato de limpeza e o fim do contrato.
6. **Ajustes:**
   - **O que já funciona** mostra as funções que passaram a operar;
   - **Mudanças recentes** mostra quando cada uma mudou;
   - o e-mail de entrada do condomínio também está lá.
7. **Relatório:** no Hoje, toque em **Baixar relatório em PDF**. Com o mês aberto, ele sai marcado como "em aberto — prévia".
8. **Pergunte ao CondoOS**, se a chave de IA estiver ativa em produção: pergunte "Quanto pagamos de limpeza em outubro?" e confira se a resposta cita a nota.

**Confira:**
- a síndica entende o que aconteceu sem ajuda;
- cada número na tela tem de onde veio;
- nenhuma tela contradiz outra.

### Etapa H (opcional): troca de síndico

1. Como Admin, em **Aprovações**, toque em **Pedir ação com aprovação** e peça uma ação simples (por exemplo, agendar uma visita técnica). Como síndica, aprove essa ação em **Aprovações**. Depois, como Admin, em **Configurações**, **Pessoas com acesso**, remova a Síndica Teste.
2. Confira:
   - a ação aprovada por ela volta para aprovação;
   - "Ações com sua aprovação" vai para **Análise parcial**;
   - **Mudanças recentes** registra "Troca de síndico";
   - a sessão aberta da síndica não abre mais o condomínio (D109).

---

## 5. Lista de verificação

| # | Verificação | Esperado | OK? |
|---|---|---|---|
| 1 | Condomínio cadastrado | Aparece na Carteira; síndica em "Pessoas com acesso" | |
| 2 | Revisora atribuída | "Ativa" em Equipe CondoOS | |
| 3 | Primeiro acesso da síndica | Link chega; Hoje com "Por onde quer começar?" | |
| 4 | Pedido criado | "Autorizado", 3 itens pendentes | |
| 5 | E-mail do pedido | Prévia igual ao recebido; "Aceito pelo servidor de e-mail"; endereço mascarado | |
| 6 | Envio da administradora | Sem login; 7 arquivos "Recebido" | |
| 7 | Conferência da síndica | "Com você"; 7 arquivos com tipo; pedido "Concluído"; link deixa de valer | |
| 8 | Leitura | Em produção, a maioria lida sozinha; o resto na fila com motivo | |
| 9 | Duplicata | Foto da nota 2037 não vira segunda despesa (5 despesas) | |
| 10 | Contrato | Em Contratos, R$ 9.200,00, IPCA, fim 31/12/2026 | |
| 11 | Achados | "Nota sem pagamento registrado" e "Despesa acima da alçada sem aprovação" | |
| 12 | Decisão | Texto de cada botão; "Próximo ponto de atenção" depois | |
| 13 | Seu mês | Decisões e fechamento de outubro | |
| 14 | Relatório PDF | Baixa; marcado "em aberto — prévia" | |
| 15 | Alertas | Equipe vê em Validação; síndica não vê os da equipe | |

## 6. Limpeza (produção)

1. Restaure o backup da preparação. O banco volta a como estava e os serviços sobem de novo com a consulta de CNPJ ligada:

   ```bash
   deploy/restore.sh <nome-do-backup>
   ```

2. No console do S3, apague a pasta `cond/<id do condomínio de teste>/` do bucket `condoos-documentos`. O id aparece no endereço de Configurações (`?condominio=<id>`).
3. Se quiser, retire o papel da revisora de teste:

   ```bash
   $C exec api python -m app.platform revoke-role seu-email+revisora@gmail.com condoos_reviewer
   ```

## 7. O que pode variar e problemas comuns

- **Leitura:** em produção, com Docling e IA, a leitura acerta 87% do corpus (D98). Fotos degradadas costumam ir para a fila. Na stack local, sem IA, quase tudo vai para a fila, e isso não é defeito.
- **Achados:** podem aparecer outros além dos dois esperados. Toda regra explica o motivo na tela; anote os que surpreenderem.
- **O resumo do dia diz "Ainda não recebemos documentos" depois do envio:** desde a D111 isso não deve acontecer. Se acontecer, anote: é defeito.
- **O link de acesso não chega:** confira a caixa certa (o `+sindica` vai para a sua caixa) e o limite de 5 links por hora por e-mail.
- **O documento aparece na fila com "CNPJ do tomador não é o do condomínio":** o condomínio foi cadastrado com outro CNPJ.
- **O link da administradora diz "inválido":** foi gerado um link novo (o anterior para de valer), o pedido foi concluído ou o prazo venceu.
- **"Ações com sua aprovação" em Análise parcial:** a síndica ainda não entrou ou as ações estão pausadas (Ajustes, Pausar automações).

## 8. Registro do ensaio local (09/11/2026)

Rodado na stack local sem Docker: banco vazio, só Admin e Revisora cadastrados pelos comandos de plataforma, sem IA e sem Docling, consulta de CNPJ desligada.

Todas as etapas de A a G funcionaram:
- o condomínio foi cadastrado com o acesso da síndica e a revisora atribuída;
- o e-mail do pedido foi aprovado e enviado ("Aceito pelo servidor");
- a administradora enviou os 7 arquivos pelo link;
- a síndica concluiu o pedido;
- a revisora corrigiu 6 documentos na fila;
- o CondoOS gerou 1 contrato, 5 despesas (a foto duplicada não virou despesa nova) e 6 achados publicados: 5 "Nota sem pagamento registrado" e 1 "Despesa acima da alçada sem aprovação" (portaria);
- a síndica viu "Seu mês", o contrato com "Vence em 52 dias", os achados com severidade em texto e a agenda.

Observações:
- O resumo do dia só mostrou os documentos depois de "Atualizar". Corrigido no mesmo dia (D111): agora ele é refeito sozinho quando chega registro novo.
- A prévia do PDF na tela de correção fica vazia na stack local, porque o armazenamento ali é em memória; em produção ela aparece.
