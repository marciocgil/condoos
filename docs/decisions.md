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

## Reconcepção do produto (análise em `docs/reconcepcao/`)

**D88 — Beachhead e condução da reconcepção.** Em 11/11/2026 o Marcio respondeu à Fase 1 (`docs/reconcepcao/fase-1-mercado-personas-dores.md`): (1) primeiro comprador a validar é o síndico profissional em São Paulo capital, com carteira de 5 ou mais condomínios e despesa média acima de R$ 1 milhão/ano; (2) D73 fica mantida: o condomínio é o cliente e a administradora é fonte de dados e canal a testar, sem venda do auditor a ela; (3) as fases seguintes avançam com as premissas, e a validação em campo (entrevistas e medição da taxa de achados em pastas reais) corre em paralelo. Os documentos de `docs/reconcepcao/` são análise: não mudam roadmap nem código, e as divergências que listam (R1 em diante) só valem depois de decididas aqui.

**D89 — Categoria, monetização e ambição (respostas à Fase 2).** Em 11/11/2026 o Marcio aceitou, como hipóteses de trabalho de `docs/reconcepcao/fase-2-posicionamento-estrategia.md`: (1) posicionamento de entrada "controladoria independente do condomínio", com "assessor inteligente" (Especificação Mestra §1.2) como visão de longo prazo; (2) assinatura por condomínio em faixas de despesa, mais taxa só sobre economia realizada em renegociação (medida por D84/D87), com proibição permanente de receita de fornecedor; os valores continuam hipótese a testar e o preço só fecha depois de medido o valor (Plano D-12); (3) a ambição é um negócio próprio e rentável no nicho, não uma tese para captação, então o foco é o beachhead de D88.

**D90 — Marca: finalistas de nome, voz do agente e direção visual (respostas à Fase 3).** Em 11/11/2026 o Marcio decidiu, sobre `docs/reconcepcao/fase-3-marca.md`: (1) os nomes a testar nas entrevistas contra "CondoOS" são Confere, Ciente e Lastro (Ciente, proposto por ele, entra no lugar de Prumo); o nome só muda com vitória clara no teste e checagem no INPI; (2) o agente não tem nome próprio nem persona humana e fala como a marca; (3) a direção visual segue as duas imagens de referência guardadas em `docs/reconcepcao/referencias/` (telas de terceiros, só referência): tema escuro mais profundo, acento verde-esmeralda no lugar do verde-lima, documento original em claro dentro da interface escura. **Nada foi alterado no código:** os tokens de `web/app/globals.css` e o Design System v1.0 continuam valendo até a troca ser planejada e ter o contraste conferido; ponto de atenção registrado: o esmeralda fica perto de `--color-success`.

**D91 — Direção da experiência (respostas à Fase 4).** Em 11/11/2026 o Marcio aceitou, como direção de `docs/reconcepcao/fase-4-experiencia.md`: (1) reduzir o aplicativo do síndico a quatro destinos (Hoje, Registros, Histórico, Enviar), com as demais seções virando filtro ou pergunta; (2) WhatsApp só para resumo do dia e captura de documento, sem aprovação, a testar depois dos primeiros clientes, o que exigirá rever D82 quando chegar a hora; (3) voz adiada, análise sob demanda só por componentes fixos preenchidos com números conferidos por código, e nenhuma autonomia para ação externa além do que D83 já permite. **É direção, não execução:** nenhuma tela mudou; cada item entra em fatia própria, com teste com usuários antes de consolidar a navegação.
