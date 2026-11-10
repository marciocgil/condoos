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

## Marco 5 — Chat e relatório

**D52 — Embeddings locais com `paraphrase-multilingual-MiniLM-L12-v2` via fastembed.**
- fastembed (Apache-2.0) roda o modelo em ONNX (onnxruntime, MIT), sem PyTorch na imagem da API. O modelo (Apache-2.0, 384 dimensões, multilíngue) vai embutido nas imagens (`python -m app.chat.warmup`).
- Substitui o e5-small da D1: o MiniLM roda em ONNX pelo fastembed, sem PyTorch na imagem da API, e não exige os prefixos "query:"/"passage:" do e5.
- Tamanho: a imagem da API passou de 0,56 GB para 1,81 GB no Marco 5, somando o executável do Agent SDK (D54), o onnxruntime e o modelo.
- Nenhum texto de documento sai da infraestrutura para gerar embeddings.
- `EMBEDDINGS_ENABLED=false` (testes) deixa a coluna `embedding` nula e a busca fica só por texto.

**D53 — Busca híbrida nos documentos** (`app/chat/search.py`).
- Pontuação = 0,5 × similaridade de cosseno + 0,5 × `ts_rank_cd` do texto completo em português (consulta com OU entre as palavras).
- Só a busca vetorial errou 2 de 3 perguntas de teste ("multa de rescisão da portaria" trazia a cláusula de reajuste de outro contrato); só o texto completo perde paráfrases.
- Indexados: contratos, convenção e atas, em trechos de cerca de 900 caracteres com 150 de sobreposição. O job `document.index` roda após a extração e é idempotente.
- O seed traz convenção, ata e o texto de cada contrato (fictícios), ligados a `contract.source_document_id`.

**D54 — Agente de chat com o Claude Agent SDK** (`app/chat/agent.py`).
- Só as 9 ferramentas de leitura de `app/chat/tools.py`, num servidor MCP no próprio processo. Todas as ferramentas nativas (arquivos, shell, web) desligadas (`tools=[]`), sem configurações de projeto, numa pasta temporária vazia.
- O condomínio não é parâmetro de nenhuma ferramenta: vem da sessão. A transação da pergunta tem o RLS restrito a esse único condomínio, inclusive para o gerente que tem vários.
- Modelo de raciocínio; até `CHAT_MAX_TURNS` turnos e `CHAT_MAX_BUDGET_USD` por pergunta; o custo entra em `llm_calls` (`purpose=chat`) e no orçamento mensal do condomínio.
- Licença: o pacote `claude-agent-sdk` é MIT, mas inclui o executável do Claude Code (cerca de 320 MB), distribuído sob os termos comerciais da Anthropic. É o componente indicado pela especificação; fica registrado para a revisão jurídica antes do piloto.
- Sem chave de API, o chat responde 503 com mensagem em português; o resto do produto funciona.

**D55 — Verificações do chat por código** (`app/chat/service.py`).
- Todo número da resposta tem de aparecer nas saídas das ferramentas daquela pergunta (ou na própria pergunta); inteiros de 0 a 31 são livres (dias, meses, contagens).
- Citações só valem se a ferramenta devolveu aquele `ref` na mesma pergunta; as demais são descartadas.
- Ação sugerida só de uma lista fechada (`abrir_achado`, `ver_contrato`, `ver_despesas`) e apontando para um registro visto.
- Palavras proibidas derrubam a resposta.
- Se a resposta falhar, há uma segunda tentativa com o motivo; se falhar de novo, o usuário recebe "Não consegui confirmar esta resposta…" em vez de números não verificados.
- O histórico é por usuário e condomínio; as 6 últimas mensagens vão como contexto, e os dados são consultados de novo a cada pergunta.

**D56 — Avaliação do chat** (`api/tests/chat_eval/`).
- 33 perguntas sobre o seed, em 8 tipos: fatos, documentos, contexto de tela, papel, outro condomínio, dado inexistente, pedido de escrita e dúvida jurídica.
- Os valores esperados não são fixos no código: cada caso os lê do seed pelas mesmas ferramentas do agente. Um teste rápido garante que todos resolvem.
- O teste ao vivo (`slow`, exige chave) passa pela API, corrige por regras e grava `docs/chat_eval.md`. Aceite: ≥ 90% e nenhum vazamento entre condomínios.

**D57 — Relatórios** (`app/reports/`).
- O relatório é a visão do corpo diretivo: não inclui achados aguardando validação nem descartados.
- PDF com ReportLab (BSD), em layout claro para impressão: o tema escuro do DS é de tela. O rodapé com o aviso de IA vai em toda página (desenhado no canvas) e é conferido por teste em cada página.
- XLSX com openpyxl (MIT): o aviso vai na primeira linha de cada aba e no rodapé de impressão.
- Competência aberta: o download é uma prévia gerada na hora e marcada como tal. Competência fechada: serve o arquivo guardado no fechamento, o que foi enviado ao síndico.

**D58 — Fechamento da competência exige fila vazia daquele condomínio e daquele mês.**
- Entram documentos em revisão, casamentos ambíguos abertos e achados graves aguardando validação.
- O mês de um documento vem da competência, da emissão ou do vencimento extraídos. Documento ou casamento sem mês identificável bloqueia: fechar um mês com pendência que pode ser dele é o erro pior.
- Só o gerente fecha. O fechamento gera PDF e XLSX, guarda em `cond/<id>/reports/`, marca `published_at` (status "Enviado" na Carteira) e registra auditoria. Não reabre pelo sistema.

## Marco 6 — Prontidão para piloto

**D59 — Contrato nasce do documento de contrato.**
- Um documento do tipo contrato, validado (automático ou corrigido pela analista), vira contrato do condomínio: fornecedor pelo CNPJ, valor mensal, índice, mês-base, vigência e escopo.
- Mesmo fornecedor e mesma data de início: liga o documento ao contrato existente em vez de criar outro.
- Contrato em nome de outro CNPJ volta para a fila de extração com o motivo; a analista corrige ou descarta.
- O cadastro do condomínio (`python -m app.onboarding <arquivo.json>`) não recebe contratos: eles chegam como documentos, com evidência. O comando nunca sobrescreve um condomínio existente.
- A competência de um mês é criada quando as regras avaliam esse mês (antes só existia no seed).

**D60 — Métricas internas do piloto** (`app/metrics.py`, tela "Métricas do piloto").
- Precisão = achados cuja última decisão do síndico é "confirmar" ÷ achados com alguma decisão do síndico (confirmar, contestar ou ignorar), pela competência do achado.
- Extração automática = documentos fiscais recebidos (upload ou e-mail) que nunca passaram por revisão manual ÷ documentos fiscais processados, pelo mês de recebimento. Extratos, convenções, atas e o seed ficam fora.
- Tempo de revisão = da publicação do achado (criação; nos graves, a validação do gerente) até a primeira decisão do síndico; mediana em horas.
- Custo de IA = soma de `llm_calls.cost_usd`, em dólares, pela data da chamada.
- Só a administradora vê. O corpo diretivo não vê métricas internas.

**D61 — Achado superado.** Se uma nova avaliação do mês não detecta mais um achado (por exemplo, a nota chegou depois do débito) e nenhuma pessoa decidiu nem comentou nele, ele passa a `superado` (migração 0007): fica registrado e auditado, mas sai da visão do corpo diretivo e do valor em risco. Se a regra voltar a detectá-lo, volta ao status inicial. Regras com algo "não avaliado" (sem IA) não superam achados, porque falta de avaliação não é avaliação negativa. Motivo: na execução do piloto, documentos chegando fora de ordem deixavam achados de R09/R10 já resolvidos pelos dados.

**D62 — Conta de concessionária é documento fiscal (R09).** Energia, água e gás são cobrados por conta (fatura), que é o documento fiscal do serviço. Um débito casado com despesa dessas categorias que tenha a conta anexada não é "pago sem nota". Achado na execução do piloto (falso positivo em água e energia); teste positivo e negativo em `tests/test_rules.py`.

**D63 — Boleto repetido.** A linha digitável identifica a cobrança. Um segundo arquivo do mesmo boleto (por exemplo, a foto do PDF) entra na mesma despesa, em vez de criar uma despesa nova e um falso "pagamento duplicado". Notas repetidas já eram unidas pelo número.

**D64 — Aceite do Marco 6 por script** (`make pilot`, `api/scripts/pilot_run.py`). Cadastra o condomínio fictício "Bosque dos Ipês", gera os 30 documentos do corpus endereçados ao CNPJ dele e um extrato OFX de outubro, e percorre pela API o que as pessoas fariam: envio, correção da fila (com o gabarito do corpus, como uma pessoa lendo o documento), validação dos graves, fechamento e download do relatório. O tempo medido é o do sistema; a leitura humana é instantânea no script. Resultado em `docs/pilot/run.md`.

## Pós-piloto — lacunas de uso real

**D65 — Registro de aprovações (R12).** A administradora (gerente ou analista; permissão `record_approval`) registra quem aprovou a despesa (conselho, assembleia), a data (nunca futura) e uma observação, opcionalmente ligada à ata enviada. O registro é auditado e reavalia o mês com prioridade; o achado R12 em que ninguém agiu vira "superado" (D61). O corpo diretivo não registra a própria aprovação. A tela fica no detalhe do achado R12.

**D66 — Termos aditivos.** Um documento de contrato cujo título (objeto ou início do texto) diz "aditivo" não vira contrato novo: vira um registro em `contract_amendment` (migração 0008, com RLS) ligado ao contrato do mesmo fornecedor. Guarda a data de efeito, o novo valor mensal, o novo fim e o escopo acrescentado.
- O contrato guarda os termos originais; o fim da vigência e o escopo passam a refletir o aditivo.
- R02 e o chat usam o valor do aditivo vigente no mês, e só os reajustes posteriores a ele (o valor do aditivo já inclui os anteriores). As telas de contratos mostram o valor vigente e quantos aditivos há.
- Sem contrato original cadastrado, ou com mais de um possível do mesmo fornecedor, o aditivo volta para a fila com o motivo; nunca é ligado ao acaso.
- Limite conhecido: aditivo só de prazo ainda exige o valor mensal na revisão (repita o valor vigente).

**D67 — Telas de cadastro da administradora** (`app/routers/registry.py`). Só o gerente (permissão `configure`):
- dados do condomínio (nome, endereço, unidades, retenção; o CNPJ não muda);
- corpo diretivo: incluir, editar e remover, com mandato;
- acessos do condomínio: dar acesso por e-mail com papel de síndico, subsíndico ou conselheiro, e remover. Os acessos da administradora aparecem, mas não são removidos por condomínio;
- contratos: cadastrar e editar à mão quando não há documento. Na edição vale o valor original; os aditivos seguem valendo pelas datas deles;
- novo condomínio pela Carteira.

Toda alteração é auditada (ids e nomes de campos, nunca dados de pessoas). Mudanças que afetam regras (corpo diretivo, contratos) reavaliam os meses em aberto com prioridade.

O condomínio novo ainda não está no escopo de RLS da requisição. Por isso é criado numa transação própria com o papel do worker, depois da verificação de que o usuário é gerente da administradora. O comando `app.onboarding` continua existindo para cargas por arquivo.

**D68 — Calibração da leitura de contratos (retorno com documentos reais).**
- **Contrato que cita nota fiscal continua contrato.** Os marcadores de NF-e/NFS-e só valem no cabeçalho do documento (cerca de 1.200 caracteres). Documento com contratante, contratada e "contrato" ou "aditivo" no título, ou com três cláusulas ou mais, é contrato. Antes, a cláusula "mediante apresentação de nota fiscal de serviço" fazia o contrato ser lido como NFS-e.
- **CNPJ da contratada.** Aceita espaços e ruído de OCR nos separadores; o dígito verificador continua obrigatório. Prefere o CNPJ que aparece na qualificação da CONTRATADA, não o de testemunhas ou intervenientes.
- **Início da vigência.** Sem data de início no contrato, vale a data da assinatura (campo novo, lido também da linha "Cidade, 10 de março de 2025").
- **Mês do reajuste.** Sem outro mês no contrato, é o mês do início da vigência, para todo contrato com índice.
- **Prazo indeterminado.** É a opção padrão no formulário; o fim da vigência só é pedido quando houver.
- **Índice "Outro"** (migração 0009), com descrição em texto: IGP-DI, IPC-Fipe, dissídio etc. Índices não acompanhados pelo sistema viram "Outro" com o nome guardado. A R02 avalia o valor até o primeiro reajuste; depois fica "não avaliada" (não adivinha o índice).

**D69 — Filtro por condomínio nas telas da administradora.** Contratos, Fornecedores, Fila de exceções e Métricas ganham o filtro "Condomínio" (Todos ou um). A escolha vai na URL (`?condominio=`) e o menu lateral a leva para as outras telas.
- Fornecedores e Métricas recalculam os totais na API (`condominium_id`) para o condomínio escolhido; não é só um filtro de tela.
- Um id fora da carteira do usuário devolve vazio.
- Novo contrato a partir do filtro já vem com o condomínio escolhido.

**D70 — Cockpit de pendências: faturamento dos contratos e aprovação dos avulsos** (`app/pending.py`, tela "Pendências").
- **Contrato vigente × NF do mês.** Cada contrato tem uma periodicidade de faturamento (migração 0010): mensal por padrão; bimestral, trimestral, semestral, anual ou sob demanda (0, sem faturamento fixo). Um contrato lido de documento com "trimestral" (etc.) no objeto já vem com a periodicidade.
- Nos meses em que a NF é esperada, a situação é:
  - *faturado*: despesa do contrato com número de nota ou NF anexada;
  - *cobrado sem NF*: boleto ou débito sem nota;
  - *sem faturamento*: nada do contrato no mês;
  - *aguardando*: até 10 dias depois do fim do mês, o prazo usual de emissão.
- **Serviço avulso** (despesa sem contrato; energia, água e gás fora, como na R12) fica pendente até ter aprovação registrada. A aprovação pode ser ligada a um documento já enviado: proposta assinada ou orçamento (tipo "outro"), ata ou contrato.
- São pendências de acompanhamento da administradora, não achados: não aparecem para o síndico e não acusam ninguém. A auditoria continua com R09, R10 e R12.
- Filtro por condomínio e pelos últimos 6 meses, com a contagem de pendências por mês.

**D71 — Agenda** (`app/agenda.py`; tela "Agenda" da administradora e do síndico). Uma visão por data do que já existe, sem tabela nova e sem gerar achado:
- **Vencimentos** de cada despesa, com a situação tirada do extrato: pago, vencido sem pagamento ou a vencer.
- **NF prevista dos contratos**, pela periodicidade (D70). O dia vem da mediana do dia de emissão das últimas notas do contrato (dia 1 sem histórico) e é marcado como previsto. O valor é o vigente, com aditivos e reajustes por índice.
- **Reajustes** no mês-base dos contratos com índice ("conferir" depois de chegar o mês).
- **Fim de contrato**: contratos de prazo indeterminado não aparecem.

