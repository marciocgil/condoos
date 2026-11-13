# Implantação do piloto

Guia para subir o CondoOS fora da máquina de desenvolvimento, com dados reais de um condomínio piloto. Para o ambiente local, veja o `README.md`.

## 1. Arquitetura

| Serviço | Imagem | Papel | Escala |
|---|---|---|---|
| `api` | `api/Dockerfile` | FastAPI; aplica migrações ao subir | 1+ réplicas sem estado |
| `worker` | `api/Dockerfile` com `INSTALL_DOCLING=true` (~4 GB) | fila de jobs: extração (Docling), casamento, regras, explicações, índices, retenção | 1+ réplicas (`SKIP LOCKED`) |
| `web` | `web/Dockerfile` | Next.js; o navegador só fala com ele (`/api/*` vai para a API) | 1+ réplicas |
| PostgreSQL 16 + pgvector | gerenciado (RDS, Cloud SQL, Azure) ou `pgvector/pgvector:pg16` | dados, fila de jobs, busca | backup diário + PITR |
| Armazenamento S3 | S3, R2, GCS (interop) ou SeaweedFS | arquivos (`cond/<condominium_id>/...`) | bucket privado, versionamento ligado |
| SMTP | qualquer provedor transacional | link mágico | — |

Saídas de rede necessárias: `api.anthropic.com` (IA, opcional), `brasilapi.com.br` (CNPJ), `api.bcb.gov.br` (índices). Nada mais sai: embeddings e OCR rodam localmente.

## 2. Banco de dados

As migrações criam três papéis. A aplicação **nunca** usa o dono do banco:

| Variável | Papel | Uso |
|---|---|---|
| `DATABASE_ADMIN_URL` | dono (`postgres` ou equivalente) | só migrações, onboarding e seed |
| `DATABASE_URL` | `condoos_app` (sem BYPASSRLS) | API; o RLS filtra por condomínio |
| `DATABASE_WORKER_URL` | `condoos_worker` (BYPASSRLS) | worker |

1. Crie o banco e habilite a extensão `vector` (gerenciados: `CREATE EXTENSION vector;` como dono).
2. Defina senhas fortes em `DB_APP_PASSWORD` e `DB_WORKER_PASSWORD` **antes** da primeira migração (a migração 0002 cria os papéis com elas).
3. `alembic upgrade head` roda sozinho quando a `api` sobe; com várias réplicas, rode-o uma vez como job antes do deploy.
4. `decision` e `audit_log` só aceitam inclusão (sem UPDATE/DELETE para os papéis da aplicação). Não conceda mais do que isso.

## 3. Variáveis de ambiente (produção)

Todas estão em `.env.example`. Segredos vêm do cofre do provedor (Secrets Manager, Key Vault, Doppler), nunca de arquivo no repositório.

