# Launch LF4 — proposta: pedido de documentos a terceiros com link de envio (migração 0021)

Data: 07/11/2026. **Aprovada pelo Marcio em 07/11/2026 e implementada (D95).** O texto abaixo é a proposta original; diferenças da implementação estão em D95 (PDF só com restrição de uso passa; PDF corrompido é guardado e a leitura diz que não leu). Detalha a ADR-L04 e a ADR-L06 (`03-arquitetura-e-dados.md`), os itens LB-040..LB-046 de `05-backlog.md` e o fluxo F02. Segue a decisão Q-L02 (D89): **o CondoOS gera o link e o texto; quem envia é o síndico, pelo canal dele. Nada sai do sistema.**

## 1. Problema

Hoje, para receber um documento de quem não tem login (administradora sem acesso, fornecedor, contador), o síndico precisa baixar o arquivo e enviá-lo de novo, ou criar um acesso completo para a pessoa. A primeira opção cansa e se perde. A segunda dá acesso demais. O Launch pede delegação: "peça à administradora" com escopo, prazo e acompanhamento, sem dar acesso a nada além do envio.

## 2. Fluxo (F02, primeiro corte)

1. **Preparar o pedido:** no Hoje (próximo passo), na prontidão C8 ("nota de 10/2026 ainda não recebida") ou num assunto, o síndico (ou a equipe CondoOS) prepara um pedido. Informa para quem (nome e papel: administradora, fornecedor, contador, outro), o que é pedido e o prazo. O sistema sugere os itens que faltam: notas fiscais esperadas e não recebidas (C8), aditivos ou contratos.
2. **Autorizar:** o síndico autoriza. Se foi ele quem preparou, a autorização vem junto. A equipe CondoOS só prepara.
3. **Link e texto:** o sistema gera um **link de envio** (validade de 7 dias, só para enviar arquivos) e um **texto pronto** em PT-BR. O síndico copia ou usa "compartilhar" do celular (WhatsApp, e-mail, o que ele usar). O sistema não envia nada. O síndico pode marcar "enviei", mas é só uma declaração dele.
4. **Envio:** quem recebe o link abre uma página simples, sem login. A página mostra o nome do condomínio, o que foi pedido e o prazo. A pessoa envia os arquivos, que passam pela triagem (seção 4) e entram no condomínio do pedido como documentos comuns. Daí seguem o caminho normal: leitura, fila, casamento e conflitos.
5. **Acompanhamento:** o pedido mostra "3 de 5 itens recebidos". Uma nota fiscal pedida conta como recebida sozinha quando a prontidão C8 a vê chegar. Os outros itens o síndico ou a revisora marcam como atendidos, olhando os arquivos recebidos. Pendentes ficam visíveis. Reenviar o texto é sempre uma ação do síndico.
6. **Fim:** "concluído" quando todos os itens forem atendidos, ou "encerrado" pelo síndico. O link expira no prazo ou quando o síndico revoga, e passa a responder como "link inválido". Revogar não apaga nada do que já chegou.

Estados do pedido, sempre separados: `rascunho` → `autorizado` → `aguardando_envio` → `recebendo` → `concluido` | `encerrado` | `expirado` | `revogado`. "Compartilhado" é só uma marca declarada pelo síndico, não um estado. Mensagem preparada não é mensagem entregue.

## 3. Modelo (migração 0021, toda aditiva)

| Tabela | Conteúdo | Observações |
|---|---|---|
| `delegation_request` (RLS) | condomínio, quem preparou, quem autorizou e quando, destinatário (**nome e papel; sem e-mail nem telefone**, porque o sistema não envia nada), escopo em texto, itens (`[{key, label, kind, contract_id?, competence?, attended_at?, attended_by?}]`), prazo, estado, `case_id` opcional, `shared_at` (declarado) | Minimização: o contato fica com o síndico |
| `delegation_link` (RLS) | pedido, **hash** SHA-256 do token (o token em si nunca é guardado), validade, revogação, limite e contagem de arquivos, último uso | Um link ativo por pedido; gerar outro revoga o anterior |
| `delegation_event` (RLS, **só inclusão**) | criado, autorizado, link gerado, compartilhado (declarado), arquivo recebido, arquivo recusado (com o motivo), item atendido, concluído, encerrado, expirado, revogado | Envio externo fica com `user_id` nulo e só ids |
| `document.origin` | aceita `pedido` | CHECK atualizado |
| `document.delegation_request_id` | FK opcional | Para a cobertura do pedido e a trilha |