Telas:
- Administradora: calendário do mês, lista por dia e filtros por condomínio e por tipo. O calendário fica oculto para leitores de tela; a lista por dia é a versão acessível.
- Síndico: "Em atraso" e "Próximos 30 dias", mais um cartão no Resumo. As quatro abas de baixo continuam as mesmas.

O CondoOS não move dinheiro: a agenda não tem ação de pagar nem de agendar pagamento. Corrigido junto: o valor esperado em Pendências passa a incluir o reajuste por índice (antes mostrava o valor original do contrato).

## Planejamento estratégico (pacote v1.0)

**D72 — Documentos vivos do planejamento** (prompt 01, 07/11/2026). O planejador mestre criou `docs/01-repo-audit.md`, `docs/02-gap-matrix.md`, `docs/03-decisions-register.md`, `docs/product-roadmap.md`, `docs/backlog.md`, `docs/traceability.md`, `docs/pilot-protocol.md` e `docs/roadmap-status.md`, sem alterar código.
- `docs/decisions.md` continua sendo o registro das decisões aceitas (é o "decision-log" do Plano Diretor §12.3). `docs/03-decisions-register.md` guarda só propostas (ADR-P01..P07), divergências com o produto (DV-01..DV-07) e as decisões abertas do Plano (Plano D-01..D-12). Proposta aceita ganha número D7x aqui.
- Histórias do projeto usam o prefixo CB-xxx, para não colidir com US-001..020 da Especificação.
- Os testes não foram executados na sessão do planejamento (contêiner sem dependências nem pgvector); o estado dos FR usa `pronto_para_validar`, nunca `validado`, até haver execução e aceite.

**D73 — Condomínio é o cliente; administradora é colaboradora opcional** (DV-01, Marcio, 07/11/2026). O piloto é contratado diretamente pelo condomínio; o síndico é o usuário principal e decide. A administradora continua com suas rotinas (financeiro, folha, burocracia) e, quando participa, é fonte de dados, executora de tarefas e parceira operacional, nunca dependência estrutural nem aprovadora obrigatória. O trabalho hoje feito pela analista se divide em automatizável (CondoOS), que exige validação (CondoOS Reviewer) e que fica na administradora. O produto atual continua funcionando para condomínios com administradora. Fluxo em `docs/flows.md` (F1).

**D74 — Revisão humana proporcional ao risco** (DV-02, Marcio, 07/11/2026). Todo achado é identificado e registrado automaticamente; a qualificação (categoria, severidade, evidência, confiança, impacto, risco) define a revisão por uma política configurável e versionada (`review_policy`, proposta em `docs/data-model.md` §3). Para o piloto: recomendação de economia exige revisão interna CondoOS; achado crítico/alto exige revisão por pessoa qualificada (sem atrasar alertas urgentes); baixo risco segue automático dentro da política; inconclusivo fica pendente de evidência. A validação pelo gerente da administradora (D48) continua permitida quando o condomínio a habilita, mas não é obrigatória. A política padrão reproduz o comportamento atual.

**D75 — Assunto é objeto independente, ligado a achados** (DV-03, Marcio, 07/11/2026; aceita ADR-P01). Achado = informação identificada; Assunto = contexto de gestão e acompanhamento, transversal a Optimize e Operate. Nem todo achado gera assunto; um assunto reúne vários achados; um achado pode estar em mais de um assunto; assunto pode nascer sem achado (pedido humano, manutenção, obrigação, evento externo). Vínculos preservam histórico e origem; duplicidade é verificada antes de criar. Modelo em `docs/data-model.md` §4.

**D76 — Oportunidade e estágios de economia separados de achado** (DV-04, Marcio, 07/11/2026; aceita ADR-P05). Fluxo: achado → qualificação → oportunidade → recomendação → validação → aprovação → execução → mensuração. Economia em estágios distintos (potencial, estimada validada, aprovada, contratada, realizada), cada um com valor, periodicidade, baseline, método, premissas, evidências, confiança, custos de implementação e riscos. Estimativa nunca é apresentada como economia capturada. Modelo em `docs/data-model.md` §5.

**D77 — Permissões granulares e papéis do piloto** (DV-05, Marcio, 07/11/2026). Papéis ativos no piloto: síndico, CondoOS Admin, CondoOS Reviewer e administradora (colaborador externo); subsíndico e conselheiro continuam como hoje. Zelador, fornecedor e morador ficam previstos e sem permissão até a necessidade do piloto. Ler, editar, validar, aprovar e executar são permissões separadas; validar recomendação não é aprovar no condomínio. Papéis de plataforma só veem condomínios atribuídos (menor privilégio); acesso externo é temporário e revogável; tudo auditado. Decisão do Claude, reversível: no condomínio sem administradora, o fechamento do mês passa ao reviewer. Matriz em `docs/authorization-matrix.md`.

**Mudanças persistentes de D73–D77** (migrações 0011–0014) estão propostas em `docs/data-model.md` §7 com impacto, relacionamentos e critérios de validação, e **aguardam aprovação do Marcio** antes de serem escritas.

## Fechamento do gate G1 (incremento 1 do roadmap)

**D78 — CI, evento de segurança e prova de revogação** (CB-001, CB-003, CB-004; 07/11/2026; plano de migração 0011–0014 aprovado pelo Marcio no mesmo dia).
- **CI** (`.github/workflows/ci.yml`): a cada push e pull request, backend (ruff, black, mypy e a suíte pytest contra `pgvector/pgvector:pg16`, `uv sync --frozen`, sem o extra docling e sem chave de LLM) e frontend (eslint, tsc, prettier). O E2E continua local (`make e2e`), porque precisa da stack inteira.
- **Evento de segurança.** Pedido a condomínio sem acesso continua 404 (D15) e grava `audit_log` `security.access_denied` com `requested_condominium_id`, método e **modelo** da rota (sem ids nem query); `condominium_id` fica nulo, porque o id pedido pode não existir. Papel sem permissão continua 403 e grava `security.permission_denied` com o condomínio, a permissão e os papéis. Os dois são gravados em transação própria (`core/audit.py::record_security_event`), porque a da requisição é desfeita no erro; falha ao gravar nunca muda a resposta. Só ids e códigos.
- **Revogação (SEC-10).** O acesso é recalculado a cada requisição; testes provam que, com a sessão ainda válida, remover o acesso dá 404 na requisição seguinte e desativar a pessoa dá 401 (`tests/test_access_revocation.py`).
- **Fuso por condomínio (CB-002)** não entrou neste incremento: a coluna `condominium.timezone` faz parte da migração 0011 aprovada e vem no incremento 2, para não criar uma migração fora do plano.
- Limite conhecido: um volume alto de tentativas negadas gera uma linha de auditoria por tentativa; limitação de taxa fica para quando houver acesso externo (fornecedor/morador).

## Incremento 2 — acesso e revisão proporcional (migrações 0011 e 0012)

**D79 — Modelo de acesso e política de revisão implementados** (CB-002, CB-013..CB-017; 07/11/2026; plano aprovado em D73–D77).
- **Papéis de plataforma** (`platform_role`) e **atribuição por condomínio** (`condo_assignment`, com RLS). A função `app_accessible_condominium_ids` ganhou o ramo da equipe CondoOS e passou a ignorar acessos revogados ou vencidos. Admin e Reviewer só alcançam condomínios atribuídos e vigentes. O primeiro Admin é criado por linha de comando (`python -m app.platform grant-role ...`, com o papel dono do banco); depois, o Admin atribui pessoas da equipe pela API (`/condominiums/{id}/assignments`). Ainda não há tela para isso.
- **O gerente deixa de ter "todas as permissões".** Antes era `frozenset(Permission)`. Agora a lista é explícita, com as mesmas permissões de antes mais `review_finding`. Sem essa mudança, ele herdaria em silêncio revisão de oportunidade e gestão da plataforma. Validar e revisar só valem quando `condominium.management_company_reviews` está ligado. A regra é aplicada em `CondoAccess.permissions`, então fila, ações permitidas e rotas obedecem juntas.
- **Acesso externo temporário:** `membership` ganhou `invited_at`, `accepted_at`, `expires_at` e `revoked_at`. Remover um acesso agora **revoga** em vez de apagar (antes era `DELETE`); conceder de novo reativa a mesma linha. O convite é aceito no primeiro login. Papéis `zelador`, `fornecedor` e `morador` foram reservados e não têm permissão.
- **Fuso horário** por condomínio (`condominium.timezone`, nome IANA). Agenda e pendências usam o "hoje" do condomínio (`core/time.py::local_today`). Salvar o perfil sem informar o fuso mantém o atual.
- **Política de revisão** (`review_policy`, só inclusão, versionada; a linha com `condominium_id` nulo é o padrão da plataforma e todos a leem). As regras são dados tipados (pydantic com campos desconhecidos recusados), sem expressão em texto. A última regra de cada objeto precisa valer para todos os casos. Sem regra aplicável, a resposta é revisão pela equipe CondoOS. O padrão v1 reproduz o comportamento anterior: achados graves passam por revisão qualificada (equipe CondoOS, ou gerente se permitido) e os demais são publicados direto; oportunidades sempre passam por revisão interna da equipe CondoOS. O achado guarda `review_requirement` e `review_policy_version`.
- **Pendente de evidência:** status `pendente_evidencia` e ação `solicitar_evidencia` (comentário obrigatório, permissão `review_finding`). Esses achados ficam fora da visão do corpo diretivo e do valor em risco, entram na fila de revisão e bloqueiam o fechamento do mês. A coluna `decision.action` passou de 10 para 25 caracteres.
- **Revisão interna** (`internal_review`): só a equipe CondoOS valida. Fica pronta para as oportunidades da VS-03.
- **Quem configura:** síndico ou Admin (`configure_policy`) decidem se a administradora revisa, por `PUT /condominiums/{id}/review-policy`. O gerente não decide isso. O conselho lê a política. Na interface, o cartão "Quem revisa os achados" aparece em Configurações (administradora/Admin). **A tela do síndico para essa chave fica para depois**; a API já atende.
- **Cadastro direto:** o Admin cadastra pela Carteira um condomínio sem administradora e é atribuído a ele automaticamente. Condomínio novo com administradora nasce com `management_company_reviews = true`; sem administradora, `false`.
- **Detalhe do achado** distingue "Validado pela administradora" de "Revisado pela equipe CondoOS" (antes, toda validação aparecia como da administradora).
- **Seed:** Fábio Nogueira Lins (`fabio.admin@condoos.example.com`, Admin nos dois condomínios) e Gabriela Pires Rocha (`gabriela.revisora@condoos.example.com`, Reviewer só em Mirante). Os ids vêm de uuid5, para não alterar a sequência aleatória dos casos plantados.
- **Migração:** `upgrade → seed → downgrade 0010 → upgrade` verificada num banco separado. O downgrade remove os acessos revogados ou vencidos (para que não voltem a valer) e perde as atribuições da equipe CondoOS.
- **Limites conhecidos:** sem tela de atribuição de pessoal CondoOS; sem tela do síndico para a política; a política por condomínio existe no modelo, mas ainda não é editável; `confidence` e `category` dos achados ficam nulos até as regras preenchê-los.

## VS-01 — Assunto (migração 0013)

**D80 — Assuntos implementados** (CB-020..CB-027; 07/11/2026; modelo aprovado em D75 e no plano de migração).
- **Tabelas:** `case_record`, `case_event` (só inclusão; é a linha do tempo), `case_link` (N:N; desfazer o vínculo só preenche `unlinked_at`) e `case_task`, todas com RLS. O nome `case` é palavra reservada no SQL; por isso `case_record` e `case_task` (o modelo de dados dizia `case` e `task`). A numeração `A-AAAA-NNNN` é sequencial por condomínio, com a linha do condomínio travada durante a criação.
- **"Sem próxima ação, sem controle"** (Espec. §8.4): um assunto aberto tem responsável, próxima ação e prazo, ou está suspenso com motivo e data. Isso é checado no serviço e também por um CHECK no banco. A fila mostra os alertas: sem responsável, sem prazo, próxima ação atrasada e suspensão vencida.
- **Estados** (Espec. §8.2) em `app/cases/__init__.py::TRANSITIONS`. Cancelar, suspender, reabrir e resolver exigem motivo, assim como voltar de "aguardando validação" para "em execução". **Resolver** exige todas as tarefas fechadas e, quando o assunto pede evidência (o padrão), ao menos uma evidência ativa. "O fornecedor disse que fez" leva a "aguardando validação", nunca a "resolvido" (WF-04, OPS-02). Assunto encerrado não é editado; só reaberto, e o histórico fica.
- **Vínculos:** achado, documento, contrato, fornecedor (só se o condomínio o usa), despesa e outro assunto. Oportunidade fica para a VS-03. Achado em revisão não pode ser vinculado por quem não o vê. Um registro que já está em outro assunto aberto exige motivo. O vínculo entre assuntos aparece nos dois lados ("citado por"). O achado não muda de status por estar num assunto.
- **Duplicidade antes de criar:** a API devolve 409 com os candidatos (assuntos abertos que compartilham um registro vinculado, ou da mesma categoria abertos nos últimos 14 dias) e não grava nada. Para seguir, é preciso informar por que abrir outro assunto; o motivo fica no evento de criação.
- **Permissões:** `manage_cases` (síndico, Admin e Reviewer) abre, edita, vincula, atribui e move qualquer assunto. `update_task` (também a administradora) trabalha nas próprias tarefas e nos assuntos dos quais é responsável. Responsável e executor precisam ter uma dessas permissões no condomínio; uma tarefa pode ir para uma pessoa sem acesso, identificada pelo nome (ex.: "Zelador Paulo"). O conselho lê e comenta.
- **Evidência:** o upload pelo assunto vira documento do condomínio **sem** passar pela extração (`ingest_file(process=False)`), para não encher a fila de exceções com fotos. Também é possível citar um documento já enviado. Concluir uma tarefa que exige evidência anexa o arquivo ao assunto.
- **Notificação interna:** nesta fatia é só no aplicativo ("Meus assuntos" lista o que a pessoa responde ou executa, e a troca de responsável vira evento). Nenhum e-mail (Plano D-04).
- **Datas:** prazo informado só com a data vale até 23h59 no fuso do condomínio. **Defeito encontrado pelo E2E e corrigido:** `formatDateTime` usava o fuso do processo, e as páginas renderizadas no servidor (UTC) mostravam "02:59". Passou a usar o horário de Brasília; formatar no fuso de cada condomínio fica para depois.
- **Telas:** aba "Assuntos" no celular do síndico (a quinta aba; abertos, meus e encerrados), item "Assuntos" no menu da administradora/equipe CondoOS, formulário de abertura com o tratamento de duplicidade, Assunto 360° (próxima ação, mudança de estado com motivo, contexto, tarefas, evidências, vínculos, comentários e linha do tempo) e "Abrir assunto" no detalhe do achado. Componentes do DS reaproveitados: `Card`, `Badge`, `Field`, `DataTable`, `Timeline`, `EmptyState`; novos: `CaseStatusBadge`/`CaseAttention`, `CaseCards`, `CaseForm`, `CaseDetailView`.
- **Limites conhecidos:** a tela só cria vínculo com achado (ao abrir a partir dele); os demais vínculos já existem na API, mas ainda não na tela. A fila não tem filtro de categoria ou criticidade na tela (a API filtra). Não há envio de alerta de prazo (FR-026). A tela Hoje ainda não mostra assuntos.

