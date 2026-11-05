# Decisões técnicas

Registro das escolhas feitas durante a construção do MVP. Cada item diz o que foi decidido, por quê e onde está no código. Decisões D1–D5 foram aprovadas pelo Marcio em 05/11/2026 (respostas às perguntas do plano).

## Aprovadas no plano

**D1 — Embeddings locais para a busca semântica do chat.** Modelo multilíngue local (`intfloat/multilingual-e5-small`, licença MIT, 384 dimensões) rodando no worker. Nenhum trecho de contrato, convenção ou ata sai para um terceiro além da Anthropic, e não há custo por chamada. Custo: imagem do worker ~1 GB maior. Entra no Marco 5 (`document_chunk` com `vector(384)`); a extensão `vector` já é criada na migração 0002.

**D2 — Corpo diretivo separado dos usuários.** Tabela `board_member` (nome completo, cargo `sindico`/`subsindico`/`conselheiro`, mandato, `user_id` opcional). A regra R08 compara os sócios do fornecedor com essa tabela, que inclui quem não tem login. O papel `subsindico` foi acrescentado a `membership`.

**D3 — Administradora opcional.** `condominium.management_company_id` aceita nulo. Um síndico profissional sem administradora recebe o papel `gerente` direto no condomínio (`membership.condominium_id`), com as mesmas permissões que o gerente da administradora tem na carteira. Papéis no nível da administradora só podem ser `gerente` ou `analista` (CHECK no banco).

**D4 — Aprovações registradas.** Tabela `approval` (despesa, quem aprovou, data, documento de origem opcional, observações, quem registrou). Preenchida pelo gerente ou, depois, extraída de atas. É a fonte da regra R12.

**D5 — LLM nos testes: gravar e reproduzir.** O cliente único de LLM (Marco 2) terá um modo de reprodução: as respostas reais são gravadas uma vez em `api/tests/fixtures/llm/` e reproduzidas na suíte normal, que roda sem chave e sem custo. A chave real só é usada nos testes `slow` (acurácia de extração e avaliação do chat).

## Divergências entre o PDF de arquitetura e o prompt

**D6 — Pipeline em jobs determinísticos; Agent SDK só no chat.** O PDF fala do Agent SDK orquestrando as etapas do meio; o prompt pede uma fila de jobs. Seguimos o prompt: cada etapa é um job idempotente (`app/core/jobs.py`) e o Claude Agent SDK fica restrito ao agente "Pergunte ao CondoOS".

**D7 — Peças de licença indefinida ficam fora do produto.** `claude-for-legal`, `financial-services`, `mcp-brasil` e Belvo aparecem no PDF com licença "—" ou não citada. Não entram no produto. Open Finance existe só como interface (`BankDataProvider`); CNAB usa parser próprio com `brcobranca` (MIT) apenas como referência de layout.

**D8 — R05 usa a data do pagamento.** O PDF diz "data do pagamento após o fim da vigência"; o prompt diz "despesa com data posterior". Usaremos a data do débito casado no extrato e, sem casamento, a data de vencimento (Marco 3).

## Infraestrutura e licenças

**D9 — SeaweedFS no lugar do MinIO.** O MinIO é AGPL-3.0 e, desde o fim de 2025, a edição comunitária não publica mais imagens Docker (`minio/minio` não existe mais no Docker Hub). Usamos SeaweedFS 4.50 (Apache-2.0) com o gateway S3, apenas no `docker compose` local. O código fala S3 genérico via boto3; em produção basta apontar `S3_ENDPOINT_URL` para qualquer serviço compatível.

**D10 — asyncpg em vez de psycopg.** O psycopg 3 é LGPL-3.0. O driver é o asyncpg (Apache-2.0) com SQLAlchemy 2 assíncrono.

**D11 — Mailpit para e-mail local.** O link mágico é enviado por SMTP ao Mailpit (MIT), com interface em http://localhost:8025. Em teste, um mailer em memória.

**D12 — Enums como VARCHAR + CHECK.** Mais simples de evoluir em migrações do que enums nativos do PostgreSQL. Valores em `app/db/enums.py`.

## Segurança e multi-tenant

**D13 — Três papéis de banco e Row-Level Security.**
- `condoos_app` (API): sem superusuário e sem `BYPASSRLS`. RLS se aplica sempre.
- `condoos_worker` (worker): `BYPASSRLS`, porque jobs atravessam condomínios.
- dono das tabelas (migrações e seed).

