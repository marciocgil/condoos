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

## 7. E-mail de entrada (Amazon SES em São Paulo, D101)

Feito uma vez, quando houver domínio. Nada é respondido ao remetente.

1. **Subdomínio só para entrada**, por exemplo `entrada.seudominio.com.br` (não use o domínio do e-mail da empresa).
2. **Bucket S3 em `sa-east-1`**, privado, só para a entrada (ex.: `condoos-entrada`), com uma regra de ciclo de vida que apaga `processed/` e `rejected/` depois de 30 dias. A política do bucket permite ao serviço SES gravar em `inbound/`.
3. **SES (região São Paulo):** verificar o subdomínio; criar um *receipt rule set* ativo com uma regra para o subdomínio: varredura de spam e vírus ligada, recusar o que vier marcado e entregar ao S3 no prefixo `inbound/`.
4. **DNS:** registro `MX 10 inbound-smtp.sa-east-1.amazonaws.com` no subdomínio.
5. **Credencial do worker:** usuário IAM só com `ListBucket` no bucket e `GetObject`, `PutObject` e `DeleteObject` em `inbound/*`, `processed/*` e `rejected/*`.
6. **Variáveis do worker:** `INGEST_EMAIL_DOMAIN=entrada.seudominio.com.br`, `INBOUND_EMAIL_PROVIDER=s3`, `INBOUND_EMAIL_S3_BUCKET`, `INBOUND_EMAIL_S3_REGION=sa-east-1` e a credencial do passo 5. Em produção, o endereço sem a parte aleatória é recusado.
7. **Teste:** mande um e-mail com um PDF para o endereço de Configurações. Em até 30 s ele aparece em "E-mail de entrada" como processado, e o documento entra na fila de leitura.

## 8. Verificação de aceite

Num ambiente de homologação com o seed:

```bash
make reset && make up
make test && make e2e
make pilot          # condomínio fictício do upload ao relatório, cronometrado (< 15 min)
make chat-eval      # com ANTHROPIC_API_KEY: avaliação do chat (≥ 90%, zero vazamento)
```

Checklist de privacidade: `docs/lgpd.md`.