## VS-03 — Oportunidade com revisão interna (migração 0014)

**D81 — Oportunidades e estágios de economia implementados** (CB-061, CB-062, CB-064; 07/11/2026; modelo aprovado em D76 e no plano de migração).
- **Tabelas:** `opportunity`, `opportunity_finding`, `savings_record` e `opportunity_review`, todas com RLS. As duas últimas só aceitam inclusão: valor e decisão são fotografias e nunca são editados.
- **Origem:** a equipe CondoOS (`view_opportunity_draft`) gera a oportunidade a partir de um achado R02 (cobrança acima do contrato) ou R03 (reajuste acima do índice). Um achado tem no máximo uma oportunidade em aberto. Oportunidade criada à mão, sem achado, fica para depois.
- **Cálculo por código, nunca pela IA:** o método `excesso_mensal_v1` usa a diferença mensal da regra; o anualizado é ×12 e o custo de implantação é zero. O baseline é o valor contratual reajustado (R02) ou o valor anterior corrigido pelo índice (R03). As premissas ficam escritas e o ressarcimento do mês já pago a maior aparece à parte, como premissa. A confiança é "alta" se o síndico confirmou o achado e "média" nos demais casos. O hash da versão cobre valor, periodicidade, custo, baseline, premissas, confiança e método, e o teste confere que o cálculo é reproduzível (FIN-01).
- **Revisão interna** (D74): a política padrão põe toda oportunidade em `em_revisao_interna`, e só a revisora CondoOS age. Ela pode:
  - aprovar (grava "economia estimada validada" e marca `presented_at`);
  - ajustar (nova linha de potencial, com motivo);
  - devolver ou rejeitar (com motivo);
  - reabrir a revisão de algo já apresentado (sai da visão do condomínio até nova aprovação).
- **Antes da aprovação, a oportunidade não existe para o corpo diretivo nem para a administradora:** a API responde 404 (OPT-01, FR-046). Depois da aprovação, o corpo diretivo vê só a economia estimada validada (nunca o potencial bruto) e, do histórico, só as aprovações e as decisões do condomínio, sem as notas internas.
- **Decisão do condomínio** (`approve_in_condo`, só o síndico): aprovar e seguir (grava "economia aprovada para execução") ou recusar (com motivo). Se o potencial mudar depois da revisão, a aprovação do condomínio é recusada até nova revisão (US-011). Revisora e síndico não fazem a ação um do outro (D77).
- **Estágios lado a lado, nunca somados:** cada um tem nome próprio na tela (potencial identificada, estimada validada, aprovada para execução, contratada ou negociada, realizada e comprovada) e a tela avisa que a estimativa não é economia capturada.
- **Assunto ↔ oportunidade:** o vínculo foi habilitado. O assunto pode nascer de uma oportunidade (origem `opportunity`) e o síndico abre um assunto para acompanhar a oportunidade aprovada.
- **Telas:**
  - menu "Oportunidades" no desktop;
  - "Gerar oportunidade" no detalhe de achados R02/R03 (só para a equipe CondoOS);
  - detalhe com recomendação, estágios, premissas, ações de revisão ou decisão e histórico;
  - no celular do síndico, cartão "Oportunidades de economia" no Resumo, mais lista e detalhe.
- **Limites conhecidos:**
  - estágios "contratada" e "realizada" (CB-063) e extração de aviso prévio e multa (CB-060) não entraram;
  - um único método de cálculo (R02/R03);
  - o relatório PDF/XLSX ainda não mostra oportunidades.

## VS-04 — Briefing do dia e tela Hoje (migração 0015)

**D82 — Briefing orientado por dados** (CB-041, CB-042; 07/11/2026; migração 0015 aprovada pelo Marcio no mesmo dia).
- **Tabela `briefing`** (RLS): um registro por pessoa, condomínio e dia no fuso do condomínio. "Atualizar" cria uma versão nova e nunca edita a anterior. Cada registro guarda o período (desde o briefing anterior da pessoa, ou as últimas 24 h), as fontes parciais e a hora em que foi lido. Retenção de 90 dias no job diário (`retention.purge`): o briefing é uma conveniência, não um registro.
- **Montado por código, sem IA** (`app/briefing/`). Sete seções:
  - riscos e atrasos (assuntos com próxima ação atrasada, suspensão vencida ou criticidade crítica; achados graves sem decisão; vencimentos sem pagamento);
  - decisões aguardando a pessoa, conforme as permissões dela (achados para decidir, oportunidades apresentadas, achados em revisão, oportunidades em revisão CondoOS, fila de exceções);
  - o que está em andamento com ela (tarefas e assuntos);
  - o que foi concluído no período;
  - agenda dos próximos 7 dias;
  - oportunidades (com o nome do estágio, nunca somadas);
  - qualidade dos dados (último documento recebido e último lançamento do extrato).
- **Não afirma o que não aconteceu:** "Concluído" só lista eventos registrados no período (assunto resolvido ou cancelado, tarefa concluída, decisão sobre achado, decisão sobre oportunidade). Cada item aponta para a fonte e abre no contexto certo.
- **Não mistura condomínios:** um briefing por condomínio; o desktop mostra um por condomínio, lado a lado. O teste confere que toda referência pertence ao condomínio do próprio briefing.
- **Fonte que falha ou está desatualizada:** cada seção roda num savepoint próprio. Se falhar, o briefing sai mesmo assim, com o aviso "Dados parciais" e a fonte indicada. Também conta como parcial ficar mais de 35 dias sem documento novo ou sem lançamento no extrato.
- **Defeito encontrado e lição:** a seção "Concluído" falhava (uso de `Result.tuples()`, obsoleto no SQLAlchemy) e a proteção de fonte parcial escondeu o erro; só um teste de conteúdo o pegou. Por isso o teste principal agora exige que, em uso normal, as únicas fontes parciais sejam as de dados desatualizados.
- **Privacidade:** os nomes exibidos vêm só das pessoas que aparecem nos registros do período (a tabela de usuários não tem RLS; nunca carregar todos).
- **Entrega só dentro do aplicativo** (Plano D-04): nenhum e-mail ou mensagem. A leitura é registrada quando a pessoa abre a tela.
- **Telas:**
  - no celular, a aba "Resumo" passou a se chamar **"Hoje"**: o briefing vem primeiro e a auditoria do mês segue logo abaixo, sem mudança (mesma rota `/resumo`);
  - no desktop, novo item **"Hoje"** no topo do menu, com um briefing por condomínio.
  - A tela inicial do desktop continua sendo a Carteira.
- **Teste E2E corrigido:** o fluxo de cadastro de contrato tinha uma corrida antiga (clicava "Mirante do Vale" antes de a página de novo contrato carregar e acertava o filtro da lista); agora espera a navegação.
- **Limites conhecidos:**
  - sem reescrita por IA do texto (pode vir depois, com a mesma conferência numérica das explicações);
  - sem envio por e-mail ou WhatsApp;
  - sem horário configurável por pessoa (FR-009);
  - sem digest semanal (FR-038).

## VS-05 — Pedido de ação com aprovação, política mínima e kill switch (migração 0016)

**D83 — Ação aprovada com escopo congelado, sem envio externo** (CB-010, CB-011, CB-050; 07/11/2026; migração 0016 aprovada pelo Marcio no mesmo dia).
- **Tabelas** (todas com RLS):
  - `action_request`: tipo da ação, assunto e oportunidade opcionais, conteúdo congelado com hash (efeito exato, motivo, quem executa, fornecedor, prazo, riscos), teto de custo, decisão e versão da política, estado, chave de idempotência (única por condomínio), quem aprovou e até quando vale a aprovação, execução registrada;
  - `action_decision`: cada passo (pedir, ajustar, aprovar, recusar, cancelar, anular, encaminhar, bloquear, aprovação vencida, executar), com a versão do conteúdo; **só inclusão**;
  - `outbox_event`: um evento por aprovação, com chave de idempotência única: reprocessar a mesma aprovação não duplica;
  - `automation_pause`: o kill switch, por condomínio e por tipo (ou "todas"); retomar preenche `resumed_at` e mantém o histórico.
- **Motor de política mínimo** (`app/policy/`, código tipado, versão 1, sem avaliação de texto):
  - tipo desconhecido → **nega**;
  - pagamento, contratação, multa e alteração de dados bancários → **nega sempre** (decisão humana fora do sistema);
  - pedir orçamento sem compromisso → só com teto R$ 0,00;
  - cobrar fornecedor, pedir orçamento e agendar visita técnica → **exige aprovação** do síndico;
  - teto acima da alçada do síndico → **nega** ("leve ao conselho ou à assembleia");
  - custo sem alçada configurada → **exige revisão** (configurar a alçada antes);
  - automação pausada → **pausa**.
  - Nenhuma regra desta versão responde "permite": nada roda sem uma pessoa.
  - A negativa fica registrada em `audit_log` (`action.denied_by_policy`), sem criar pedido.
- **Ciclo** (Especificação §9.5):
  - quem trata assuntos (`manage_cases`: síndico, Admin e Reviewer CondoOS) pede;
  - só quem aprova pelo condomínio (`approve_in_condo`: síndico) aprova, recusa ou pede ajustes;
  - a aprovação vale para o hash da versão que estava na tela. Versão diferente → 409 (SEC-04);
  - a aprovação vale por 7 dias;
  - ajustar depois de aprovado anula a aprovação e cancela o evento pendente;
  - recusa exige motivo e nunca gera evento (WF-06).
- **Despacho** (job `action.dispatch`, worker): confere de novo o estado, o hash do conteúdo (recalculado), a validade e a política.
  - Conteúdo alterado por fora → `bloqueada`.
  - Aprovação vencida ou política mudada → volta para aprovação.
  - Sem conector no piloto, **nada é enviado**: a ação passa a "aprovada, aguardando execução" e uma pessoa executa e registra.
- **Execução registrada:** confere a validade de novo (SEC-05). Custo final acima do teto anula a aprovação, atualiza o teto e devolve para nova aprovação (SEC-04). Não existem estados "expirada" ou "invalidada": o pedido volta para aprovação, e a trilha registra "aprovação vencida" ou "anulou a aprovação".
- **Kill switch** (FR-007): `configure_policy` (síndico, Admin CondoOS) pausa e retoma. Tipos pausáveis: despacho de ações e reescrita das explicações por IA.
  - O worker não roda job pausado: devolve para a fila sem gastar tentativa e tenta de novo em 1 minuto.
  - Pedidos novos recebem 409 enquanto houver pausa.
  - Pausar e retomar ficam em `audit_log`.
- **Assunto:** cada passo de uma ação vinculada entra na linha do tempo do assunto (`case_event` tipo `acao`).
- **Hoje:** o briefing mostra ao síndico as ações aguardando aprovação e, a quem trata assuntos, as aguardando execução.
- **Telas:**
  - "Aprovações" no celular, com pedidos, aprovação contextual e o card de pausa (acesso pelo Hoje e pelo assunto);
  - item "Aprovações" no menu do desktop;
  - "Pedir ação com aprovação" no assunto;
  - card "Pausar automações" em Configurações.
  - A tela de aprovação mostra o que a §7.5 pede: o que será autorizado, por quê, o que acontece depois do clique, custo e teto, quem executa, fontes, riscos, alçada e vigência.
- **Fora do escopo:** autenticação reforçada (§7.5 item 10; depende de MFA, excluído), "Escalar" e delegação, aprovação pelo conselho, conectores de envio, política configurável pelo condomínio (CB-012).

## Sobras do backlog (CB-018, CB-019, CB-023, CB-028, CB-063, CB-070)

**D84 — Itens do backlog sem mudança de estrutura** (07/11/2026; pedido do Marcio: "Faça os itens de backlog"). Nenhuma migração nova.
- **CB-018, equipe CondoOS em Configurações.** O Admin CondoOS atribuído ao condomínio lista, atribui (motivo e prazo opcional) e remove pessoas da equipe pela API existente. A pessoa precisa já ter o papel na plataforma. O status aparece como texto e ícone ("Ativa" ou "Encerrada").
- **CB-019, "Ajustes" no celular do síndico.** Novo link no topo da tela, com quem revisa os achados (liga e desliga a revisão pela administradora) e a pausa de automações. A pausa saiu da tela Aprovações e foi para cá.
- **CB-023, filtros da fila de assuntos.** Pessoa, categoria, criticidade e prazo (atrasados, próximos 7 dias, sem prazo) no celular e no desktop. A API ganhou `?prazo=`. Os filtros ficam na URL.
  - Defeito achado pelo E2E: escolher dois filtros em seguida perdia o primeiro, porque a URL ainda não tinha sido atualizada. Corrigido.
- **CB-028, vincular pela tela do assunto.** "Vincular registro" busca contratos, documentos, fornecedores, despesas, achados e outros assuntos (nova rota só de leitura `.../link-candidates`).
  - Respeita a visibilidade: o corpo diretivo não vê achados em revisão; outro condomínio responde 404.
  - Marca o registro que já está em outro assunto aberto e pede o motivo antes de vincular, como a API exige.
- **CB-063, economia contratada e realizada** (sem mover dinheiro nem enviar nada):
  - **contratada:** registrada pelo síndico ou pela revisora CondoOS depois da aprovação do condomínio, com o documento do acordo (guardado sem ir para a extração) e o novo valor mensal. A economia é o baseline menos o valor acordado (método `acordo_v1`), com o custo da mudança; a oportunidade passa a "em execução";
  - **realizada:** medida só pela revisora CondoOS, a partir das faturas com nota emitidas depois do acordo (até 12), comparadas com o baseline (método `medicao_faturas_v1`). A confiança é média com menos de 3 faturas; sem fatura, nada é registrado. Passa a "resultado medido";
  - cada estágio é uma linha nova em `savings_record`, nunca somada aos outros. Como `opportunity_review` só aceita as ações já listadas na migração 0014, o histórico desses dois passos vem de `savings_record` e `audit_log`.
- **CB-070, base do piloto.** As métricas internas ganharam indicadores do protocolo §4, só com contagens:
  - despesas por competência;
  - achados contestados ou ignorados (só um sinal de falso positivo);
  - divergências confirmadas em R$ (não é economia);
  - tentativas de acesso entre condomínios e ações negadas pela política (meta: zero);
  - sessões do corpo diretivo;
  - economia anual por estágio, estimada validada e realizada, sempre separadas.
  - Horas poupadas e falso positivo real continuam fora do produto (diário e revisão amostral).

## Itens do backlog com migração (0017)