Cada requisição autenticada faz `set_config('app.condominium_ids', ..., true)` com os condomínios acessíveis ao usuário. As tabelas com dados de condomínio têm a política `tenant_isolation`; sem escopo, nenhuma linha aparece. A lista de condomínios acessíveis vem da função `app_accessible_condominium_ids` (SECURITY DEFINER). O código também filtra por `condominium_id` em toda consulta: o RLS é a segunda camada. Senhas dos papéis vêm de `DATABASE_URL` e `DATABASE_WORKER_URL`.

**D14 — `decision` e `audit_log` só aceitam inclusão.** O papel da API não tem `UPDATE` nem `DELETE` nessas tabelas (REVOKE na migração 0002). `decision` ganhou `condominium_id` para ficar sob RLS.

**D15 — 404 para recursos de outro condomínio.** Pedir dados de um condomínio sem acesso devolve 404, não 403, para não revelar que o id existe.

**D16 — Link mágico.** Token aleatório de 256 bits, guardado só como hash SHA-256, válido por 15 minutos, uso único (UPDATE atômico). A página `/auth/verify` consome o token com POST, então leitores de link de e-mail que só fazem GET não o queimam. Limite de 5 links por e-mail por hora. A resposta é a mesma para e-mail cadastrado ou não.

**D17 — Sessões no servidor.** Tabela `user_session` com hash do token, validade de 14 dias e revogação no logout. Cookie `httpOnly`, `SameSite=Lax`, `Secure` configurável. O navegador só fala com o Next.js; `/api/*` é repassado à API (rewrite), então o cookie é do próprio domínio.

**D18 — Commit antes da resposta.** A dependência do banco usa `Depends(get_db, scope="function")` (alias `DbSession`): a transação é confirmada antes de a resposta sair. Com o escopo padrão, o commit podia acontecer depois da resposta, e o teste E2E pegou o caso: o cookie novo chegava ao `/me` antes de a sessão existir no banco (401 intermitente). `tests/test_app_wiring.py` impede a regressão.

## Modelo de dados

**D19 — Ajustes em relação à seção 4 do prompt.**
- `user` → `app_user` (palavra reservada no PostgreSQL). `llm_calls` mantém o nome do prompt.
- `expense.invoice_number`: número da nota, usado pela R01 ("mesmo número de nota pago duas vezes").
- `bank_transaction.external_id` (FITID, nosso número CNAB, hash da linha CSV) com unicidade por condomínio, para a ingestão ser idempotente.
- `finding.dedupe_key` (mesma regra + mesmo objeto = mesmo achado ao reprocessar), `finding.ai_assisted` (R04 e R07) e `finding.supplier_id`.
- `competence`: o mês contábil de cada condomínio, com status `aberta`/`fechada`, chaves dos relatórios e data de publicação.
- `condominium`: `slug` (caixa de e-mail de ingestão), `rule_params` (parâmetros por condomínio), `expense_categories` e `retention_years`.
- Tabelas de autenticação: `magic_link_token` e `user_session`.
- `finding_comment`: comentários de conselheiros e síndicos (o PDF diz que o conselheiro comenta; `decision` não tem essa ação).
- `job.dedupe_key`: idempotência ao enfileirar.

**D20 — Descartar achado grave.** O prompt diz que o gerente pode "descartar com comentário obrigatório", mas as listas de status e de ações não têm essa opção. Acrescentados o status `descartado` e a ação `descartar`. Achados descartados nunca aparecem para o síndico.

**D21 — Dinheiro.** `NUMERIC(14,2)` no banco, `Decimal` no Python, string no JSON da API (sem erro de ponto flutuante). Débitos no extrato são negativos.

## Seed

**D22 — Seed fictício e determinístico.** Semente fixa e último mês fixo (outubro/2026), para os testes não dependerem da data de hoje. São 12 meses (nov/2025 a out/2026); outubro está `aberta` e os demais estão `fechada`. CNPJs têm dígito verificador válido mas são gerados ao acaso. Os reajustes do seed são percentuais fictícios, não valores reais de índice: `index_value` é preenchida a partir do BCB no Marco 3. Os e-mails usam subdomínios de `example.com` (reservado pela RFC 2606); o domínio `.test` é recusado pelo validador de e-mail. Os casos plantados de cada regra entram no Marco 3.

**D23 — Valor em risco da R11.** O prompt diz "demais = valor da despesa", mas a R11 compara o total de uma categoria, não uma despesa. O valor em risco é o excesso sobre o limite (média + σ × desvio), não o gasto inteiro do mês.
