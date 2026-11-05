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

## Marco 2 — Ingestão e extração

**D24 — Cliente único de LLM** (`app/llm/client.py`). Toda chamada passa por ele:
- saída estruturada com `output_config.format` (JSON Schema estrito gerado do Pydantic e validado de novo do nosso lado);
- cache do system prompt;
- timeout de 120 s e 3 tentativas;
- uma linha em `llm_calls` por chamada real, com tokens, cache, custo estimado e latência;
- teto de custo por condomínio por mês (`LLM_MONTHLY_BUDGET_USD_PER_CONDOMINIUM`, padrão US$ 40).

Para Sonnet 5.5 e Opus 5.5, o fallback server-side de recusa (`fallbacks: "default"`) fica ligado. Modos: `live`, `record`, `replay` e `off`; sem chave, o padrão é `replay`. Respostas gravadas ficam em `api/tests/fixtures/llm/`. Os preços em `app/llm/pricing.py` servem só para a métrica interna; a fatura é a fonte de verdade.

**D25 — Ordem de confiança e regra de confiança por campo.**
- Fontes: XML fiscal e códigos com dígito verificador válido têm confiança 1,0. A IA usa a autoavaliação dela. As heurísticas de texto ficam em 0,75. Um CNPJ único e válido no texto fica em 0,95.
- A nota final é o menor valor entre a fonte e as validações: dígito verificador, CNPJ do tomador igual ao do condomínio, fornecedor diferente do condomínio, data plausível e soma serviços − retenções = líquido.
- Campo obrigatório abaixo de 0,9 manda o documento para a fila de exceções.
- Num documento automático, campo opcional abaixo de 0,9 é descartado. Num documento que vai para a fila, ele fica como sugestão para o analista.
- Documento revisado por pessoa nunca é reprocessado.

**D26 — Mínimo de dados à Anthropic.** Quando o documento tem camada de texto boa, só o texto é enviado. O arquivo (PDF ou imagem) vai apenas quando não há texto utilizável.

**D27 — Docling só no worker.** O extra `docling` instala o torch de CPU (índice do PyTorch). Os modelos são baixados no build da imagem (`app.extraction.warmup`) e o worker roda com `HF_HUB_OFFLINE=1`. A imagem do worker tem cerca de 4,0 GB; a da API, 558 MB. Sem Docling, o pypdfium2 lê só PDFs digitais.

Licenças na árvore do Docling: tudo MIT, BSD ou Apache, exceto `certifi` e `tqdm` (MPL-2.0). A MPL é copyleft por arquivo e só obriga a abrir mudanças nesses próprios arquivos; usamos os dois sem modificação. O `certifi` já vinha antes pelo httpx.

**D28 — CNAB.** Leitura própria e extensível por banco (`@register(layout, banco)`).
- 240 FEBRABAN para Itaú, Bradesco e BB: pagamentos com segmentos A/B e J/J-52 (débitos confirmados com ocorrência "00") e cobrança com segmentos T/U (liquidações 06/17, como créditos).
- 400 cobrança para os três bancos, com tabela de posições por banco.
- Arquivo com CNPJ de outro titular é recusado inteiro.

**Limite:** as posições seguem os manuais e o `brcobranca`, mas não foram conferidas com arquivos reais de banco (a regra é nunca usar dado real). Antes do piloto, é preciso validar com um retorno real anonimizado de cada banco.

**D29 — Fotos HEIC recusadas** com instrução para enviar em JPEG. O iPhone converte para JPEG no upload pelo navegador na maioria dos casos.

**D30 — Caixa de e-mail.** `FolderEmailProvider` lê `.eml` de uma pasta (`INBOUND_EMAIL_DIR`) e só confirma o recebimento depois do commit. O endereço é `<slug>@ingest.condoos.local`. Não há lista de remetentes permitidos no MVP: qualquer remetente coloca documentos na fila, mas eles passam pelas mesmas validações. Com o provedor real, acrescentar verificação SPF/DKIM.

**D31 — Extrato em PDF não é importado**: vai para a fila pedindo OFX ou CSV.

**D32 — Migrações não importam listas do código.** A 0002 importava `RLS_TABLES` dos modelos e quebrou quando a 0003 acrescentou uma tabela. Agora cada migração congela suas listas, e um teste garante que toda tabela em `RLS_TABLES` tem a política no banco.