**D85 — Versões, proveniência e cláusulas de rescisão** (CB-012, CB-030, CB-031, CB-060; 07/11/2026; migração 0017 aprovada pelo Marcio no mesmo dia). Migração toda aditiva; ida e volta verificada.
- **CB-012, alçadas e parâmetros versionados.**
  - Nova tabela `condominium_settings_version` (RLS, só inclusão). A versão 1 sai dos valores atuais.
  - Mudar alçada ou parâmetro em Configurações cria uma versão com autor, motivo e início. Salvar os mesmos valores não cria versão.
  - As regras avaliam cada mês com a versão vigente no fim dele; meses anteriores à primeira versão usam a primeira. A R12 registra a versão que decidiu (`versao_alcadas`).
  - `condominium.approval_limits` e `rule_params` continuam com o valor atual, então nada que já os lia mudou.
  - O motor de ações (D83) usa a alçada atual, porque a decisão é agora.
- **CB-030, proveniência por campo** (`document.field_provenance`).
  - Cada campo guarda a origem (XML, texto, IA) e, quando o texto mostra o valor, a página e o trecho. O trecho é localizado por código nos formatos brasileiros (R$ 1.234,56, 05/10/2026, CNPJ e CPF formatados) e nunca é inventado.
  - Campo sem valor fica "não disponível".
  - A revisão por pessoa marca todos os campos como "confirmado", com autor e data. O trecho é mantido quando o valor não mudou.
  - A tela de correção mostra origem, página e trecho de cada campo. A IA que não tem trecho localizado aparece como "confira no arquivo".
- **CB-031, versão de documento** (`document.version`, `document.supersedes_id`).
  - Nova rota `POST .../documents/{id}/versions`: o arquivo novo vira a versão seguinte.
  - A anterior fica guardada, com o ponteiro para a nova, e sai da busca do chat.
  - Os contratos que vinham dela passam a apontar para a nova.
  - Só uma versão mais nova por documento; o mesmo arquivo de novo é recusado.
  - O contrato tem "Enviar nova versão do contrato".
- **CB-060, aviso prévio, renovação e multa** (`contract.notice_days`, `auto_renewal`, `termination_penalty`, `clause_evidence`).
  - Lidos por regra do texto do contrato, com o trecho; o que o texto não diz fica vazio.
  - Aplicados quando o contrato nasce do documento e no seed. Para bancos existentes: `python -m app.extraction.clauses`. Valor posto por pessoa é mantido.
  - A agenda mostra o prazo do aviso prévio ("previsto"); as telas de contrato mostram os termos ou "não disponível".
- **Limites:**
  - a leitura de cláusulas é por regra (sem IA) e cobre as redações comuns;
  - não há tela para editar os termos lidos;
  - a versão do documento é marcada pela pessoa (não há detecção automática de "mesmo documento").

## Integração de branches

**D86 — Ações do relatório na carteira seguem permissão e competência** (trazida da branch `claude/compassionate-edison-b6wkpi`, onde tinha o número D65, já usado). `/portfolio` devolve, por condomínio, `can_close` (papel com `close_competence`) e `has_competence` (existe competência do último mês da carteira). A tela mostra "Fechar mês" só com os dois verdadeiros e a prévia só quando a competência existe (senão "—"). Antes, a analista via o botão e recebia 403, e um condomínio recém-cadastrado recebia 404.

**D87 — Método da economia realizada confirmado (Plano D-07).** O Marcio aprovou em 07/11/2026 o método `medicao_faturas_v1` (D84): média das faturas com nota emitidas depois do acordo, comparada ao baseline, com o custo da mudança descontado no valor líquido. Sazonalidade e mudança de escopo continuam fora; um método novo entra como versão nova.

## CondoOS Launch (prompt mestre v1.0)

**D88 — Launch planejado como trilha própria, sem código** (07/11/2026; pedido do Marcio: Fase 0 e proposta da Fase 1). Prompt salvo em `docs/condoos-planning/prompts/CONDOOS_LAUNCH_PROMPT_MESTRE.md`; diagnóstico e blueprint em `docs/condoos-planning/launch/` (`00-status-e-proximos-passos.md` é a porta de entrada). Decisões do Claude, reversíveis: (1) nomes próprios para não colidir com o Plano Diretor e o MVP: marcos LM1–LM5, fases LF0–LF8, gates LG0–LG8, backlog LB-xxx, ADR-L, DL, Q-L; (2) o Launch é camada de condução sobre os objetos existentes, sem serviço novo: marcos derivados de fatos do banco (marco nunca é permissão), prontidão por capacidade calculada na leitura e consumida pela política, guia por cartões determinístico com IA opcional; (3) propostas que exigem aprovação ficam como ADR-L01..L06 e perguntas Q-L01..Q-L04 (auto-cadastro, envio a terceiros, ordem frente à VS-06, migração 0018). Nada implementado até a revisão (gate LG1).

**D89 — Respostas do Marcio ao Launch e fatia LF2-a entregue** (07/11/2026). Respostas: Q-L01 implantação **assistida** pelo Admin CondoOS no piloto (o Admin cria e convida; auto-cadastro fica P2); Q-L02 pedidos a terceiros pelo primeiro corte — o sistema gera link e texto e o **síndico envia** (nada sai do CondoOS, coerente com D83); Q-L03 o Launch LF2 vem **antes da VS-06**; Q-L04 migração 0018 (`launch_state`) e alçadas opcionais no cadastro **aprovadas** (a mudança de API de LB-009 fica para o próximo incremento). Entregue:
- `app/launch/`: marcos LM1–LM5 calculados de fatos (LM1 = síndico com acesso ativo e `accepted_at`, isto é, já entrou; LM2 = contrato, convenção ou ata lido por completo com texto; LM3 = despesa ligada a contrato num mês com competência; LM4 = revisor CondoOS atribuído **e** documento chegando por outro caminho — e-mail do condomínio ou administradora; LM5 = ação com execução registrada). Nenhum marco é gravado nem libera nada.
- Prontidão C1 (perguntas sobre documentos), C2 (leitura de contratos), C3 (confronto de cobranças), binária, com "o que falta"; `autorizada` não existe (D83). Chat em `replay` conta como indisponível (C1 em análise parcial).
- Cartão de primeiro valor do contrato montado por código só com `document.extracted`: *lido* (≥ 0,9 ou confirmado por pessoa), *a confirmar*, *não encontrado*; trecho e página da proveniência; cláusulas de rescisão do contrato; limites da leitura sempre presentes. Evento `launch.first_value_shown` uma vez por documento.
- Próximos passos: no máximo três, um principal (verde-lima), pela ordem do objetivo, só o que de fato falta; "Fazer depois" esconde por 7 dias.
- Tabela `launch_state` (migração 0018, RLS): objetivo, adiados, cartão oculto; eventos `launch.*` em `audit_log`. Permissão nova `MANAGE_LAUNCH` (síndico e Admin CondoOS); conselheiro e administradora só leem.
- SEC-02: regra "conteúdo de documento é dado não confiável" em todos os prompts que recebem documento (extração, classificação, chat, explicação, R04/R07); teste com contrato contendo instrução injetada. Não há respostas gravadas no repositório, então nada precisou ser regravado.
- Interface: cartão de jornada na tela Hoje do síndico (objetivo por escolha rápida, "o que já fiz por você", passos, marcos e prontidão com texto e ícone); cartão de primeiro valor no envio, acompanhando a leitura.
Fora desta fatia: LB-009 (alçadas opcionais), LB-011/012 (prontidão em Ajustes/Configurações e implantações na Carteira), LB-020 (tipos documentais), LB-022 (bordas do upload), métricas de LB-090 na tela.

**D90 — Launch LF2-b: alçada opcional, prontidão nas telas de ajuste, implantações na Carteira e tempo até o primeiro valor** (07/11/2026; pedido do Marcio: "seguir com as próximas ações"; mudança de API aprovada em Q-L04/D89).
- **LB-009 — alçada opcional no cadastro.** `approval_limits` deixa de ser obrigatório em `POST /portfolio/condominiums` e em `app.onboarding` (gravado como `{}`). Sem alçada: R12 não avalia (já não avaliava sem valor) e a política devolve `require_review` para ação com custo ("configure a alçada antes de aprovar"); ação sem custo (pedir orçamento) segue pedindo aprovação do síndico. Nada novo na política: só passou a ser visível.
- **Prontidão C7 — "Ações com sua aprovação":** não configurado sem alçada; análise parcial com ações pausadas (kill switch); supervisionada com alçada. Nunca "autorizada" (D83).
- **LB-011:** cartão "O que já funciona" (componente `CapabilityReadiness`) em Ajustes do síndico e em Configurações da administradora/equipe CondoOS; o cartão de jornada usa o mesmo componente.
- **LB-012:** `GET /portfolio/launch` (só condomínios que a pessoa revisa: gerente, analista, equipe CondoOS) e seção "Implantações em andamento" na Carteira: marcos, próximo marco, funções ativas e atividade (último documento ou evento da jornada; parada a partir de 7 dias).
- **LB-090:** tempo até o primeiro valor = do primeiro acesso do síndico (`accepted_at`) ao primeiro `launch.first_value_shown` (zero se a leitura já existia), mais passos adiados, na seção "Implantação (Launch)" de Métricas. Horas da equipe seguem no diário do piloto (D84).
- **LB-022:** as bordas do envio já eram recusadas pela API sem criar documento (`test_ingestion.py`); a tela agora diz como resolver (vazio, grande, tipo não aceito) e o cartão de um arquivo repetido avisa que mostra a leitura guardada.

**D91 — Tipos documentais novos (LB-020)** (07/11/2026; migração 0019 aprovada pelo Marcio no mesmo dia). Regimento interno, apólice de seguro, balancete, laudo técnico e plano de manutenção entram no CHECK de `document.doc_type` (valores congelados na migração; a volta converte esses documentos em "outro", preservando arquivo e texto). Primeiro corte:
- **Classificação** pelo título no início do documento (heurística, antes da regra solta "contratante/contratada", porque um plano de manutenção ou laudo pode nomear as partes) e pelo prompt de classificação com IA quando houver chave.
- **Só texto**: entram em `TEXT_ONLY_TYPES` — sem extração de campos, nunca vão para a fila de exceções — e em `INDEXED_TYPES` (busca do chat e marco LM2). O cartão de primeiro valor mostra "Guardei …" com o limite "questões jurídicas ou técnicas seguem com um profissional".
- **Aditivo continua "contrato"** (decisão do Claude, reversível): o fluxo de D66 já reconhece o aditivo pelo título e o liga ao contrato como `contract_amendment`; um tipo separado duplicaria esse caminho.
- **Retenção**: os tipos novos não entram em `PURGED_TYPES` (ficam guardados, como convenção e ata). **Correção manual**: a tela de correção continua oferecendo só os tipos com extração; reclassificar para um tipo novo pela tela fica para depois.

**D92 — Launch LF3-a: prontidão C4, C8 e C9 e cobertura no relatório** (07/11/2026; pedido do Marcio: "pode começar a fase 3"). Parte da LF3 sem migração:
- **C4 — Recomendações de economia:** depende do confronto de cobranças (C3) e de uma revisora CondoOS atribuída; sem ela as oportunidades ficam internas (D81).
- **C8 — Documentos esperados dos contratos:** pelo mês anterior, com `pending.py` (D70): "nota fiscal ainda não recebida para N de M contratos; pode ter sido emitida e não enviada". Nunca diz "não emitida". Só contagens; a lista por contrato continua no cockpit de Pendências da administradora (D70).
- **C9 — Fechamento do mês:** última competência, fila do mês vazia (`pending_for_month`) e alguém que possa fechar (gerente ou revisora CondoOS, D77).
- **LB-037 — Cobertura no relatório:** bloco "Cobertura deste relatório" no PDF e aba "Cobertura" na planilha: notas fiscais dos contratos recebidas no mês, extrato bancário presente ou não, itens ainda em revisão ("este relatório é parcial"). Vale também para mês fechado, que pode ter nota esperada que nunca chegou.
- **LB-031:** a reconciliação nos dois sentidos já existia em `pending.py` (contrato sem cobrança, cobrança sem contrato/aprovação) e agora aparece como cobertura em C8 e no relatório; a lista detalhada segue só para a administradora (D70).
- A parte com migração (conflitos de dados, Central de Validação, política que consulta conflitos, classes "inferido"/"conflitante") está proposta em `docs/condoos-planning/launch/07-lf3-proposta-conflitos.md` e **aguarda aprovação** da migração 0020.

**D93 — Launch LF3-b: conflitos de dados e Central de Validação** (07/11/2026; proposta `docs/condoos-planning/launch/07-lf3-proposta-conflitos.md` aprovada pelo Marcio: migração 0020, revisora CondoOS e gerente resolvem, política nega ações com o fornecedor enquanto houver conflito aberto).
- **Modelo (migração 0020):** `data_issue` (RLS; tipo, estado `aberto`/`resolvido`/`descartado`, contrato afetado, fornecedor, campo em disputa, os dois lados com trecho e página, funções rebaixadas, valor mensal em jogo, detector versionado, chave única por condomínio, resolução) e `data_issue_event` (RLS, só inclusão). `case_link` aceita `data_issue` (vínculo com assunto, D75). Volta da migração remove esses vínculos, as duas tabelas e restaura o CHECK.
- **Detectores v1** (`app/data_issues/`, determinísticos): aditivo com efeito fora da vigência que o documento do contrato declara; dois contratos do mesmo fornecedor para o mesmo serviço (palavras do objeto, ≥ 60%) com períodos que se cruzam e sem um ser versão do outro (D85); aditivos do mesmo dia com valores diferentes. Rodam quando um contrato ou aditivo entra pelo casamento e quando a gerência cria ou edita um contrato. Idempotentes; o seed não gera nenhum. A chave do conflito segue o documento do aditivo, não a linha.
- **Ciclo:** conflito que deixa de aparecer sem ação de pessoa vira "descartado — superado por novos dados" e volta se reaparecer (como D61); o que uma pessoa decidiu fica. Resolver exige escolher um dos lados e motivo (≥ 10 caracteres); descartar e reabrir exigem motivo. Resolver **registra** a decisão e não altera o contrato (correção de dado segue pela tela de Contratos).
- **Efeitos enquanto aberto:** C2 e C3 em análise parcial com o título; o cartão de primeiro valor marca o campo como "Conflitante" e explica; achados com evidência do contrato ganham a linha "Contrato com divergência de dados em validação"; a política devolve `DENY` para ação com o fornecedor (`evaluate(..., supplier_id=...)`, lido do banco, nunca de texto), na criação, no ajuste, na aprovação e no despacho.
- **Quem pode:** ver, quem vê o condomínio; resolver, descartar e reabrir, `CORRECT_EXTRACTION` (revisora CondoOS e gerente). O síndico vê a prontidão rebaixada e o conflito no cartão, mas não resolve.
- **Central de Validação** (`/admin/validacao`, item "Validação" no menu): conflitos abertos da carteira, maior valor em jogo primeiro, os dois lados lado a lado com trecho e link para o documento, escolha da versão e motivo; mostra o tamanho da fila de exceções, que continua na sua tela.
- **Fora desta fatia:** detectores `duplicidade_suspeita` e `dado_vencido` (tipos reservados); classe "inferido" na proveniência (LB-036 parcial: "conflitante" entregue).

