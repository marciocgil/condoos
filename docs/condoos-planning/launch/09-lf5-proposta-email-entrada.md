# Launch LF5 — proposta: e-mail de entrada real (LB-050, LB-051)

Data: 08/11/2026. **Aprovada pelo Marcio em 08/11/2026 (opção A, endereço com parte aleatória, migração 0022) e implementada com o bucket simulado (D101).** Ainda não há domínio; a configuração real está em `docs/deploy.md`, seção 7. Detalha LB-050 (provedor real com mock nos testes) e LB-051 (saúde do canal) de `05-backlog.md`; LB-052..055 ficam para depois.

## 1. Problema

Cada condomínio já tem um endereço `<slug>@<INGEST_EMAIL_DOMAIN>`, mas só existe o provedor de pasta (`FolderEmailProvider`): os `.eml` são lidos de `data/inbound-email/`, o que só funciona localmente. No piloto, a administradora e os fornecedores precisam mandar notas e boletos por e-mail para um endereço real. O síndico também precisa saber se o canal está funcionando (último e-mail recebido, último documento, recusas).

O código já tem o ponto de extensão (`InboundEmailProvider` com `fetch` e `ack`) e o caminho do anexo até o documento (`ingest_file`, triagem, extração). Falta o provedor real, uma identificação mais segura do endereço e a saúde do canal.

## 2. Opções de provedor

Preços de 08/11/2026, conferidos nas páginas dos provedores; confirmar antes de contratar.

| | **A. Amazon SES em São Paulo → S3** (recomendada) | B. Postmark (webhook) | C. Cloudflare Email Routing + Worker | D. Caixa IMAP (Google Workspace, Zoho…) |
|---|---|---|---|---|
| Como chega | O SES recebe e grava o `.eml` num bucket S3 em São Paulo; o worker lê o bucket | O Postmark faz POST de um JSON com os anexos numa rota pública nossa | Um Worker (JavaScript, na Cloudflare) recebe e repassa à nossa API | O worker lê uma caixa por IMAP |
| Custo do piloto | US$ 0,10 por 1.000 e-mails + US$ 0,09 por 1.000 blocos de 256 KB: **menos de US$ 1/mês** | US$ 16,50/mês (plano Pro; o Basic não tem entrada) | Grátis (Workers Free; US$ 5/mês no pago, se faltar memória) | Mensalidade por caixa |
| Onde os dados passam | **Brasil** (região sa-east-1) | EUA | Rede global da Cloudflare | Depende do provedor |
| Rota pública nova | Não | Sim (webhook com senha) | Sim (o Worker chama a API) | Não |
| Código novo | Leitor de S3 em Python (já usamos S3) | Rota de webhook | Outro runtime (JavaScript) para manter | Cliente IMAP |
| Limite de tamanho | 40 MB por mensagem | 35 MB | 25 MB | Do provedor |
| O que exige de você | Conta AWS; apontar o MX do subdomínio para o SES | Conta Postmark; MX do subdomínio | Domínio no DNS da Cloudflare | Caixa e senha de app |

**Por que A:** os dados ficam no Brasil (bom para a LGPD e para o contrato de operador, item 22 de `docs/lgpd.md`), o custo é quase zero, não abre nenhuma rota pública nova e reaproveita o que já existe: o `.eml` cai no S3 e passa pelo mesmo `parse_eml` do provedor de pasta. O SES também pode marcar spam e vírus no recebimento e recusar o que vier marcado, o que soma à nossa triagem de arquivos. Isso deve ser confirmado ao configurar.

## 3. Fluxo com a opção A

1. A administradora manda o e-mail para `acacias-7k3q@entrada.<seu-dominio>`.
2. O SES (São Paulo) verifica o destinatário, recusa spam e vírus marcados e grava a mensagem em `s3://<bucket-entrada>/inbound/<id>`.
3. O worker lê o prefixo a cada 30 s, como faz hoje com a pasta. Para cada mensagem, acha o condomínio pelo endereço e manda cada anexo para `ingest_file(origin=email)`, com triagem, deduplicação por hash e extração. Depois move o arquivo para `processed/` ou `rejected/`.
4. Destinatário desconhecido, sem anexo ou com todos os anexos recusados: nada entra em condomínio nenhum; fica só o registro da recusa (seção 5).
5. O bucket de entrada apaga mensagens processadas depois de 30 dias. O documento aceito fica no bucket normal, com a retenção de sempre.

Nada é enviado de volta: o sistema não responde ao remetente. Uma resposta automática seria envio de e-mail, que continua fora (Q-L02).

## 4. Endereço com parte aleatória

Hoje o endereço é só o slug (`jardim-das-acacias@…`), fácil de adivinhar: qualquer pessoa conseguiria jogar arquivos num condomínio. Proposta: o endereço passa a ter um sufixo aleatório (`acacias-7k3q@…`), mostrado em Configurações e no Hoje. O síndico pode **trocar o endereço** se ele vazar; o antigo para de funcionar. O endereço por slug continua valendo só no ambiente local.

## 5. Saúde do canal (LB-051) e migração 0022

Uma tabela nova, toda aditiva:

| Tabela | Conteúdo | Observações |
|---|---|---|
| `inbound_message` (RLS quando há condomínio) | condomínio (nulo se o destinatário for desconhecido), recebida em, **domínio** do remetente (não o endereço completo), quantos anexos, quantos documentos criados, quantos duplicados, quantos recusados e por quê, estado (`processada`, `recusada`, `falhou`) e o `Message-ID` em hash, para não processar duas vezes | Minimização: nem assunto nem corpo são guardados; só ids e contagens. Só inclusão. |
| `condominium.inbound_token` | a parte aleatória do endereço; trocar gera outra | Único |

Com isso, Configurações e a prontidão C8 mostram: **último e-mail recebido, último documento criado por e-mail, recusas nos últimos 30 dias e "nenhum e-mail há N dias"** (alerta, não achado). A volta da migração apaga a tabela e a coluna; os documentos ficam.

## 6. Testes previstos

- Provedor S3 com bucket em memória (o mesmo armazenamento dos testes): mensagem válida vira documento; mesma mensagem duas vezes não duplica; destinatário desconhecido não grava em condomínio nenhum; anexo recusado pela triagem fica registrado.
- Endereço antigo para de funcionar depois da troca; o token de A nunca grava em B.
- Saúde do canal: último recebido, recusas e "sem e-mail há N dias".
- Kill switch: pausar a entrada por e-mail de um condomínio (`automation_pause`) deixa a mensagem esperando, sem perder.
- E2E: Configurações mostra o endereço, a troca e a saúde do canal.

## 7. O que preciso de você

1. **Provedor:** opção A (SES em São Paulo → S3)? Ou outra?
2. **Domínio:** qual domínio vamos usar para a entrada (ex.: `entrada.condoos.com.br`)? Você precisa ter acesso ao DNS dele para criar o registro MX. Se ainda não houver domínio, construo e testo tudo com o mock, e a configuração real fica para quando houver.
3. **Endereço com parte aleatória** e troca pelo síndico (seção 4)?
4. **Migração 0022** como descrita (seção 5)?

A conta AWS e o registro MX ficam com você. Quando chegar a hora, te passo o passo a passo. Até lá, tudo roda com o mock e o provedor de pasta continua no ambiente local.