**D33 — Dado de treino.** `extraction_correction` grava uma linha por campo corrigido (valor extraído, valor corrigido, confiança e fonte), inclusive troca de tipo do documento (`_doc_type`). Tem RLS.

**D34 — Fator de vencimento do boleto.** O fator reiniciou em 1000 no dia 22/02/2025. Os dois ciclos são calculados e fica a data mais próxima da data de referência.

**D35 — Valores lidos por OCR.** "R$ 8.364.18" (ponto no lugar da vírgula) é lido como 8364,18: o último ponto seguido de 2 dígitos é decimal.

**D36 — CNPJ no texto.** Só conta como CNPJ o número formatado ou o que vem logo após o rótulo "CNPJ". Sequências soltas de 14 dígitos aparecem dentro da linha digitável e, 1 vez em 100, passam no dígito verificador.

**D37 — Acurácia sem chave de API** (`docs/extraction_accuracy.md`, Docling e modo `replay`):
- 12 de 30 documentos sem revisão (XMLs, boletos com linha digitável e uma foto de boleto);
- 29 de 30 com o tipo correto;
- **0 documentos automáticos com dado divergente**.

Notas fiscais em PDF, recibos, contratos e fotos ruins dependem do LLM. A meta de 90% sem revisão só pode ser medida com a chave: `LLM_MODE=record uv run python -m corpus.accuracy`.

## Marco 3 — Enriquecimento, casamento e regras

**D38 — BrasilAPI.** O formato da resposta foi conferido no OpenAPI oficial (`cnpj.json` do repositório BrasilAPI).
- Situação em `descricao_situacao_cadastral` e `data_situacao_cadastral`; CNAE em `cnae_fiscal` e `cnaes_secundarios`; sócios em `qsa`.
- 404: CNPJ inexistente. Os dados que já existiam são mantidos e o problema fica registrado (`enrichment_error`).
- 503, 429 e 5xx: até 4 tentativas com espera exponencial, respeitando `Retry-After`. Depois disso, o job falha e a fila tenta de novo mais tarde, sem gravar no cache.
- Cache de 30 dias por fornecedor. O CPF do sócio fica só mascarado; sócio pessoa jurídica guarda o CNPJ, que é público.
- `SUPPLIER_PROVIDER=offline` nunca chama a API (útil nos testes).
- Os CNPJs fictícios do seed não existem na Receita: os fornecedores do seed vêm marcados como `enrichment_source="seed"`, já enriquecidos.

**D39 — Índices reais.** As séries do SGS do Banco Central são 433 (IPCA), 189 (IGP-M) e 188 (INPC). Os códigos foram confirmados por valores históricos (IPCA jan/2023 = 0,53%; INPC = 0,46%), porque o endpoint de metadados não responde. As séries de jan/2020 a out/2026 estão em `app/seed/fixtures/bcb_indices.json`; são estatísticas públicas, não dados de cliente. O seed usa esses valores e a mesma função das regras (`rules/contracts.py`) para calcular os reajustes, então os casos negativos batem exatamente. O worker atualiza os índices uma vez por dia.

**D40 — Despesa e documentos.** A tabela `expense_document` liga uma despesa à nota, ao boleto e ao recibo.
- A nota cria a despesa, ou se junta a uma já existente com o mesmo fornecedor e número de nota.
- O boleto se junta à única despesa compatível (mesmo fornecedor, valor ± R$ 0,01, data compatível). Sem nenhuma, cria a despesa; com mais de uma, vai para a fila.
- O valor da despesa é o líquido da NFS-e: as retenções são pagas à parte, como tributo.

**D41 — Casamento ambíguo.** A tabela `match_issue` (com RLS) guarda os casos de pagamento, contrato ou boleto ambíguos. Eles aparecem na fila de exceções com a ação "Resolver"; quem resolve escolhe a opção, inclusive "nenhuma". O sistema nunca escolhe ao acaso.

**D42 — Ajustes na lógica das regras.** Detalhes em `docs/rules.md`.
- R01 exige a mesma competência, para contratos mensais não virarem duplicidade.
- R02 não julga o mês de reajuste (é do R03), evitando contar a mesma diferença duas vezes.
- R04 tem uma etapa determinística antes de chamar a IA.
- R07 usa a tabela CNAE para categorias mapeadas e a IA só nas demais.
- R11 exclui despesas de contrato e mede o excesso.
- R12 isenta contratos e contas de consumo (configurável).
- R09 ignora tarifas e movimentações entre contas próprias.