**D94 — Launch LF3 fechada no código: campo "inferido", envio em lote e gate LG3** (07/11/2026; pedido do Marcio: "seguir com os próximos passos"). Sem migração.
- **LB-036 — "inferido":** o motor de confiança passa a devolver quais campos preencheu por regra (D68: início = data da assinatura; mês de reajuste = mês do início) e a proveniência grava `source: "inferido"` com a regra, **sem trecho** (o texto não diz aquilo, mesmo que a data apareça nele). O cartão de primeiro valor mostra "Presumido" com a regra, inclusive "prazo indeterminado" quando não há data de fim (antes aparecia como "lido"). A tela de correção diz "presumido por regra, não lido no texto". Documentos já processados mantêm a proveniência antiga até serem processados de novo.
- **LB-033 — "Faça por mim":** `GET /condominiums/{id}/documents-status?ids=…` (até 50; id de outro condomínio simplesmente não volta) e painel "Leitura do lote" no envio do síndico com o estado de cada arquivo (lendo, lido, a conferir pela equipe com o motivo, não consegui ler) e os totais; aparece quando o envio tem mais de um arquivo.
- **Gate LG3:** `tests/test_lg3_gate.py` percorre num só cenário documentos contraditórios (contrato e aditivo entrando pelo casamento real → conflito, C2 parcial, política nega), ausente (C8 "ainda não recebida", cobertura do relatório "0 de 1" e "sem extrato"), duplicado (um documento) e ilegível (nunca "lido"). Gate LG3 atendido no código; a confirmação na stack do docker vai junto com o `make e2e` do LG2.

**D95 — Launch LF4: pedido de documentos a terceiros com link de envio e triagem de arquivos** (07/11/2026; proposta `docs/condoos-planning/launch/08-lf4-proposta-delegacao.md` aprovada pelo Marcio: migração 0021, triagem sem antivírus de assinatura, destinatário só com nome e papel, link de 7 dias e 30 arquivos).
- **Triagem (ADR-L06), em todo envio** (upload, e-mail, link), em `app/ingestion/triage.py`, só com pypdfium2 e Pillow: PDF com JavaScript, ação de abrir programa, arquivo embutido ou rich media é recusado (nomes com escape `#xx` decodificados, e pdfium confere scripts e anexos mesmo em fluxos compactados); PDF que pede senha para abrir é recusado; PDF só com restrição de uso (senha de dono, comum em notas de prefeitura) passa; PDF corrompido é guardado e a leitura diz que não conseguiu ler (comportamento anterior). Imagens são abertas com limite de pixels e regravadas no mesmo formato (sai metadado e qualquer conteúdo anexado); imagem que não abre é recusada. Mensagens em PT-BR com o que fazer. ZIP, Office e executáveis já não eram aceitos.
- **Modelo (migração 0021):** `delegation_request` (RLS; destinatário só nome e papel, itens, prazo, estado), `delegation_link` (RLS; só o hash SHA-256 do token, validade, revogação, limite e contagem), `delegation_event` (RLS, só inclusão), `document.origin = 'pedido'` e `document.delegation_request_id`. Função `app_delegation_link_condominium(hash)` (SECURITY DEFINER) devolve só o condomínio do link: a rota pública roda com o papel da aplicação dentro daquele condomínio (RLS), nunca com o papel do worker.
- **Regras (`app/delegation/`):** preparar = síndico, CondoOS Admin e Reviewer (`MANAGE_CASES`); o síndico que prepara já autoriza; a equipe só deixa rascunho. Autorizar, gerar link e marcar "já enviei" = só o síndico (`APPROVE_IN_CONDO`). Encerrar e revogar = síndico e Admin (`MANAGE_DELEGATION`, nova). Gerar outro link invalida o anterior. O texto pronto leva o link; **nada é enviado pelo sistema** e "já enviei" é declaração do síndico. Itens de nota fiscal sugeridos pela C8 contam como recebidos sozinhos quando a nota chega; os demais, por uma pessoa. Tudo recebido conclui; link vencido expira; encerrar/revogar não apaga o que chegou. Kill switch: o tipo "Links de envio de documentos" pausa os links do condomínio.
- **Rota pública:** `GET /public/delegations/{token}` mostra só condomínio, destinatário, itens, prazo e arquivos restantes; `POST .../files` só grava. Token desconhecido, vencido, revogado, de pedido fechado ou pausado: o mesmo 404. Cada envio e cada recusa entram no histórico só com ids.
- **Telas:** "Pedidos" no celular do síndico (a partir de "Enviar documentos" e do próximo passo "Peça os documentos que faltam", que aparece quando a C8 está parcial), formulário com sugestões, detalhe com autorizar, link e texto, "Compartilhar" (partilha nativa do celular), "Copiar texto", "Já enviei", itens, arquivos recebidos e histórico; página pública `/enviar/[token]`.
- **Fora desta fatia:** tela de pedidos no desktop da equipe (a equipe prepara pela API por enquanto); limite por IP na rota pública (há limite por link e por arquivo); antivírus de assinatura.
- **Regressão corrigida nos E2E:** desde D90 a Carteira tem duas tabelas; `login.spec.ts` e `condoos-staff.spec.ts` passam a olhar só a tabela "Condomínios da carteira".

**D96 — Gates LG2, LG3 e LG4 validados na stack do docker** (08/11/2026, MacBook do Marcio, `make reset && make up && make e2e`). 33 fluxos passaram e 32 foram pulados por projeto (celular/desktop), incluindo todos os do Launch (`launch.spec.ts`, `validation.spec.ts`, `delegation.spec.ts`). Única falha: `correction.spec.ts`, porque o recibo do teste foi lido por completo sozinho (`done`, sem revisão) e nunca entrou na fila. Causa confirmada: a stack do Marcio tem `ANTHROPIC_API_KEY` ativa (37 chamadas, US$ 0,18 na suíte inteira e na repetição do teste); o teste supunha que, sem IA, todo recibo vai para a fila. O teste passa a esperar a leitura e pula com aviso quando ela dispensa correção (confirmado no MacBook: "1 skipped"). As falhas vistas antes na stack local sem docker (navegação lenta no `next dev`) não apareceram no docker.

**D97 — Medições com a chave de IA prontas para rodar no Mac** (08/11/2026; pedido do Marcio: medir chat, acurácia e R04/R07 com a chave).
- **`make accuracy` em modo de gravação quebrava:** registrava o custo das chamadas num condomínio fictício (`uuid5("condoos-corpus")`) que não existe, e a chave estrangeira de `llm_calls` recusava. Agora as chamadas da medição são registradas **sem condomínio** (o custo fica em `llm_calls`; não há orçamento por condomínio). `analyze` e as funções de IA aceitam `condominium_id` nulo só para isso.
- **Gravações da medição separadas dos testes:** `make accuracy` grava as respostas em `api/corpus/cassettes/` (fora do git), nunca em `tests/fixtures/llm`, para que testes que esperam "sem IA" (recibo na fila) não passem a usar respostas reais.
- **`make rules-eval`:** teste lento `test_every_planted_case_live` roda os casos plantados com o modelo real e exige exatidão (todos os positivos, nenhum extra, nada "não avaliado"); escreve `docs/rules_eval.md`. Observação: no seed só o caso de R04 depende do modelo; o de R07 é decidido pela parte determinística (CNAE incompatível), então a parte de IA da R07 continua sem caso plantado.
- Correção junto com D97: "dias sem atividade" da implantação (Carteira, D90) comparava a data de hoje no fuso do condomínio com a data UTC do último evento; perto da meia-noite dava um dia a mais. Agora as duas datas ficam no fuso do condomínio (`core/time.py::local_date`). O teste que pegou o defeito passou a calcular a data esperada da mesma forma.

**D98 — Primeiras medições com o modelo real e duas correções no chat** (08/11/2026, no MacBook do Marcio, com a chave dele).
- **R04 com o modelo (`make rules-eval`): aprovada.** 12 casos plantados, nenhum positivo perdido, nenhum falso positivo, nada "não avaliado".
- **Acurácia com o modelo (`LLM_MODE=record make accuracy`, sem Docling no Mac):** 26/30 (87%) sem revisão (meta 90%); tipo de documento 30/30; 1 documento automático com dado divergente (meta 0): o campo `objeto` de `20_contrato.pdf` (texto livre; o relatório passa a mostrar esperado × obtido para confirmar se é só redação diferente). As 4 fotos que foram para revisão disseram por quê (baixa confiança, dígito verificador).
- **Chat ao vivo (`make chat-eval`):** 28/33 (85%; meta 90%), **zero vazamento entre condomínios**. As 5 falhas tinham duas causas, ambas corrigidas:
  1. **Soma errada na ferramenta `search_expenses`** (defeito anterior, origem do aviso "cartesian product" nos testes): o total somava `Expense.amount` contra a subconsulta, multiplicando as linhas (energia de 09/2026 do Acácias: R$ 7.745,40 real × R$ 756.516,11 devolvido). Agora soma só as linhas filtradas; teste compara com o banco.
  2. **Verificador de números recusava valores citados de trechos de documento:** os trechos vêm em texto brasileiro ("R$ 9.250,00") e o verificador só lia números em formato de máquina. Agora números brasileiros que aparecem nas saídas das ferramentas também valem; valor inventado continua recusado (teste com os dois casos).
- **Relatório de acurácia:** nova seção "Campos não lidos corretamente" (arquivo, automático, campo, divergente/ausente, esperado, obtido). Rodar de novo em `LLM_MODE=replay` usa as respostas gravadas em `api/corpus/cassettes/` sem custo.
- **Segunda rodada (mesmo dia):** chat ao vivo **32/33 (97%), zero vazamento: aprovado.** O `objeto` divergente era só redação: esperado "limpeza e conservação das áreas comuns do condomínio", lido "Prestação de serviços de limpeza e conservação das áreas comuns do condomínio". A comparação de campos de texto livre (`objeto`, `descricao`, `discriminacao`) em `corpus/accuracy.py` passa a aceitar quando um texto contém o outro (os demais campos seguem exatos); com isso, 0 automático com dado divergente.
- **Pendente:** acurácia sem revisão em 87% (meta 90%): os erros estão só em fotos degradadas, que foram para revisão como devem. Medir de novo com Docling (no worker do docker) antes de mexer na extração.

**D99 — Acurácia com Docling: a IA lê fotos melhor pela imagem do que pelo texto do OCR** (08/11/2026, worker do docker no MacBook do Marcio, `make accuracy-docling`, modo `record`).
- **Resultado:** igual no total (26/30 sem revisão, 87%; **0 automático com dado divergente**; tipo 30/30). PDFs e XMLs seguem perfeitos. A foto 28 (boleto) passou a vir completa.
- **Mas as fotos pioraram:** com o Docling, a IA recebe o texto do OCR e não a imagem (regra "a IA recebe só o texto quando há texto"). O OCR erra letras e dígitos ("Viglare Seriços ... Lita", "Femeira", CNPJs, competência 2025-10) e a IA copia o erro. Sem Docling, a IA olhava a foto e errava menos (foto 27: 1 campo errado sem Docling, 9 com Docling). Todos esses casos foram para revisão (dígito verificador e baixa confiança seguraram), mas um nome com erro de OCR é o tipo de dado que poderia passar.
- **Aprovado pelo Marcio e implementado (08/11/2026):** para foto ou imagem, mandar sempre a imagem à IA, mesmo quando o Docling produzir texto; PDF com camada de texto segue só com o texto. O texto do OCR continua guardado para a busca. Custo: alguns centavos a mais por foto. Nenhum dado novo sai: a imagem já ia à IA quando não havia texto.
- **Medição depois da mudança** (`LLM_MODE=replay make accuracy-docling`, sem custo: as respostas das fotos já estavam gravadas): 26/30 (87%) sem revisão, **0 automático com dado divergente**, tipo 30/30. Os erros de campo caíram de 17 (Docling mandando texto) para 6, todos em fotos que foram para revisão. A foto 28 (boleto) ficou 7/7: a linha digitável vem do texto do OCR pela leitura determinística (dígitos verificadores conferidos), e o resto a IA lê na imagem.
- **Leitura dos 87%:** PDFs e XMLs 25/25 automáticos e certos; fotos 1/5. As fotos 26, 27, 29 e 30 do corpus são degradadas de propósito (inclinadas, baixa resolução) e foram para revisão com o motivo escrito; a 26 tinha os 10 campos certos, mas a IA declarou baixa confiança. Não afrouxamos a regra de confiança para bater a meta: a meta de 90% passa a ser conferida no piloto, com a proporção real de fotos.

**D100 — Sobras da LF4: limite por IP, pedidos no desktop da equipe e "com você × com outros" no Hoje** (08/11/2026).
- **Limite por endereço nas rotas públicas do link (LB-041):** 60 pedidos a cada 10 minutos por endereço (`public_link_max_requests`, `public_link_window_seconds`), somados à abertura e ao envio, além dos limites por link e por arquivo. Acima disso, 429 com "Muitas tentativas a partir desta rede" e `Retry-After`, a mesma resposta para qualquer token. O endereço é o último item de `X-Forwarded-For` (posto pelo nosso balanceador ou, sem ele, pelo servidor web), então um valor forjado pelo cliente no começo da lista não conta. Contagem só em memória (`app/core/ratelimit.py`): nenhum IP vai para o banco nem para os logs. Com mais de um processo da API, cada um conta à parte; no piloto há um só.
- **Pedidos no desktop da equipe (LB-044):** `/admin/pedidos` com filtro por condomínio (`GET /portfolio/delegations`), abertos primeiro pelo prazo; a equipe prepara pedido (fica como rascunho) e abre o detalhe; autorizar e gerar o link seguem só com o síndico.
- **"Com você × com outros" no Hoje do síndico (LB-044):** `GET /condominiums/{id}/delegations/board`, calculado a cada leitura. Com você: autorizar o pedido, enviar o link (não marcado como enviado), conferir arquivos recebidos com itens que não se resolvem sozinhos (nota fiscal se resolve pela C8). Com outros: pedidos com o destinatário (progresso, prazo, vencido com ícone e texto) e a equipe CondoOS (documentos em conferência, divergências em validação). O cartão some quando não há nada dos dois lados. Achados e ações continuam no briefing, sem repetir aqui.
- Verificação: 358 testes do backend, lint, E2E `delegation.spec.ts` (celular e desktop) na stack local sem Docker. **`make e2e` no docker (MacBook do Marcio, 08/11/2026): 33 passaram, 35 pulados por projeto, nenhuma falha.**

