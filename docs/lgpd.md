# Checklist LGPD — CondoOS (piloto)

Mapeia cada requisito de privacidade (seção 12 da especificação e boas práticas da LGPD) ao que o sistema faz hoje, com o lugar no código ou o teste que comprova. "Pendente" indica o que depende da administradora ou fica para depois do piloto.

## Dados tratados

| Categoria | Exemplos | Base legal sugerida (a confirmar com o jurídico) |
|---|---|---|
| Usuários do sistema | nome e e-mail de síndicos, conselheiros e equipe da administradora | execução de contrato (art. 7º, V) |
| Corpo diretivo | nome, cargo e mandato | legítimo interesse / obrigação da convenção |
| Fornecedores (PJ) | CNPJ, razão social, situação cadastral, CNAE | dados públicos da Receita (BrasilAPI) |
| Sócios de fornecedores | nome e CPF **sempre mascarado** (`***.456.789-**`) | dados públicos; uso só para a regra R08 (conflito de interesses) |
| Documentos financeiros | notas, boletos, recibos, extratos, contratos, convenção e atas | obrigação legal de prestação de contas do síndico |

**Moradores:** o MVP não guarda dados de moradores. A receita de condomínio entra só como lançamento agregado do extrato, sem nome de unidade.

## Checklist

| # | Item | Status | Onde |
|---|---|---|---|
| 1 | Isolamento entre condomínios: toda rota filtra por `condominium_id` e o RLS do PostgreSQL filtra de novo | ✅ | `app/db/models.py` (`RLS_TABLES`), migrações; `tests/test_isolation.py` |
| 2 | Isolamento entre administradoras | ✅ | `app_accessible_condominium_ids`; `tests/test_isolation.py`, `tests/test_rbac.py` |
| 3 | Outro condomínio responde 404 (nada é revelado) | ✅ | rotas; testes de chat, achados e relatórios |
| 4 | RBAC por papel em toda rota | ✅ | `app/auth/rbac.py`, `require(Permission.X)` |
| 5 | CPF sempre mascarado na interface, no chat e nos relatórios | ✅ | `app/core/br.py` (`mask_cpf`); o seed e o enriquecimento guardam só o CPF mascarado; `get_supplier` do chat devolve o mascarado |
| 6 | Sem dados de moradores | ✅ | nenhuma tabela com unidade ou morador |
| 7 | Arquivos com chave por condomínio | ✅ | `cond/<condominium_id>/...` (`app/storage`) |
| 8 | URLs pré-assinadas de curta duração | ✅ | `S3_PRESIGN_TTL_SECONDS=300` |
| 9 | `audit_log` de login, upload, configuração, decisão e exportação | ✅ | ações `auth.login`, `auth.logout`, `auth.magic_link_requested`, `document.uploaded`, `document.reviewed`, `document.discarded`, `match_issue.resolved`, `settings.updated`, `finding.decision`, `report.exported`, `decisions.exported`, `competence.closed`, `condominium.onboarded`, `retention.purged` |
| 10 | `decision` e `audit_log` só aceitam inclusão | ✅ | permissões do papel da aplicação (sem UPDATE/DELETE) |
| 11 | Retenção configurável (padrão 5 anos para documentos fiscais) | ✅ | `condominium.retention_years` (mínimo 5); job diário `retention.purge` (`app/core/retention.py`); `tests/test_retention.py` |
| 12 | Nenhum dado de cliente nos logs (só IDs) | ✅ | convenção do código; logs do chat e do worker usam só IDs e contagens |
| 13 | Envio à Anthropic só do necessário | ✅ | ver "Dados enviados à IA" abaixo |
| 14 | Embeddings dos documentos sem terceiros | ✅ | modelo local na imagem (D52) |
| 15 | Segredos só por variável de ambiente | ✅ | `.env.example`; nada de chave no repositório |
| 16 | Link mágico de uso único e curta duração; limite por hora | ✅ | 15 min, uso único, limite por e-mail/hora (`app/auth/service.py`) |
| 17 | Cookie de sessão seguro em produção | ⚠️ configurar | `SESSION_COOKIE_SECURE=true` atrás de HTTPS (ver `docs/deploy.md`) |
| 18 | Linguagem dos achados sem acusação ("indício", nunca "fraude") | ✅ | motor recusa; chat e explicações verificados por código |
| 19 | Pessoa sempre decide; sistema não move dinheiro | ✅ | nenhuma integração de pagamento; chat só lê |
| 20 | Relatórios com aviso de IA em toda página | ✅ | `app/reports/pdf.py`; teste por página |
| 21 | Registro das operações de tratamento (ROPA) | ⏳ pendente | a administradora preenche com o modelo da tabela "Dados tratados" |
| 22 | Acordo de tratamento de dados entre o condomínio (controlador) e o fornecedor do CondoOS (operador), com a lista de subprocessadores (Hostinger, AWS, Anthropic) e a transferência internacional para a IA | ⏳ minuta pronta, revisão jurídica e assinatura pendentes | D107; a administradora já é operadora do condomínio e não assina com o CondoOS; subprocessadores pelos termos padrão de cada um |
| 23 | Canal do titular (acesso, correção, exclusão) | ⏳ pendente | hoje por solicitação à administradora; usuários são desativados por `app_user.is_active` |
| 24 | Relatório de impacto (RIPD) antes do uso em escala | ⏳ pendente | após o piloto |
| 25 | Revisão da licença do executável embutido no Agent SDK | ✅ exceção aceita | D107 |
| 27 | E-mail do pedido enviado pelo CondoOS (D103) | ✅ | só com aprovação do síndico; endereço do destinatário mascarado depois do envio (fica o SHA-256); pedido guarda só o domínio; texto sem valores nem dados financeiros; "responder para" é o e-mail do síndico, com o consentimento dado na D103 |
| 28 | Resumo semanal de vencimentos por e-mail (D109) | ✅ | só para o síndico do próprio condomínio, desligado até ele ligar; só nome da obrigação, data e link (sem valores nem dados de terceiros); registro do envio só com ids, semana e contagem; pausa no kill switch |
| 26 | E-mail de entrada com dados no Brasil e registro mínimo | ✅ | SES e bucket em São Paulo; `inbound_message` guarda só o domínio do remetente e contagens (sem assunto, corpo ou endereço completo); mensagens apagadas do bucket de entrada em 30 dias; endereço com parte aleatória que o síndico pode trocar (D101) |

## Dados enviados à IA (Anthropic)

| Tarefa | O que vai | O que não vai |
|---|---|---|
| Classificação e extração (`app/extraction`) | o texto do documento; o arquivo só quando não há texto (foto, PDF escaneado) | dados de outros documentos e do condomínio |
| Explicação do achado (`app/findings/explain.py`) | dados da regra e rótulos das evidências | documentos inteiros |
| Regras R04 e R07 (`app/rules/judge.py`) | descrição da despesa, objeto e escopo do contrato, CNAE | valores de outras despesas |
| Chat (`app/chat`) | a pergunta, as 6 últimas mensagens do mesmo usuário e o que as ferramentas devolvem (só deste condomínio, com CPF mascarado) | dados de outros condomínios; nada é gravado pela ferramenta |

Toda chamada é registrada em `llm_calls` (finalidade, modelo, tokens, custo), sem o conteúdo, e respeita o limite mensal de custo por condomínio.