**D43 — Sem IA, as regras assistidas ficam "não avaliadas".** No seed, o caso positivo do R04 (pintura no contrato de limpeza) só aparece com IA. O teste de aceite cobre os dois cenários: com respostas de modelo simuladas, o R04 é encontrado; sem modelo, é relatado como não avaliado, e todo o resto bate do mesmo jeito.

**D44 — O seed avalia outubro/2026 ao ser carregado** (`python -m app.seed` e `docker compose`), com data de referência 05/11/2026, para a demonstração já ter achados. O mês é a competência aberta. O Resumo do síndico abre no último mês fechado (setembro), como pede o prompt; para ver os achados plantados, escolha outubro.

**D45 — Fluxo dos jobs.**
1. `document.process` → `document.match` (quando o documento sai sem revisão, ou depois da correção humana).
2. Em seguida, `bank.match` e `rules.evaluate` da competência, com 20 s de atraso.
3. Extrato importado → `bank.match` → `rules.evaluate` dos meses que tiveram casamento.

O motor é idempotente, então reavaliar não duplica achados.

## Marco 4 — Achados, decisões e telas (Design System v1.0)

**D46 — O Design System v1.0 é a referência visual.** O Marcio forneceu o `CondoOS_Design_System_v1.0.md` com o pedido de refatoração. Diagnóstico, matriz e plano estão em `docs/ui-audit.md`. Os conflitos foram resolvidos assim:
- tema escuro em vez do claro dos mockups, mantendo a estrutura dos mockups;
- abas inferiores mantidas no síndico, em vez do drawer do DS, porque são fluxo exigido pelo prompt original;
- vocabulário do domínio atual ("achados"), sem kanban nem KPIs de economia.

**D47 — Ajustes de contraste (WCAG AA), conferidos por script.**
- `text.muted` passou de #8E98A5 (4,17 sobre os cartões) para #A6AEB8 (≥ 4,5 em todas as superfícies).
- Novo token `border.control` (#797F85, 3:1) para contorno de campos e controles; `border.subtle` (1,38) fica só nas divisórias.
- `status.danger` não é usado em texto sobre `surface.elevated` (3,85).

**D48 — Transições de status do achado** (`app/findings/decisions.py`).
- Síndico: confirmar, contestar (comentário obrigatório) e ignorar, só em achados visíveis ao corpo diretivo.
- Gerente: validar e descartar (comentário obrigatório) os graves; reabrir decididos ou descartados. Um descartado reaberto volta para validação; os demais voltam a "publicado".
- Toda ação gera uma linha em `decision` (só inclusão) e outra em `audit_log`.
- O endpoint devolve as ações permitidas para o papel, e a interface mostra só essas.

**D49 — Explicações pela IA com validação numérica** (`app/findings/explain.py`).
- A IA reescreve título e explicação; o código extrai todo número do texto e exige que ele exista nos dados da regra, nas evidências, no CNPJ ou na competência. Um valor exibido com k casas tem de bater com um valor permitido arredondado a k casas.
- Se falhar, a IA tem uma segunda tentativa com o motivo da recusa; se falhar de novo, fica o texto da regra. Palavras proibidas também derrubam o texto.
- Graves usam o modelo de raciocínio; os demais, o de extração.
- O texto da IA é mantido enquanto os números da regra não mudam (`finding.explanation_source`, migração 0005).
- Os textos determinísticos das 12 regras passam pela mesma validação. Ela encontrou três números sem origem nos dados (CNPJ formatado; "12 meses" em R03 e R08), que entraram nos dados das regras.

**D50 — Valor em risco no Resumo.** Soma os achados do mês que não foram ignorados nem descartados. A Carteira soma os abertos (aguardando validação, publicados e contestados).

**D51 — Testes E2E em série** (`workers: 1`). Vários testes entram como o mesmo usuário pela caixa compartilhada do Mailpit; em paralelo, um pegava o link de uso único do outro. O teste "gerente valida achado grave" usa um dos 3 graves do seed e, quando não sobra nenhum, é pulado com a instrução `make reset && make up`.