**D101 — LF5: e-mail de entrada real (Amazon SES em São Paulo → S3), endereço com parte aleatória e saúde do canal** (08/11/2026). Aprovado pelo Marcio: provedor A da proposta (`docs/condoos-planning/launch/09-lf5-proposta-email-entrada.md`), endereço com parte aleatória e troca pelo síndico, migração 0022. Ainda não há domínio: tudo foi construído e testado com um bucket simulado; a configuração real está em `docs/deploy.md`, seção 7.
- **Provedor:** `S3EmailProvider` lê o que o SES gravou em `inbound/` e move para `processed/` ou `rejected/`; a pasta local continua (`FolderEmailProvider`). Escolha por `INBOUND_EMAIL_PROVIDER` (`none`, `folder`, `s3`). Nada é respondido ao remetente.
- **Endereço:** `<slug>-<parte aleatória de 8>@<domínio>` (`condominium.inbound_token`). Os dois pedaços precisam bater: slug de A com a parte de B não entra em lugar nenhum. Trocar o endereço (síndico e Admin CondoOS, `MANAGE_DELEGATION`) faz o antigo parar na hora e grava `inbound.address_changed` na auditoria. O endereço só com o slug vale fora de produção (`INBOUND_ACCEPT_SLUG_ADDRESS`).
- **Registro e saúde (LB-051):** `inbound_message` (RLS, só inclusão) guarda o domínio do remetente, as contagens (anexos, documentos novos, já recebidos, recusados), os motivos e o estado (`processada`, `recusada`, `falhou`); nada de assunto, corpo ou endereço completo. O `Message-ID` em hash evita processar duas vezes. Destinatário desconhecido fica com condomínio nulo, invisível para a aplicação. O cartão "E-mail de entrada" (Ajustes do síndico e Configurações da equipe) mostra o endereço, copiar, "Recebendo", "Nenhum e-mail recebido ainda" ou "Nenhum e-mail há N dias" (a partir de 30), os últimos e-mails e a troca do endereço.
- **Pausa:** novo tipo `email.inbound` no kill switch: as mensagens ficam esperando no bucket, sem perda e sem registro, até retomar.
- **Falha:** erro ao processar grava `falhou` e move a mensagem para `rejected/`, sem travar as outras.
- Verificação: 6 testes novos (`test_inbound_email.py`), suíte do backend, lint, migração 0022 ida e volta, E2E `launch.spec.ts` (troca do endereço) na stack local sem Docker. **`make e2e` no docker (MacBook do Marcio, 08/11/2026): 34 passaram, 36 pulados por projeto, nenhuma falha; a migração 0022 subiu sozinha.**

**D102 — LF5: documento esperado conferido em todos os canais (LB-052) e cobertura do mês na Agenda (LB-055)** (08/11/2026). Sem migração.
- **Antes de dizer "não recebida", conferir todos os canais:** `pending.py::arrivals` procura documentos fiscais (NFS-e, NF-e, boleto, recibo, outro) recebidos desde o início do mês por qualquer canal (app, e-mail, link de pedido) que ainda não viraram despesa: em leitura, em revisão ou lidos sem casamento. O CNPJ lido (prestador, emitente, beneficiário ou recebedor) e o mês lido (competência, emissão, vencimento ou data) ligam o documento ao contrato. Com isso, o contrato fica **"em_conferencia"** (chegou, em conferência) em vez de "sem faturamento" ou "aguardando". Em conferência não conta como pendência aberta.
- **Documentos ainda sem CNPJ lido** contam como "ainda em leitura" e entram como ressalva no texto: "Há N documento(s) ainda em leitura que podem ser alguma delas."
- **Onde aparece:** prontidão C8 (fato `em_conferencia`; a mensagem de falta passa a dizer "não recebida por nenhum canal"), cobertura do relatório do mês, Agenda (selo "NF chegou, em conferência"), cockpit de Pendências (selo "Chegou, em conferência") e o pedido de documentos (a sugestão de pedir a nota ignora o que está em conferência). A nota recebida mostra por qual canal chegou, quando há documento ligado.
- **Cobertura do mês (LB-055):** `GET /condominiums/{id}/coverage?month=AAAA-MM` (quem vê o condomínio; padrão: mês anterior) e o cartão "Notas dos contratos · MM/AAAA" na Agenda do síndico (mês anterior) e na Agenda do desktop (mês mostrado, com um condomínio escolhido). Só acompanhamento: lacuna é "não recebida", nunca acusação.
- Verificação: testes novos em `test_pending.py` (canal, mês, ressalva, C8, rota e isolamento), suíte do backend (366), lint, E2E `agenda.spec.ts` (celular e desktop) na stack local sem Docker.

**D103 — LB-053: o CondoOS envia por e-mail o pedido de documentos, com aprovação do síndico** (08/11/2026). Respostas do Marcio à proposta `docs/condoos-planning/launch/10-lb053-proposta-envio-pedido.md`: (1) exceção aprovada: o CondoOS envia **só** o e-mail do pedido de documentos, sempre com aprovação do síndico da versão exata (revê Q-L02 e a Plano D-04 só para este caso; DL-07 resolvida); (2) "responder para" com o e-mail do síndico; (3) e-mail do destinatário mascarado depois do envio; (4) a equipe CondoOS prepara e o síndico aprova; (5) migração 0023 aprovada.
- **É o primeiro e único envio do sistema.** Usa os pedidos de ação de D83: tipo `pedido_documento.enviar_email` (L3, sem custo, `sends_email`, `internal`: não aparece no formulário genérico e a rota genérica recusa criá-lo ou mandar `email` no conteúdo). A política continua negando por padrão. O conteúdo congelado tem destinatário, remetente ("CondoOS em nome do <condomínio>"), responder para, assunto e corpo fixo mais um recado de até 500 caracteres. O síndico aprova o hash dessa versão, na tela do pedido ou na de Aprovações, que agora mostra o e-mail inteiro; ajustar o e-mail depois é recusado (cancela e prepara outro).
- **Despacho:** o worker confere tudo de novo (estado, hash, validade, política, pedido aberto e limites). Num savepoint, gera o link novo (o anterior deixa de valer; o token não é guardado: o corpo aprovado leva `{link}`) e envia pelo SMTP do link mágico. Registra "aceito pelo servidor de e-mail" (Message-ID e hora em `outbox_event.receipt`, evento `email_enviado`, `shared_at`), nunca "entregue". O endereço fica mascarado no conteúdo e o SHA-256 do endereço completo fica para a trilha. Se o servidor recusar, tenta 3 vezes (2, 4 e 8 min) e então bloqueia com `email_falhou`; nada é enviado e o link anterior continua valendo. Os outros tipos de ação continuam sem enviar nada.
- **Limites:** um destinatário, sem anexo; 1 e-mail por pedido a cada 24 h e 3 no total; 20 por condomínio por dia; um envio em andamento por pedido; pedido em rascunho não envia. A pausa `pedido_documento.enviar_email` (e a pausa geral de ações) deixa o envio esperando.
- Sem SMTP configurado (`MAILER=console`), a opção não aparece. Envio real fora do ambiente local depende do domínio com SPF e DKIM (o mesmo da entrada, D101).
- Verificação: 4 testes novos (`test_request_email.py`), 370 testes do backend, lint, migração 0023 ida e volta, E2E `delegation.spec.ts` (o e-mail chega ao servidor simulado e o link funciona) na stack local sem Docker.

**D104 — Domínio `condoos.ia.br` e nomes do e-mail** (08/11/2026). O Marcio registrou `condoos.ia.br` (DNS no registro.br). Saída por `nao-responda@condoos.ia.br` (identidade do domínio no SES com Easy DKIM e DMARC `p=none`); entrada em `<slug>-<parte aleatória>@entrada.condoos.ia.br` (MX do subdomínio `entrada` para o SES de São Paulo, bucket `condoos-entrada`). O domínio principal fica livre para uma caixa de pessoas no futuro. O `docker-compose.yml` passa a aceitar SMTP, remetente, domínio de entrada e o provedor S3 da entrada pelo `.env` (padrão continua Mailpit e pasta), para testar a Amazon a partir do docker local antes da hospedagem; valores vazios contam como não definidos. Passo a passo em `docs/deploy.md`, seção 7.

**D105 — Configuração real na AWS e veredito de vírus do SES** (08/11/2026). Com o Marcio, na conta do projeto (São Paulo): liberada a região `sa-east-1` na SCP de regiões da organização (bloco `RegionFloor`) e nas regiões visíveis do console; SES no plano Essentials, identidade `condoos.ia.br` (Easy DKIM 2048) e e-mail pessoal verificados, **sem** Gerenciador Virtual de Capacidade de Entrega (o rastreamento de abertura e de links reescreveria o link de envio e coletaria dado de terceiro); DNS no registro.br (3 CNAME do DKIM, `_dmarc` com `p=none`, MX de `entrada` para `inbound-smtp.sa-east-1.amazonaws.com`); bucket `condoos-entrada` privado com expiração de `processed/` e `rejected/` em 30 dias e política que só deixa o SES desta conta gravar em `inbound/`; conjunto de regras `condoos` ativo com a regra `entrada-documentos`. O SES só marca vírus e spam: o CondoOS passa a recusar mensagem com `X-SES-Virus-Verdict: FAIL` ("O provedor de e-mail detectou vírus na mensagem.") e a ler a marcada como possível spam com uma nota na saúde do canal (uma nota fiscal pode ser mal julgada). Só `FAIL` é considerado: um cabeçalho forjado só consegue recusar o e-mail do próprio remetente. Teste em `test_inbound_email.py`. Depois, no mesmo dia: identidade `condoos.ia.br` e e-mail pessoal **verificados**; usuário IAM `condoos-worker` (só lista, lê e move em `inbound/`, `processed/` e `rejected/` do bucket); credenciais SMTP do IAM (não o Mail Manager, que tem custo à parte); pedido de acesso de produção **aprovado pela Amazon em 09/11/2026** (a conta saiu do modo de teste em `sa-east-1`); lista de supressão da conta habilitada para devolução e reclamação. Testes de envio só para endereços reais do Marcio ou para o simulador da Amazon (`success@simulator.amazonses.com`), nunca para `@example.com`. **Primeiro envio real em 09/11/2026 às 10:29:** link de acesso e pedido de documentos aprovado pelo síndico (o Marcio, cadastrado como síndico do condomínio de teste pelo Admin CondoOS), entregues na caixa de entrada do Gmail a partir de `nao-responda@condoos.ia.br`, com "responder para" do síndico; o pedido mostrou "Aceito pelo servidor de e-mail" e o endereço mascarado. Ajuste de texto depois do teste: o cartão do link diz "O CondoOS enviou por e-mail" quando o último compartilhamento foi o e-mail (campo `shared_by` no detalhe do pedido), e o formulário não diz mais "não pedimos e-mail". **Primeiro e-mail real recebido em 09/11/2026 às 10:02**: do Gmail do Marcio para `jardim-das-acacias-…@entrada.condoos.ia.br`, com PDF, lido pelo docker local (`INBOUND_EMAIL_PROVIDER=s3`) e mostrado em Ajustes como "Processado · 1 documento novo". O envio continua pelo Mailpit no ambiente local, porque os usuários do seed são `@example.com` (pela Amazon, o link de acesso não chegaria e os envios voltariam como inexistentes); o teste de envio real fica para quando houver usuário com e-mail de verdade.

**D106 — Hospedagem do piloto: VPS da Hostinger** (09/11/2026). O Marcio achou caras as opções da AWS (`docs/proposta-hospedagem.md`: EC2 + RDS, ~US$ 120/mês) e escolheu a **VPS KVM 4 da Hostinger** (4 vCPU, 16 GB, 200 GB, Ubuntu 26.04 LTS, data center no Brasil, R$ 59,99/mês em 24 meses), já contratada, com acesso SSH só por chave. Tudo numa máquina (`docker-compose.prod.yml`: PostgreSQL 16 + pgvector sem porta exposta, `api`, `worker` com Docling, `web` e Caddy 2.10 com HTTPS automático e HSTS para `app.condoos.ia.br`). Fora da máquina, na AWS São Paulo: e-mail (D105), documentos no bucket privado e versionado `condoos-documentos` e backup diário do banco (`pg_dump` cifrado com AES-256 e senha só no servidor e no gerenciador de senhas, guardado 30 dias em `backups/`). Preparação do servidor por script (`deploy/setup-server.sh`: atualizações automáticas, firewall com 22, 80 e 443, Docker oficial, usuário `condoos`, sem senha e sem root por SSH, swap). Troca aceita: sem PITR, a perda máxima é de um dia (contra 5 minutos no RDS); a migração para o RDS é restaurar o backup e trocar o endereço do banco. Novo comando `python -m app.platform add-person` para o primeiro Admin num banco vazio (teste em `test_access_model.py`). Passo a passo em `docs/deploy.md`, seção 9. **No ar em 09/11/2026:** servidor preparado pelo script (Docker 29.9.3, firewall com OpenSSH, 80 e 443), código baixado por chave de implantação só de leitura do GitHub (sem token pessoal no servidor), os 5 serviços de pé, certificado HTTPS emitido para `app.condoos.ia.br`, primeiro Admin CondoOS criado (`add-person` + `grant-role`) e entrada pelo link mágico enviado pela Amazon. Bucket `condoos-documentos` (privado, versionado, `backups/` expira em 30 dias) e usuário IAM `condoos-app` só com lista, leitura, gravação e exclusão nesse bucket. **Backup e restauração testados no mesmo dia:** backup cifrado enviado ao S3, pessoa de teste criada depois, restauração do backup e a pessoa sumiu; backup diário agendado no cron do usuário `condoos` (3h30 UTC). Correções vindas do teste: aspas no remetente do arquivo de produção (o script de backup lê o arquivo pelo bash) e download da restauração para um arquivo do próprio usuário antes de parar o sistema (um nome errado não muda nada). Sem dados reais até os itens da seção 5 de `docs/proposta-hospedagem.md`.

**D107 — Exceção de licença do chat e autorização do piloto** (09/11/2026). Decisões do Marcio:
- **Licença (fecha a pendência da D54):** aceito o executável do Claude Code embutido no `claude-agent-sdk`, sob os termos comerciais da Anthropic, como **única exceção** à regra de licenças abertas. Motivos: o uso da chave de API já está sob os mesmos termos; os termos permitem oferecer produto a clientes com o Agent SDK usando chave de API (nunca login do claude.ai); o programa roda só no servidor do CondoOS e não é redistribuído. Alternativa registrada, sem prazo: trocar o motor do chat pela biblioteca `anthropic` (MIT) com o laço de ferramentas próprio.
- **Piloto:** condomínio piloto onde a síndica é **Karla Mônaco**; o Marcio é condômino e criador do CondoOS (conflito de interesse declarado no termo). O fornecedor é o **Marcio, pessoa física** (sem CNPJ por ora). Instrumento: termo de participação no piloto com acordo de tratamento de dados (condomínio controlador, fornecedor operador; Hostinger, AWS e Anthropic como subprocessadores; transferência internacional para a Anthropic; aviso de incidente em 3 dias úteis; eliminação em 30 dias no fim). A administradora não assina com o CondoOS. A minuta fica num documento fora do repositório (tem dados reais) e passa por revisão jurídica antes da assinatura. Os condôminos recebem um comunicado (WhatsApp) e o tema vai à próxima assembleia; o grupo informa, não autoriza.
- Dados reais só depois do termo assinado.