| Variável | Produção |
|---|---|
| `ENVIRONMENT` | `production` |
| `SEED_ON_START` | `false` (o seed é só para demonstração) |
| `WEB_BASE_URL` | URL pública HTTPS (links do e-mail apontam para ela) |
| `SESSION_COOKIE_SECURE` | `true` |
| `MAILER`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | provedor SMTP com SPF/DKIM no domínio do remetente |
| `S3_ENDPOINT_URL`, `S3_PUBLIC_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | bucket privado; credencial só com GET/PUT/DELETE no bucket |
| `S3_PRESIGN_TTL_SECONDS` | 300 (padrão) |
| `ANTHROPIC_API_KEY` | chave da organização; sem ela o sistema funciona sem IA (modo `replay`: o que a IA faria vai para a fila de exceções) |
| `LLM_MONTHLY_BUDGET_USD_PER_CONDOMINIUM` | teto mensal por condomínio (padrão 40) |
| `CHAT_MAX_TURNS`, `CHAT_MAX_BUDGET_USD` | limites por pergunta do chat |
| `MAX_UPLOAD_MB` | 20 (padrão) |

## 4. Rede e segurança

- HTTPS terminado no balanceador; só a porta do `web` exposta. A `api` fica na rede interna (o `web` a chama por `API_INTERNAL_URL`).
- `S3_PUBLIC_ENDPOINT_URL` precisa ser alcançável pelo navegador (os links pré-assinados de documento usam esse endereço).
- Cabeçalhos: o `web` roda com `poweredByHeader: false`; acrescente HSTS no balanceador.
- O executável do Claude Code embutido no `claude-agent-sdk` (chat) roda dentro da `api` sem ferramentas nativas e numa pasta temporária vazia (D54). Revise a licença antes do piloto.

## 5. Cadastrar o condomínio piloto

1. Preencha um arquivo como `docs/pilot/onboarding-bosque-dos-ipes.json`: dados do condomínio (CNPJ válido), alçadas, corpo diretivo (com e-mail para quem vai entrar) e a administradora.
2. Rode, com o papel dono:
   ```bash
   docker compose run --rm api python -m app.onboarding /caminho/onboarding.json
   ```
   O comando recusa slug ou CNPJ já cadastrados (nunca sobrescreve) e registra `condominium.onboarded` na auditoria.
3. Usuários da administradora: membros com papel `gerente` ou `analista` na administradora já enxergam o condomínio novo.
4. Envie os **contratos** primeiro (tela "Enviar documentos" ou o e-mail de entrada mostrado em Configurações, `<slug>-<parte aleatória>@<INGEST_EMAIL_DOMAIN>`): cada contrato validado vira contrato do condomínio (D59). Depois, notas, boletos, recibos e o extrato do mês.

## 6. Operação

- **Fila de exceções:** a analista corrige extrações e casamentos ambíguos; o gerente valida achados graves. A competência só fecha com a fila daquele mês vazia.
- **Jobs diários** (agendados pelo worker): índices do BCB e a política de retenção (`retention.purge`, 5 anos para documentos fiscais por padrão; `retention_years` por condomínio).
- **Métricas do piloto:** tela *Métricas do piloto* (precisão, extração automática, tempo de revisão, custo de IA).
- **Logs:** só IDs e contagens; nenhum dado de cliente. Envie stdout dos contêineres para o coletor do provedor.
- **Saúde:** `GET /health` na `api`. O `worker` não expõe HTTP: monitore a tabela `job` (itens `queued` antigos ou `failed` indicam problema).
- **Backup:** PostgreSQL com PITR (7 dias no mínimo) e versionamento no bucket. Teste a restauração antes do piloto.

## 7. E-mail: entrada e saída pela Amazon SES em São Paulo (D101, D103)

Domínio do CondoOS: **`condoos.ia.br`** (DNS no registro.br, **modo avançado** em "Configurar endereçamento" para criar CNAME, TXT e MX; a troca de modo leva umas 3 horas).

**Conta AWS:** a do projeto (não a de gerenciamento da organização). Se o console disser que a ação é negada por uma *service control policy*, na conta de gerenciamento → Organizations → Políticas de controle de serviço → `AdvancedModeRegionRestrictionSecurityControlPolicy`, bloco `RegionFloor`, acrescente `"sa-east-1"` à lista `aws:RequestedRegion`; depois, em Configurações unificadas → Configurações da conta → Regiões visíveis, inclua São Paulo. No SES, plano **Essentials** (sem mensalidade) e etapa 4 do assistente desligada (sem rastreamento de abertura e de links). Uma conta AWS, região **São Paulo (`sa-east-1`)**, faz as duas coisas. Nenhuma caixa de e-mail é necessária: o sistema lê o que chega e as respostas aos pedidos vão para o e-mail do síndico ("responder para").

| Uso | Endereço | DNS |
|---|---|---|
| Saída (link de acesso e pedido de documentos) | `nao-responda@condoos.ia.br` | 3 CNAME do DKIM + TXT do DMARC |
| Entrada (notas e boletos de cada condomínio) | `<slug>-<parte aleatória>@entrada.condoos.ia.br` | MX de `entrada` |

O domínio principal (`condoos.ia.br`) continua livre para uma caixa de pessoas (Google Workspace, Zoho), se um dia houver.

### 7.1 Saída

1. **SES → Identities → Create identity → Domain:** `condoos.ia.br`, com *Easy DKIM* (RSA 2048). A Amazon mostra **3 registros CNAME**.
2. **registro.br → domínio → DNS → Editar zona:** crie os 3 CNAME exatamente como mostrados. Crie também um TXT em `_dmarc` com `v=DMARC1; p=none`. Em até algumas horas, a identidade fica "Verified".
3. **Sair do modo de teste:** SES → *Account dashboard* → *Request production access* (tipo transacional; descreva: "e-mails de acesso e pedidos de documentos aprovados pelo síndico, sem marketing"). Até a liberação, o SES só envia para endereços verificados.
4. **SES → SMTP settings → Create SMTP credentials:** guarde o usuário e a senha (são mostrados uma vez).
5. **Variáveis:** `SMTP_HOST=email-smtp.sa-east-1.amazonaws.com`, `SMTP_PORT=587` (o envio usa STARTTLS sozinho), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM=CondoOS <nao-responda@condoos.ia.br>`.

