# CondoOS

Agente auditor de despesas para condomínios. Ele lê as despesas do mês, confere cada uma contra contrato, cadastro do fornecedor, extrato bancário e histórico, e entrega ao síndico uma lista de achados priorizados por valor em risco, cada um com a evidência anexada. Uma pessoa sempre decide; o sistema nunca move dinheiro.

> MVP em construção. Status por marco em [`CLAUDE.md`](CLAUDE.md). Decisões em [`docs/decisions.md`](docs/decisions.md).

## Subir localmente

Requisitos: Docker com Compose v2.

```bash
cp .env.example .env    # opcional: todos os valores têm padrão de desenvolvimento
make up                 # ou: docker compose up -d --build --wait
```

| Serviço | Endereço |
| --- | --- |
| Aplicação web | http://localhost:3000 |
| API (documentação) | http://localhost:8000/docs |
| E-mails enviados (Mailpit) | http://localhost:8025 |
| Armazenamento S3 (SeaweedFS) | http://localhost:8333 |

Na primeira subida, a API aplica as migrações e carrega um seed **fictício**: a administradora "Atlântida Gestão Condominial", os condomínios "Jardim das Acácias" e "Mirante do Vale", e 12 meses de despesas e extrato.

### Entrar

1. Abra http://localhost:3000/login e digite um dos e-mails abaixo.
2. Abra o e-mail no Mailpit (http://localhost:8025) e clique no link.

| E-mail | Papel |
| --- | --- |
| `ana.sindica@acacias.example.com` | Síndica do Jardim das Acácias |
| `bruno.conselho@acacias.example.com` | Conselheiro do Jardim das Acácias (só leitura) |
| `carla.sindica@mirante.example.com` | Síndica do Mirante do Vale |
| `diego.gerente@atlantida.example.com` | Gerente da administradora (vê a carteira) |
| `elisa.analista@atlantida.example.com` | Analista da administradora |

Cada link vale 15 minutos, serve uma única vez, e cada e-mail pode pedir até 5 links por hora.

## Desenvolvimento

```bash
make install   # dependências do backend (uv) e do frontend (npm)
make test      # testes do backend
make lint      # ruff, black, mypy, eslint, tsc, prettier
make e2e       # testes Playwright contra a stack em execução
```

Os testes do backend precisam de um PostgreSQL 16 com a extensão `pgvector`. Por padrão usam `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres` (mude com `TEST_DATABASE_ADMIN_URL`). A suíte cria o banco `condoos_test` do zero a cada execução.

Para usar o PostgreSQL da própria stack nos testes, suba só o banco numa porta livre:

```bash
POSTGRES_PORT=5433 docker compose up -d postgres
TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/postgres make test
```

## Segurança

- Isolamento entre condomínios em duas camadas: filtro explícito em toda consulta e Row-Level Security no PostgreSQL. A API conecta com um papel sem privilégio de ignorar o RLS.
- `decision` e `audit_log` só aceitam inclusão; o papel da API não pode alterar nem apagar linhas.
- Segredos só por variável de ambiente. Nunca commite o `.env`.
- Todos os dados de exemplo são fictícios.