**D108 — Experiência do síndico no piloto (LB-080..LB-086)** (09/11/2026). O Marcio aprovou a proposta `docs/condoos-planning/launch/11-proposta-experiencia-piloto.md` com as recomendações: **Q-L07** sem prazo de conferência na tela (só "em conferência desde <data e hora>"); **Q-L08** o bloco de auditoria do Hoje continua no último mês fechado, com o nome do mês e a linha dos meses abertos com pontos pendentes; **Q-L09** nenhuma tela escondida do síndico; **Q-L10** esta fatia antes da LF6. Sem migração; a API só acrescenta campos.
- **Guia em passos (LB-080):** `GET /launch` devolve `progress` (passos do objetivo já cumpridos, de `steps.met`, sobre o total do objetivo). Passo que ainda não se aplica (notas antes de contrato) não conta como feito; passo adiado continua pendente. O cartão mostra um passo em foco ("Passo X de N") e os outros recolhidos; o passo de envio leva a `enviar?passo=<chave>`, que diz o que foi pedido. Depois de qualquer envio, "Continuar o guia" recarrega o Hoje (carga completa, nunca cópia em cache). Progresso nunca é permissão.
- **Em conferência (LB-081):** `GET /launch` devolve `in_review` (documentos sem revisão de pessoa, lendo ou esperando conferência; total, por tipo e os 5 mais antigos com a data). Contratos explica o contrato em conferência e, vazio, oferece "Enviar contrato".
- **Seu mês (LB-082):** `GET /launch/month` (`app/launch/month.py`), ativo só depois do LM3, sobre o mês anterior: documentos (cobertura de `month_pending`), decisões (só para quem pode decidir) e fechamento (só leitura). Item sem pendência some. Depois do LM3 o cartão de implantação vira uma linha e não pergunta mais o objetivo.
- **Hoje coerente (LB-083):** o resumo do mês diz "Último mês fechado: …" e `summary.later_waiting` traz os meses seguintes com pontos publicados. O briefing separa fonte que nunca recebeu nada (`not_started`, caixa "Começando", sem o aviso de parciais na frase) de fonte atrasada (continua "Dados parciais", D82); a frase não usa "(ões)" nem zeros. O link de volta de Enviar diz "Hoje".
- **Severidade (LB-084):** na lista, selo com texto e ícone; no detalhe, uma linha diz que severidade e valor em risco medem coisas diferentes.
- **Pergunte (LB-085):** `GET /chat/status`; o botão fixo só aparece quando o chat responde, e `/pergunte` sem modelo diz "Indisponível no momento".
- **Depois de decidir (LB-086):** antes do clique, o que Confirmar, Contestar e Ignorar fazem; depois, "Próximo ponto de atenção" (o publicado de maior valor) ou "Tudo decidido por enquanto", e "Voltar ao Hoje".
- Testes: `tests/test_pilot_experience.py` (6) e E2E em `launch.spec.ts` (condomínio novo criado pelo Admin CondoOS percorre o guia; condomínio em operação vê "Seu mês"), `findings.spec.ts`, `briefing.spec.ts` e `chat-reports.spec.ts`.

**D109 — LF6-a: troca de síndico, histórico das capacidades e rollback (LB-061, LB-064, LB-065)** (09/11/2026). O Marcio autorizou seguir para a LF6. Ela foi dividida como a LF2 e a LF3: **LF6-a** (este item, sem migração) e **LF6-b** (monitores diários com alertas internos, LB-060/LB-062, e Centro de Evolução, LB-063), que vai como proposta. O gate LG5 não tinha sido marcado como fechado (sobra só o LB-054, WhatsApp, que segue apenas especificado); a LF6 começou com essa pendência registrada.
- **Troca de síndico (LB-061, F06):** só o síndico aprova ações (`APPROVE_IN_CONDO`). Ao remover o acesso de um síndico, `actions.revalidate_approvals` devolve para aprovação toda ação aberta (enfileirada ou aguardando execução) aprovada por quem não é mais síndico: aprovação anulada, outbox cancelado, decisão `invalidar` com o motivo. O despacho e o registro de execução também conferem se quem aprovou ainda é síndico ativo (`approver_active`), o que cobre acesso vencido por data; a verificação diária faz o mesmo. A C7 ("Ações com sua aprovação") só fica operante com um síndico de acesso ativo que já entrou no CondoOS; sem ele, "análise parcial", inclusive num condomínio novo antes do primeiro acesso.
- **Histórico das capacidades (LB-064):** cada mudança de estado de C1..C9 vira uma linha `launch.capability_changed` no `audit_log` (só inclusão; estado antes e depois, o que falta e o motivo da verificação). Escolhido o `audit_log` em vez de tabela nova: é append-only, já tem condomínio e data, e dispensa migração. Grava na remoção e na inclusão de acesso, na pausa e na retomada das automações, no primeiro acesso de um síndico (job `launch.health` enfileirado pelo login) e na verificação diária do worker (`launch.health`, uma por dia). A primeira verificação grava o estado inicial; sem mudança, nada é gravado. `GET /launch/history`; Ajustes (síndico) e Configurações (equipe) mostram as 5 mudanças mais recentes.
- **Rollback (LB-065):** testado nos dois sentidos: a C7 cai quando a síndica sai e volta quando o novo síndico entra, com as duas mudanças no histórico; a pausa das automações já rebaixava a C7 (D83) e agora também entra no histórico.
- **Gate LG6:** troca de síndico (`tests/test_lf6_health.py`, e2e `health.spec.ts`); contrato substituído (`test_document_versions.py`, `test_data_issues.py::test_amendment_outside_the_term`); contato incorreto (`test_request_email.py`: envio que falha não vira sucesso); alteração bancária sempre negada (`test_actions.py`, `dados_bancarios.alterar`); credencial revogada (`test_access_revocation.py`, `test_access_model.py`); rollback (`test_lf6_health.py`).

**D110 — LF6-b: monitores diários, alertas internos e Centro de Evolução (LB-060, LB-062, LB-063)** (09/11/2026). O Marcio aprovou a proposta `docs/condoos-planning/launch/12-lf6b-proposta-monitores.md` com as recomendações: **Q-L11** alertas guardados em `data_issue` com tipos novos e a coluna `audiencia` (migração 0024, aprovada); **Q-L12** alertas `equipe` vistos pela equipe CondoOS e pela gerência (`VIEW_PENDING_FINDINGS`), o síndico só vê os `condominio`; **Q-L13** canal parado em 35 dias, acesso vencendo e ação parada em 7 dias; **Q-L14** Centro de Evolução para síndico e equipe, no máximo 3 sugestões.
- **Monitores (LB-060):** `app/data_issues/monitors.py`, rodados pela verificação diária `launch.health` (D109) e na verificação disparada pelo primeiro acesso de um síndico. Detectores versionados: `canal_parado_v1`, `contrato_aditado_v1` (aditivo que muda valor, fim ou escopo com efeito entre 45 dias atrás e 30 dias à frente), `revisor_ausente_v1` (sem administradora e sem revisora CondoOS ativa), `sindico_sem_acesso_v1` (nenhum síndico com acesso ativo, ou acesso terminando em até 7 dias) e `acao_parada_v1` (audiência `condominio`). O seed não abre nenhum alerta (teste).
- **Alertas (LB-062):** a conciliação de `data_issue` virou `reconcile(..., kinds)`, usada pelos conflitos (D93) e pelos alertas, cada um no seu escopo: um não supera o outro. Alertas não têm capacidade nem fornecedor, e `open_issues`, a política e o quadro de pedidos leem só conflitos: **alerta nunca deixa função parcial nem recusa ação**. Resolver um alerta registra o que foi feito, sem escolher lado; conflito continua exigindo o lado. Alerta `equipe` responde 404 para quem não é da equipe ou da gerência. Central de Validação com a seção "Alertas de saúde"; Carteira com a coluna "Alertas"; Configurações com o atalho; Ajustes do síndico mostra os alertas `condominio`.
- **Centro de Evolução (LB-063):** `app/launch/evolution.py`, calculado a cada leitura, sem tabela: contrato faltando (fornecedor que cobrou em 2 meses ou mais sem contrato), usar o e-mail de entrada (3 envios à mão em 60 dias e nenhum por e-mail), enviar o pedido pelo CondoOS (3 pedidos compartilhados à mão, só com SMTP), extrato (despesas de 2 meses sem extrato) e alçada (ação com custo pedida sem alçada). "Agora não" guarda `evo:<sinal>` em `launch_state.postponed` por 30 dias. `GET /launch/evolution`; cartão "Para evoluir" em Ajustes e Configurações.
- **Migração 0024:** amplia os tipos de `data_issue` e acrescenta `audiencia` (padrão `condominio`; o que já existia não muda). A volta remove os alertas, os eventos e os vínculos deles e restaura a regra anterior; ida e volta verificadas no banco local (os 25 conflitos ficaram).
- Testes: `tests/test_lf6b_monitors.py` (7) e e2e `health.spec.ts` (a equipe vê e trata o alerta; a síndica não o vê).

**D111 — O resumo do dia acompanha os registros novos** (09/11/2026). O ensaio do teste de ponta a ponta (`docs/pilot/teste-ponta-a-ponta.md`) mostrou o resumo do dia dizendo "Ainda não recebemos documentos" depois que a administradora enviou 7 arquivos, até a síndica tocar em "Atualizar". Pedido do Marcio: corrigir. Ao abrir o Hoje, se algum registro de que o resumo é feito (documentos, despesas, extrato, achados, assuntos, tarefas, ações, oportunidades e pedidos de documentos) foi criado ou mudou depois da última versão do dia, o resumo é refeito como **versão nova** (`briefing.changed_since`, uma consulta por tabela, para no primeiro registro novo). Sem mudança, continua a mesma versão. A regra da D82 fica: um resumo por pessoa, condomínio e dia, versionado, e "Atualizar" continua criando versão nova. Teste: `test_briefing.py::test_briefing_follows_new_records_without_refresh`.