### 7.2 Entrada

1. **S3 (São Paulo):** bucket privado `condoos-entrada` (acesso público bloqueado, SSE-S3), com duas regras de ciclo de vida que expiram `processed/` e `rejected/` em 30 dias. Política do bucket (só o SES desta conta, em São Paulo, grava, e só em `inbound/`):
   ```json
   {"Version": "2012-10-17", "Statement": [{"Sid": "PermitirSESGravarEntrada", "Effect": "Allow",
     "Principal": {"Service": "ses.amazonaws.com"}, "Action": "s3:PutObject",
     "Resource": "arn:aws:s3:::condoos-entrada/inbound/*",
     "Condition": {"StringEquals": {"AWS:SourceAccount": "<id da conta>"},
                   "StringLike": {"AWS:SourceArn": "arn:aws:ses:sa-east-1:<id da conta>:receipt-rule-set/*"}}}]}
   ```
2. **SES → Identities:** a identidade `condoos.ia.br` já cobre `entrada.condoos.ia.br`.
3. **SES → Email receiving → Rule sets:** crie e **ative** um rule set (`condoos`) com uma regra (`entrada-documentos`) para `entrada.condoos.ia.br`: TLS opcional, *spam and virus scanning* ligado, ação *Deliver to S3 bucket* `condoos-entrada`, prefixo `inbound/`, sem perfil IAM nem SNS. O SES só marca (cabeçalhos `X-SES-Virus-Verdict` e `X-SES-Spam-Verdict`); o CondoOS recusa a mensagem com vírus (`FAIL`) e lê, com uma nota, a marcada como possível spam.
4. **registro.br:** registro **MX** em `entrada` com prioridade 10 apontando para `inbound-smtp.sa-east-1.amazonaws.com`.
5. **IAM → Users:** usuário `condoos-worker` só com `s3:ListBucket` no bucket e `s3:GetObject`, `s3:PutObject` e `s3:DeleteObject` em `inbound/*`, `processed/*` e `rejected/*`. Crie uma *access key*.
6. **Variáveis do worker:** `INGEST_EMAIL_DOMAIN=entrada.condoos.ia.br`, `INBOUND_EMAIL_PROVIDER=s3`, `INBOUND_EMAIL_S3_BUCKET=condoos-entrada`, `INBOUND_EMAIL_S3_REGION=sa-east-1`, `INBOUND_EMAIL_S3_ACCESS_KEY_ID`, `INBOUND_EMAIL_S3_SECRET_ACCESS_KEY`. Em produção, o endereço sem a parte aleatória é recusado.

### 7.3 Testar antes da hospedagem (no docker local)

Com as variáveis de 7.1 e 7.2 no `.env` da raiz (nunca commitado), `make up` passa a enviar pela Amazon e a ler o bucket real. Os links dos e-mails apontam para `WEB_BASE_URL` (`http://localhost:3000`), então só abrem no próprio computador. Para voltar ao Mailpit, apague essas linhas do `.env` e rode `make up` de novo.

- **Saída:** peça o link de acesso com um e-mail seu cadastrado (ou mande um pedido de documentos para o seu e-mail). Ele deve chegar na caixa de entrada, não no spam.
- **Entrada:** mande, de qualquer e-mail, um PDF para o endereço de Ajustes. Em até 30 s, ele aparece em "E-mail de entrada" como processado.

## 8. Verificação de aceite

Num ambiente de homologação com o seed:

```bash
make reset && make up
make test && make e2e
make pilot          # condomínio fictício do upload ao relatório, cronometrado (< 15 min)
make chat-eval      # com ANTHROPIC_API_KEY: avaliação do chat (≥ 90%, zero vazamento)
```

