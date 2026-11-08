# Launch LF5 — proposta: o CondoOS envia por e-mail o pedido de documentos (LB-053)

Data: 08/11/2026. **Aprovada pelo Marcio em 08/11/2026 (as 5 decisões) e implementada (D103).**

## 1. O que muda e por que isto pede decisão

Hoje o CondoOS gera o link e o texto do pedido, e **o síndico envia** pelo canal dele (Q-L02, D89). O sistema não manda nada para fora (D83, Plano D-04: "só notificações internas"). O Marcio pediu que o CondoOS passe a enviar o e-mail do pedido.

Este seria o **primeiro envio externo do sistema**. Por isso a proposta mantém as regras de D83 (política que nega por padrão, aprovação da versão exata, conferência de novo antes de executar, kill switch) e abre uma exceção estreita: **um único tipo de ação**, só o e-mail de pedido de documentos, sempre com aprovação do síndico. Todos os outros tipos continuam sem enviar nada.

Registro: divergência **DL-07** (Q-L02 e Plano D-04 × envio pelo sistema) em `docs/03-decisions-register.md`.

## 2. Fluxo

1. No pedido (já autorizado), aparece a opção **"Enviar por e-mail pelo CondoOS"**, ao lado de "Copiar texto" e "Compartilhar".
2. O síndico informa **um** e-mail de destino e, se quiser, um recado curto (até 500 caracteres). O resto do texto é fixo: condomínio, o que se pede, prazo e o link.
3. A tela mostra o **e-mail exatamente como vai sair** (remetente, responder para, assunto, corpo). O síndico clica em "Aprovar e enviar". A aprovação vale para essa versão (hash, como em D83). Se a equipe CondoOS preparou o envio, ele fica esperando a aprovação do síndico.
4. O worker confere tudo de novo: aprovação válida, conteúdo igual ao aprovado, pedido aberto, limites e pausa. Só então gera o link e envia pelo provedor SMTP (o mesmo do link mágico).
5. O pedido registra **"e-mail aceito pelo servidor em <data e hora>"**. Isso **não é entrega**: o sistema nunca diz "entregue" nem "lido". Se o servidor recusar, o sistema tenta 3 vezes e depois mostra "envio falhou" ao síndico, com o motivo.
6. "Já enviei" (declarado) continua existindo para quem preferir mandar pelo WhatsApp.

## 3. O link no e-mail

O token do link nunca é guardado (D95: só o hash). Se o e-mail aprovado contivesse o link, o token ficaria salvo no conteúdo da ação. Proposta: o conteúdo aprovado leva o lugar do link (`{link}`), e **o próprio envio gera o link**. Como cada pedido tem um link ativo por vez, o link anterior (se o síndico já tinha mandado por WhatsApp) para de valer. A tela avisa isso antes de aprovar.

## 4. Limites contra abuso

- Um destinatário por envio, sem cópia e sem anexo.
- Texto fixo do sistema mais o recado do síndico. Isso impede que o CondoOS vire um disparador de e-mails com qualquer conteúdo.
- No máximo 1 envio por pedido a cada 24 h e 3 no total. No máximo 20 envios por condomínio por dia.
- Kill switch novo: `pedido_documento.enviar_email`. A pausa geral de ações também barra o envio. Pausar depois de aprovado deixa o envio esperando.
- A política nega se o pedido estiver fechado, vencido ou revogado, ou se o síndico não puder aprovar (`APPROVE_IN_CONDO`).

## 5. Remetente e resposta

- **De:** `CondoOS em nome do <Condomínio> <pedidos@<domínio>>`.
- **Responder para:** o e-mail do síndico, para que a resposta vá para ele e nada volte ao CondoOS. Isso mostra o e-mail do síndico ao destinatário; ver a pergunta 2.

## 6. Dados pessoais (LGPD)

- O e-mail do destinatário é dado de terceiro. Ele fica no conteúdo da ação só até o envio. Depois, é **mascarado** (`j***@empresa.com.br`); o hash do endereço completo fica, para a trilha conferir o que foi aprovado.
- O pedido guarda só o domínio do destinatário. Logs só com ids.
- O texto do e-mail não leva valores nem dados financeiros do condomínio, só o que já aparece na página pública do link.

## 7. Modelo (migração 0023, pequena)

| Mudança | Por quê |
|---|---|
| `delegation_event.kind` aceita `email_aprovado`, `email_enviado` e `email_falhou` | Histórico do pedido |
| `outbox_event.receipt` (JSON, opcional) | Recibo do servidor: id da mensagem e hora do aceite |

O tipo de ação é código (`app/policy`), sem tabela nova. A volta apaga a coluna e restringe os tipos de evento de novo (os eventos de e-mail viram `compartilhado`).

## 8. Pré-requisito para envio real

Sem um domínio com SPF e DKIM, o e-mail cai em spam ou é recusado. Até haver domínio (o mesmo da entrada, D101), tudo roda e é testado localmente com o Mailpit. No ambiente sem SMTP configurado, a opção não aparece.

## 9. Testes previstos

- Envio só depois da aprovação da versão exata; conteúdo alterado anula a aprovação.
- O worker confere tudo de novo; pausa deixa esperando; pedido fechado bloqueia.
- O link nasce no envio e o anterior para de valer; o token não fica guardado.
- "Aceito pelo servidor" registrado, nunca "entregue"; falha do SMTP depois de 3 tentativas.
- Limites por pedido e por condomínio. A equipe prepara e não aprova; isolamento entre condomínios.
- O e-mail fica mascarado depois do envio.
- Os outros tipos de ação continuam sem enviar nada (teste de regressão de D83).
- E2E: síndico envia pelo CondoOS e o e-mail chega no Mailpit com o link que funciona.

## 10. Decisões que preciso

1. **Aprovar a exceção:** o CondoOS envia o e-mail do pedido de documentos, só esse tipo, sempre com aprovação do síndico da versão exata (revê Q-L02 e Plano D-04 só para este caso).
2. **Responder para = e-mail do síndico?** (recomendo sim). A alternativa é não ter "responder para", e o destinatário só responde pelo link.
3. **Mascarar o e-mail do destinatário depois do envio?** (recomendo sim). A alternativa é guardar o endereço completo para facilitar o reenvio.
4. **A equipe CondoOS pode preparar o envio para o síndico aprovar?** (recomendo sim)
5. **Migração 0023** como descrita (seção 7).