A volta da migração apaga as três tabelas e a coluna, e converte `origin = 'pedido'` em `upload`. Os documentos ficam.

## 4. Triagem de arquivos (ADR-L06): proposta sem GPL

O ClamAV está fora (é GPL e a regra do projeto proíbe). Um serviço externo de antivírus mandaria documentos do condomínio para terceiros, o que é ruim para a LGPD e tem custo. Proposta para o piloto, **em código e com bibliotecas já usadas (Pillow, pypdfium2: licenças permissivas)**:

1. **Só formatos aceitos hoje** (PDF, JPEG/PNG/WebP, XML fiscal, OFX/CSV/CNAB), identificados pelo conteúdo (`sniff`) e não pela extensão. ZIP, Office e executáveis ficam fora.
2. **PDF:** recusar arquivo criptografado e qualquer PDF com `/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/OpenAction` com ação, `/AA` ou `/RichMedia`. O PDF também precisa abrir no pypdfium2.
3. **Imagens:** abrir e regravar com o Pillow (descarta metadados e qualquer conteúdo escondido), com limite de pixels contra "bombas de descompressão".
4. **XML:** o parser atual já recusa entidades externas.
5. **Entrega:** o arquivo sempre é baixado como anexo, nunca exibido no domínio do app.

Essa triagem vale para **todo envio** (upload com login, e-mail e link), não só para o link. O motivo de cada recusa aparece em PT-BR e vai para o histórico do pedido. Antivírus de assinatura fica para quando houver piloto real e decisão de custo.

## 5. Segurança do link

- Token aleatório de 32 bytes, guardado só como hash. Token inválido, vencido ou revogado responde 404 genérico, sem dizer qual dos casos.
- O link **só envia**: não lista, não baixa e não mostra nada além do nome do condomínio, dos itens pedidos e do prazo.
- Os arquivos gravam no condomínio do pedido, dentro do escopo de RLS daquele condomínio. Teste obrigatório: um token do condomínio A nunca grava em B.
- Limites: 20 MB por arquivo (já existente), 30 arquivos por link, validade de 7 dias (máximo 30).
- O mesmo arquivo enviado duas vezes vira um documento só (hash).
- Cada envio e cada recusa entram no histórico, só com ids.
- O kill switch (`automation_pause`) também pausa os links de um condomínio.

## 6. Permissões

| Ação | Quem |
|---|---|
| Preparar pedido | síndico, CondoOS Admin e Reviewer atribuídos (`MANAGE_CASES`) |
| Autorizar e gerar link | **só o síndico** (`APPROVE_IN_CONDO`) |
| Revogar link, encerrar pedido | síndico e CondoOS Admin |
| Marcar item atendido | síndico e revisora CondoOS |
| Ver pedidos | quem vê o condomínio |

## 7. Telas

- **Celular do síndico:** "Pedir documentos" a partir de um passo do Hoje, de um aviso de C8 ou de um assunto. Formulário curto, autorização, cartão com o link, o texto e o botão "Compartilhar" (a partilha nativa do celular). Lista "Pedidos" com o progresso.
- **Página pública** `/enviar/[token]`: celular primeiro, com o Design System. Mostra condomínio, itens, prazo e envio com o resultado de cada arquivo (recebido, recusado e por quê, já recebido antes).
- **Desktop da equipe:** pedidos por condomínio na Carteira ou em Pendências.

## 8. Testes previstos

- Fluxo completo com síndico e administradora simulados.
- Link inválido, vencido e revogado respondem 404.
- Isolamento: o token de A nunca grava em B.
- O link só aceita envio, sem listar nem baixar.
- Limite de arquivos.
- Triagem: PDF com JavaScript, PDF criptografado, imagem regravada, ZIP recusado.
- Duplicidade.
- Item atendido automaticamente pela C8.
- Revogação no meio do envio.
- Kill switch.
- Histórico só de inclusão.
- E2E no celular (síndico) e na página pública.

## 9. Decisões que preciso

1. **Aprovar a migração 0021** como descrita: três tabelas, `origin = 'pedido'` e `document.delegation_request_id`.
2. **Triagem sem antivírus de assinatura no piloto** (seção 4), aplicada a todos os envios. Ou prefere esperar uma solução de antivírus antes de abrir o link?
3. **Destinatário sem contato guardado** (só nome e papel, porque quem envia é o síndico). Ou quer guardar o e-mail para uso futuro?
4. **Validade padrão do link de 7 dias e 30 arquivos.** Ajusto se preferir outros valores.