Checklist de privacidade: `docs/lgpd.md`.

## 9. Piloto numa VPS da Hostinger (D106)

Escolha do piloto (`docs/proposta-hospedagem.md`, seção 7): **VPS KVM 4 da Hostinger** (4 vCPU, 16 GB, Ubuntu 26.04 LTS, data center no Brasil) com tudo numa máquina (`docker-compose.prod.yml`: PostgreSQL, `api`, `worker`, `web` e **Caddy**, que tira o certificado HTTPS sozinho). Ficam na AWS São Paulo: e-mail (seção 7), **documentos** (bucket `condoos-documentos`) e o **backup diário cifrado** do banco (`backups/` no mesmo bucket). Servidor: `187.53.98.14`; endereço: `https://app.condoos.ia.br`.

Arquivos: `docker-compose.prod.yml`, `deploy/Caddyfile`, `deploy/.env.production.example`, `deploy/setup-server.sh`, `deploy/backup.sh`, `deploy/restore.sh`. O `deploy/.env.production` (com as senhas) só existe no servidor e está no `.gitignore`.

### 9.1 AWS: bucket dos documentos e usuário da aplicação

1. **S3 → Criar bucket** em `sa-east-1`: nome `condoos-documentos`, *Bloquear todo o acesso público* ligado, **versionamento ativado**, criptografia padrão (SSE-S3).
2. **Gerenciamento → Regra de ciclo de vida** `apagar-backups`: prefixo `backups/`, *Expirar versões atuais* em 30 dias e *Excluir permanentemente versões não atuais* em 1 dia.
3. **IAM → Usuários → Criar** `condoos-app` (sem acesso ao console). Política em linha:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {"Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::condoos-documentos"},
       {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
        "Resource": "arn:aws:s3:::condoos-documentos/*"}
     ]
   }
   ```
   Crie a chave de acesso (*Aplicação executada fora da AWS*) e guarde-a no gerenciador de senhas. Ela entra em `S3_ACCESS_KEY_ID` e `S3_SECRET_ACCESS_KEY`. A entrada de e-mail continua com a chave do `condoos-worker`.

### 9.2 DNS

No registro.br, zona `condoos.ia.br`: registro **A** `app` → `187.53.98.14`. Confira com `dig +short app.condoos.ia.br` antes do passo 9.5 (o Caddy só tira o certificado com o nome apontando para o servidor).

### 9.3 Preparar o servidor (uma vez)

Do Mac, na pasta do projeto:

```bash
scp deploy/setup-server.sh root@187.53.98.14:
ssh root@187.53.98.14 'bash setup-server.sh'
```

O script atualiza o sistema e liga as atualizações automáticas de segurança, abre no firewall só SSH, 80 e 443, instala o Docker (repositório oficial), cria o usuário `condoos` com a mesma chave SSH do root, desliga senha e login do root por SSH e cria 4 GB de swap. **Antes de fechar a sessão do root, teste em outra janela:** `ssh condoos@187.53.98.14`.

### 9.4 Código e segredos

```bash
ssh condoos@187.53.98.14
git clone https://github.com/marciocgil/condoos.git && cd condoos
git checkout claude/exciting-gauss-d4lrhc
cp deploy/.env.production.example deploy/.env.production && chmod 600 deploy/.env.production
openssl rand -hex 24      # uma vez para cada senha
nano deploy/.env.production
```

Preencha direto no servidor (nunca por chat ou e-mail). Guarde `BACKUP_PASSPHRASE` também no gerenciador de senhas: sem ela nenhum backup volta.

### 9.5 Subir

```bash
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production ps
curl -s https://app.condoos.ia.br/api/health
```

A primeira montagem do `worker` (Docling) leva uns 15 minutos. A `api` aplica as migrações ao subir; o seed fica desligado.

### 9.6 Primeiro acesso

O banco nasce vazio. Cadastre a pessoa e dê o papel de Admin CondoOS (papel dono do banco):

```bash
C="docker compose -f docker-compose.prod.yml --env-file deploy/.env.production"
$C exec api python -m app.platform add-person <seu-email> "<seu nome>"
$C exec api python -m app.platform grant-role <seu-email> condoos_admin "Implantação do piloto"
```

Entre em `https://app.condoos.ia.br` com o link de acesso. O condomínio piloto é cadastrado pela Carteira ("Novo condomínio"), e o Admin fica atribuído a ele; ou por `app.onboarding` (seção 5). **Dados reais só depois dos itens da seção 5 de `docs/proposta-hospedagem.md`.**