**D112 — Conformidade e vencimentos, primeiro corte (FR-057, WP-16)** (09/11/2026; proposta `docs/proposta-conformidade.md` e migração 0025 aprovadas pelo Marcio no mesmo dia: corte e migração sim; periodicidade sugerida marcada "confirme com o responsável técnico"; síndico e gerente da administradora validam; **a IA já sugere as datas do documento**, sempre "a confirmar"; aviso padrão de 60 dias).
- **Modelo (0025, RLS):** `compliance_obligation` (aplicabilidade `a_validar`/`aplicavel`/`nao_aplicavel` com quem, quando e motivo; periodicidade só depois de validada; antecedência; responsável; arquivar em vez de apagar), `compliance_evidence` e `compliance_event` (só inclusão; a evidência mais recente vale).
- **Catálogo** (`app/compliance/catalog.py`): 14 candidatas comuns (AVCB/CLCB, seguro, extintores, hidrantes, SPDA, elevadores, caixa d'água, potabilidade, pragas, gás, elétrica, inspeção predial, bombas e gerador). Não cita norma nem afirma que se aplica (Plano D-10): tudo entra "a validar" e só gera aviso depois que uma pessoa confirma. Periodicidade nula quando varia demais para sugerir (AVCB, gás, elétrica, inspeção predial).
- **Situação calculada a cada leitura** (`status.py`): vencido, vence em breve (dentro da antecedência), sem documento, sem validade, lendo, a validar, em dia, não se aplica, arquivada. Validade = a do documento, ou emissão + periodicidade validada ("calculada"). Textos sem "irregular", "conforme" ou "em conformidade"; ausência de registro é "Nenhum documento registrado no CondoOS", nunca "não cumprida".
- **Leitura pela IA** (job `compliance.read_validity`, prompt `compliance_validity.md` com a regra de conteúdo não confiável): ao ligar um documento sem datas, o modelo lê emissão e validade; **uma data só fica se estiver escrita no texto** (sem texto, foto ou PDF escaneado vão como anexo); sem modelo ou sem data aceita, uma leitura por padrões ("vigência de … a …", "válido até", "emissão"). O resultado é uma linha nova "a confirmar"; a pessoa confirma ou corrige (linha nova "pessoa"). Se alguém digitou as datas enquanto a leitura esperava, a leitura não muda nada.
- **Onde aparece:** tela Conformidade (celular, a partir de Ajustes; desktop, menu lateral com filtro de condomínio); Agenda (tipo "validade": vencimento e "começar a renovação" na data da antecedência); Hoje (riscos: vencido ou vence em até 30 dias); chat (`list_compliance`, citação "obrigação", regra 7 do prompt; caso `conformidade-seguro` na avaliação). Atalhos "Pedir documento" (pedido de D95 já preenchido) e "Criar assunto de renovação" (D80). Nada é enviado para fora.
- **Permissões:** `manage_compliance` (síndico, gerente, analista, Admin CondoOS) e `validate_compliance` (síndico e gerente). Conselheiro só vê.
- **Seed:** Jardim das Acácias com o catálogo ativo, seguro vencendo em 45 dias, AVCB em dia e extintores sem documento (datas relativas a hoje).
- Fora do corte: perfil da edificação que sugere obrigações (CAP-08.01), dossiê por obrigação (CAP-08.06), lembrete por e-mail ou WhatsApp, ordens de serviço.
- Verificação: `test_compliance.py` (5), prompt no `test_prompt_injection.py`, 378 testes do backend, lint, migração ida e volta, E2E `compliance.spec.ts` (celular e desktop) e os fluxos de agenda, pedidos, assuntos e Hoje numa stack local sem Docker.

**D113 — Conformidade: perfil do prédio, dossiê e resumo semanal por e-mail** (09/11/2026; pedido do Marcio "faça os itens que ficaram para depois"; migração 0026 e o novo envio aprovados por ele no mesmo dia: "Aprovar migração 0026" e "Sim, só para o síndico").
- **Perfil do prédio** (CAP-08.01; `condominium.building_profile`, `compliance/profile.py`): andares, elevadores, gás encanado, gerador, bombas, caixa d'água, hidrantes, para-raios e piscina; "não informado" é a ausência do campo. Cada item do catálogo diz de quais campos depende (`needs`); para obrigação ainda "a validar", o sistema mostra "provavelmente se aplica" ou "provavelmente não se aplica". **Nunca valida sozinho.** Mudança gravada em `audit_log` (`condominium.building_profile_changed`, só os nomes dos campos). Catálogo ganhou "Tratamento e análise da água da piscina" (15 itens).
- **Dossiê em PDF por obrigação** (CAP-08.06; `GET …/compliance/{id}/dossier.pdf`, permissão EXPORT, auditado como `compliance.dossier_exported`): situação, quem decidiu que se aplica, quando e por quê, periodicidade, aviso, responsável, documentos e datas com a origem de cada data (pessoa, IA ou texto, "a confirmar"), histórico. "Base normativa: não informada pelo CondoOS". Rodapé em todas as páginas: "não é laudo nem parecer técnico ou jurídico".
- **Resumo semanal por e-mail** (segundo envio externo do sistema, depois de D103): `condominium.compliance_email_enabled` desligado até o síndico ligar (permissão `configure_compliance_email`, só síndico; auditado). Job `compliance.reminders` agendado a cada hora; envia na segunda-feira a partir das 8h no fuso do condomínio, só aos síndicos com vínculo ativo, só se houver documento vencido ou vencendo em até 30 dias; texto com nome da obrigação, situação e data, aviso de que não é parecer e o link; sem valores. No máximo um por síndico por semana (`compliance_reminder`, RLS, só inclusão, sem endereço nem conteúdo); recusa do servidor fica registrada como "falhou" e volta na semana seguinte. Pausa `conformidade.lembrete_email` no kill switch. "Enviado" é aceito pelo servidor, nunca "entregue".
- Verificação: `test_compliance.py` (8 no total), 381 testes do backend, lint, migração 0026 ida e volta, E2E `compliance.spec.ts` (perfil, resumo, dossiê) e `launch.spec.ts` numa stack local sem Docker.

**D114 — Lista de achados no desktop** (09/11/2026; o Marcio viu 5 achados no cartão "Achados abertos" da Carteira e não achou onde analisá-los). O desktop só chegava a um achado pela Fila de exceções (os aguardando validação), pelo Hoje ou pelo chat; a linha do condomínio na Carteira abre a tela do síndico. Nova página `/admin/achados` (item "Achados" no menu lateral e link "ver achados" no cartão da Carteira): achados de todos os condomínios da pessoa ou de um só (filtro de condomínio), por situação (sem filtro: os abertos, os mesmos do cartão: aguardando validação, novos e contestados) e gravidade, ordenados por valor em risco; cada linha abre o detalhe já existente (`/admin/achados/{condomínio}/{achado}`), com as ações que o papel permite. Usa a rota existente `GET /condominiums/{id}/findings` (visibilidade por papel mantida). Sem mudança no backend. E2E em `findings.spec.ts`.

**D115 — Menu organizado por propósito** (09/11/2026; proposta `docs/proposta-menu.md`, as 5 decisões aprovadas pelo Marcio). Só telas, sem mudança de banco nem de API; os endereços continuam os mesmos.
- **Desktop** (`AdminNav`): topo (Hoje, Carteira, Agenda) e grupos com título: **Gestão financeira** (Achados, Aprovações, Oportunidades, Pendências, Relatórios), **Gestão operacional** (Assuntos, Conformidade, Pedidos de documentos), **Contratos e documentos** (Contratos, Fornecedores, Enviar documentos), **Qualidade dos dados** (Fila de exceções, Conflitos de dados), **Cadastro e configurações** (Dados do condomínio, Métricas do piloto). Cada pessoa vê só o que o papel usa, pela união das permissões dos seus condomínios (ex.: a revisora não vê "Dados do condomínio"; Métricas só para a equipe CondoOS); a página continua recusando quem não pode. Desvio da proposta, decidido pelo Claude: a **Carteira fica para todos no desktop** (é a página inicial da equipe e onde o Admin cadastra condomínio, mesmo com um só).
- **Renomeados:** "Validação" → **Conflitos de dados** (título "Central de Validação" também); "Configurações" → **Dados do condomínio**; "Pedidos" → **Pedidos de documentos**.
- **Relatórios** (novo, `/admin/relatorios`): relatórios mensais (fechados e prévia do mês aberto, PDF e XLSX), trilha de decisões e dossiês de conformidade das obrigações confirmadas, por condomínio.
- **Celular do síndico:** 4 abas — **Hoje**, **Finanças** (Achados, Aprovações, Oportunidades, Relatórios), **Rotina** (Assuntos, Agenda, Conformidade, Pedidos), **Documentos** (Contratos, Enviar documentos) — com o seletor de seções no topo das telas de lista (`SectionNav`, definição em `lib/sindicoNav.ts`). Correção da proposta: a antiga aba "Histórico" não mostrava despesas, e sim a trilha de decisões e os relatórios; virou **Relatórios** dentro de Finanças. Ajustes segue na engrenagem do topo; o atalho para Conformidade em Ajustes saiu (agora está na aba Rotina). As 13 telas do síndico ficam a no máximo dois toques.
- Testes de ponta a ponta atualizados para os nomes novos. Na stack local sem Docker, 36 passaram na rodada completa; das falhas, uma era o teste de login (corrigido), uma o clique na linha da tabela (corrigido: só a primeira célula é link), `correction.spec.ts` falha igual sem esta mudança (efeito da stack local, D96) e `opportunities.spec.ts` depende de seed recém-carregado (`make reset`). **Confirmado no Docker do Marcio em 09/11/2026 (`make reset && make up && make e2e`): 36 passaram, nenhuma falha.** Antes disso, uma rodada falhou inteira porque o `.env` do Mac ainda apontava o SMTP para a Amazon (os links de acesso iam para `@example.com` pelo SES); as linhas de SMTP, remetente e domínio de entrada saíram do `.env` local, e a reputação da conta no SES seguiu íntegra (0% de devolução e de reclamação).

**D116 — Correção do SSH do servidor** (09/11/2026). Um `ssh` de teste pediu senha no servidor de produção: o `setup-server.sh` gravava a proibição de senha em `/etc/ssh/sshd_config.d/90-condoos.conf`, mas o sshd fica com o **primeiro** valor que lê, e a imagem da Hostinger traz um arquivo anterior na ordem (ex.: `50-cloud-init.conf`) com `PasswordAuthentication yes`. Corrigido no servidor (arquivo renomeado para `00-condoos.conf`, conferido com `sshd -T`) e no script, que agora usa `00-` e falha se senha ou root ainda forem aceitos. Login por chave não foi afetado.

**D117 — Grupos do menu mais visíveis** (09/11/2026; o Marcio achou que os títulos se confundiam com os itens). Título do grupo em branco e negrito (antes cinza), linha separando cada grupo e itens recuados com uma linha vertical à esquerda ligando-os ao título; itens dos grupos em 13 px para "Pedidos de documentos" e "Cadastro e configurações" caberem numa linha na largura de 232 px do Design System. Só `AdminNav`, sem cor nova.

**D118 — Junção de dois branches paralelos** (09/11/2026). Duas sessões trabalharam ao mesmo tempo a partir do mesmo ponto (`5f0bba7`): `claude/dazzling-euler-ja9ojc` (experiência do síndico no piloto, LF6-a, LF6-b, resumo do dia e roteiro do teste de ponta a ponta) e `claude/exciting-gauss-d4lrhc` (conformidade, lista de achados no desktop, menu por propósito e correção do SSH). O servidor de produção foi trocado para o primeiro e o menu "voltou". Para juntar sem perder nada: as decisões deste branch foram **renumeradas de D108–D113 para D112–D117** (as do outro ficam D108–D111) e as migrações deste branch passaram de 0024/0025 para **0025 (conformidade) e 0026 (perfil e resumo semanal)**, depois da 0024 do outro (alertas de saúde). Os textos das decisões citam o número novo; o Marcio aprovou as migrações quando ainda se chamavam 0024 e 0025. Conflitos resolvidos mantendo os dois lados (enums, jobs diários, layout do celular com o seletor de seções e o botão do chat só quando ele responde). Daqui em diante, um branch só: `claude/exciting-gauss-d4lrhc`.

**D119 — CNPJ do condomínio conferido na Receita antes do cadastro** (09/11/2026; pedido do Marcio). No "Novo condomínio", quando o CNPJ fica completo, a tela consulta a Receita pela mesma BrasilAPI dos fornecedores (`GET /portfolio/cnpj/{cnpj}`, só para quem pode cadastrar condomínio: gerente da administradora ou Admin CondoOS; até 30 consultas a cada 10 minutos por pessoa; nada é gravado) e mostra razão social, nome fantasia, situação com a data, natureza jurídica e endereço, com atalhos "Usar como nome" e "Usar o endereço". Avisa, sem bloquear, quando a situação não é "ATIVA" e quando a natureza jurídica não é "Condomínio Edilício" (código 308-5), para pegar o CNPJ da administradora ou de um fornecedor digitado por engano. Com a Receita fora do ar, diz isso e o cadastro continua. `SupplierRecord` passou a trazer natureza jurídica e endereço (não gravados). Os testes do backend agora rodam com `SUPPLIER_PROVIDER=offline` (antes um teste podia consultar a Receita de verdade); o e2e simula a resposta da Receita no navegador. Testes: `test_cnpj_lookup.py` (2), e2e em `condoos-staff.spec.ts`.

**D120 — Correções na leitura e na conferência de documentos** (10/11/2026; proposta `docs/proposta-correcoes-leitura.md`, decisões do Marcio: "1 sim 2 sim 3 sim 4 sim 5 recusar"; migração 0027 aprovada). Origem: os testes do Marcio com contratos, comprovantes e notas. Os casos foram reproduzidos com documentos fictícios; os documentos dele não entram no repositório.
- **A1 — Confiança por evidência** (`extraction/evidence.py`): um campo lido abaixo de 0,9 sobe para 0,95 só com prova conferida por código: (1) **o valor está escrito no texto** (CNPJ, valor, data, competência, índice IPCA/IGP-M/INPC, texto de 8+ caracteres, cada item do escopo) e a IA deu pelo menos 0,6 (abaixo disso, estar escrito em algum lugar não basta: um contrato tem vários valores e datas); (2) **a razão social confere com a da Receita** para o CNPJ lido (sem acento, pontuação e sufixo LTDA/ME/S.A.; confirma os dois campos); (3) **o CNPJ do condomínio é o do cadastro**. Campo com problema de validação nunca sobe. A Receita vem do cadastro de fornecedores (fonte Receita ou seed, nunca "documento") e, se faltar, da BrasilAPI, guardando o resultado; falha só significa "sem prova". A prova fica na proveniência (`evidence`) e aparece na tela de correção. Sem prova, a regra dos 0,9 continua.
- **A2 — Tela de correção** (`ReviewForm`): campos em três grupos — "A conferir" (obrigatórios abaixo do limite, cada um com "Por que conferir"), "Lidos com confiança" e "Opcionais" (vazio aparece "opcional, não encontrado", sem a cor de alerta).
- **A3 — CNPJ procurado no texto**: em contrato sem CNPJ da contratada, todos os CNPJs válidos do texto, menos o do condomínio, o da administradora e o do contratante; se sobrar um só, ele entra como sugestão (0,5, "sugerido do texto, confira") e só fica confirmado se a razão social conferir na Receita. Se o texto (camada de texto boa, não foto) **não tem nenhum** outro CNPJ, o contrato não fica preso por isso (B2).
- **A4 — Mesma nota em outro arquivo** (`matching/documents.py`): número comparado sem série e sem zeros à esquerda (com letras, como está escrito); número faltando em uma das cópias → mesmo fornecedor, valor e data de emissão (só despesa criada por nota); texto igual (200+ caracteres, sem espaços) → mesmo documento. A cópia entra na mesma despesa com o papel **`copia`**, sem despesa nova e sem alerta de duplicidade; o cartão de primeiro valor diz "cópia da nota já recebida".
- **A5 — Assinatura depois do início**: observação na proveniência de `data_assinatura`, no cartão e no alerta (B1); não trava.
- **B1 — Alertas de contrato** (`data_issues/contracts.py`, detector `contrato_leitura_v1`, tipos `contrato_assinado_depois`, `contrato_contratante`, `contrato_cnpj_condominio`, `contrato_sem_cnpj`): guardam o que estava escrito (o valor original vem de `extraction_correction`, mesmo depois de a pessoa corrigir o cadastro). Contratante = administradora (ou empresa que a Receita mostra não ser condomínio) → "o contratante não é o condomínio"; outro CNPJ → "CNPJ do condomínio errado no contrato". Não bloqueiam nada (sem capacidades, como os alertas de D110), rodam ao cadastrar o contrato e no job diário, somem como "superado" quando a condição some e ninguém agiu. Na Central de Validação (seção "Alertas de contrato") e em Ajustes do síndico, com "Pedir correção do contrato" (pedido de documentos já preenchido) e "Criar assunto".
- **B2 — Contrato sem CNPJ da contratada**: cadastrado pela razão social (`contract.supplier_id` vazio, `supplier_name`). Se o valor (mensal, ou total do pontual) passa da alçada do síndico vigente para a categoria (mesma regra da R12) **ou** o serviço é essencial (portaria, limpeza, elevadores, segurança, manutenção predial, seguro), o sistema abre o assunto **"Ajustar contrato: incluir o CNPJ da contratada"** para o síndico ativo, com prazo de 30 dias e ligado ao contrato (um por contrato). Nos outros casos, só o alerta. A primeira nota de um fornecedor com a mesma razão social preenche o CNPJ do contrato. Na correção, a pessoa pode salvar contrato sem CNPJ se a razão social estiver preenchida.
- **B3 — Contrato pontual × contínuo**: campos novos `natureza`, `valor_total` e `parcelas` (prompt do contrato atualizado). Sem natureza lida: valor total sem mensal = pontual; senão contínuo (presumido, aparece como "inferido"). Pontual exige o valor total, não pede índice nem mês de reajuste, entra com `billing_frequency_months = 0` (nenhuma "NF não recebida") e mostra "faturado até agora" contra o total nas telas de contratos (`billed_totals`). Valores mensais nas regras, agenda, pendências, chat e relatório tratam o pontual sem valor mensal.
- **B4 — Tipos novos**: `comprovante` (data, valor, **beneficiário final**, documento dele, banco pagador, autenticação, código pago; liga à despesa pelo código de barras ou pelo beneficiário, valor e data com o papel `pagamento`; nunca vira despesa), `guia_tributo` (tributo, competência, vencimento, valor, código de barras; vira despesa "tributos" sem fornecedor, isenta da alçada da R12; a mesma guia de novo é cópia), `relatorio_adm` e `extrato_rendimento` (só texto, pesquisáveis no chat). Classificação por título antes do boleto (comprovante e guia também têm código de barras) e pela IA (lista de tipos do prompt atualizada).
- **B5 — Relação de devedores recusada**: reconhecida pelo título ("relação de devedores/inadimplentes") ou por "inadimplência" com uma lista de unidades (5+), nunca num balancete. O arquivo é apagado do armazenamento, nada lido fica guardado, o documento fica como "recusado" com a explicação e o fato vai para o `audit_log` (`document.refused`).
- **Migração 0027**: tipos de documento, papéis `copia`/`pagamento`, os 4 tipos de alerta e, em `contract`, `nature`, `supplier_name`, `total_value`, `installments`, `supplier_id` e `monthly_value` opcionais com CHECKs (fornecedor ou razão social; mensal no contínuo, total no pontual). A volta recusa rodar enquanto existir contrato pontual ou sem fornecedor.
- **Efeito medido sem o modelo** (corpus, leitura só do texto, sem as gravações da IA neste ambiente): 11/30 → 13/30 documentos sem revisão. Os prompts de contrato e de classificação mudaram: as respostas gravadas no Mac do Marcio para esses dois pedidos deixam de valer; para refazer a medição completa, `LLM_MODE=record make accuracy` (centavos).
- Verificação: `test_reading_evidence.py` (10), `test_reading_fixes.py` (15), R12 com tributos (positivo e negativo), 425+ testes do backend, lint e tipos (backend e web). Ponta a ponta não rodado neste ambiente.