### 9.7 Backup e restauração

```bash
chmod +x deploy/backup.sh deploy/restore.sh
deploy/backup.sh                          # primeiro backup, na mão
crontab -e                                # acrescente a linha abaixo
30 3 * * * /home/condoos/condoos/deploy/backup.sh >> /home/condoos/backup.log 2>&1
```

Restaurar (apaga o banco atual e volta o backup escolhido; pede para digitar RESTAURAR):

```bash
deploy/restore.sh condoos-AAAAMMDDTHHMMSSZ.sql.gz.enc
```

O teste de restauração é item obrigatório antes do piloto: faça um backup, cadastre algo, restaure e confira que o cadastro sumiu.

### 9.8 Atualizar

```bash
cd ~/condoos && git pull
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production up -d --build
```

Faça um `deploy/backup.sh` antes de atualizar quando houver migração nova.

### 9.9 Teste de fumaça com dados fictícios (antes do primeiro dado real)

Feito em 09/11/2026: leitura (Docling e IA) dos 3 tipos, e-mail de entrada e chat funcionando em produção. Confere em produção a leitura de documentos (Docling e IA), o chat e o e-mail de entrada, e depois apaga tudo pela restauração.

1. `deploy/backup.sh` e anote o nome do arquivo.
2. Suba com a consulta de CNPJ desligada (os documentos do corpus têm CNPJ inventado, que pode existir de verdade):
   ```bash
   SUPPLIER_PROVIDER=offline docker compose -f docker-compose.prod.yml --env-file deploy/.env.production up -d api worker
   ```
3. No site: Carteira → Novo condomínio com dados fictícios e o **CNPJ 49.788.750/0001-69** (o do condomínio do corpus; com outro CNPJ, os documentos vão todos para a fila por "CNPJ do tomador não é o do condomínio", o que também é um resultado válido); envie `api/tests/fixtures/corpus/01_nfse.pdf`, `20_contrato.pdf` e `26_foto_nfse.jpg`; espere "Lido"; pergunte algo no chat; mande um e-mail com um desses anexos para o endereço de entrada mostrado em Ajustes.
4. Restaure o backup do passo 1 (`deploy/restore.sh <nome>`): o banco volta ao estado anterior e os serviços sobem de novo com a consulta de CNPJ ligada.
5. No console do S3, apague a pasta `cond/<id do condomínio de teste>/` do bucket `condoos-documentos` (arquivos sem registro no banco).

Para o percurso completo (cadastro, acesso da síndica, pedido à administradora, envio pelo link, fila de exceções e resultados), siga `docs/pilot/teste-ponta-a-ponta.md`, que usa a mesma preparação e a mesma limpeza.

### 9.10 Zerar os dados para um novo teste do zero (D131)

Apaga condomínios, administradoras, fornecedores, documentos (banco e arquivos em `cond/` no S3), análises, auditoria, assuntos, pedidos e a trilha. **Ficam:** as contas das pessoas (sem acesso a nada até novo convite), os papéis da equipe CondoOS (seu Admin continua), as sessões, os índices do BCB e as versões dos prompts dos agentes. Faz o backup cifrado antes; a trilha nova começa com uma linha `platform.data_reset`.

```bash
cd ~/condoos && git pull && deploy/reset.sh
```

O script pede para digitar o endereço do site (`app.condoos.ia.br`); qualquer outra coisa cancela sem mexer em nada. Depois: Carteira → Novo condomínio, ou `/implantar` (quem implanta vira o síndico do condomínio criado).

**Para voltar atrás:** `deploy/restore.sh <nome do backup feito pelo script>` restaura o banco; os arquivos apagados no S3 voltam pelo versionamento do bucket (console: mostrar versões, apagar o marcador de exclusão). **Recomendado** (uma vez, no console do S3): regra de ciclo de vida `apagar-versoes-documentos`, prefixo `cond/`, *Excluir permanentemente versões não atuais* em 30 dias. Sem ela, versões antigas dos documentos apagados (pelo reset ou pela retenção) ficam no bucket indefinidamente.
