# CondoOS Audit — diagnóstico e plano de implementação

Data: 11/11/2026. Base: "CondoOS Audit — Prompt Mestre de Implementação v1.0" (enviado pelo Marcio) e o código do branch `claude/exciting-gauss-d4lrhc`.

## 1. Diagnóstico: o que já existe × o que o documento pede

| Req. | Pedido no documento | O que já existe no CondoOS | Lacuna |
|---|---|---|---|
| 1 | Produto Audit reutilizável por Optimize/Operate, motor único | Auditor de despesas (12 regras R01–R12, achados), Optimize (oportunidades), Operate parcial (ações com política, D83) | Farol mensal de 25 controles e execução por competência |
| 2 Etapa 0 | Implantação guiada com contas, fundos, unidades, orçamento | Launch (D88/D89: marcos, prontidão), cadastro de condomínio, corpo diretivo, contratos, alçadas versionadas (D85), conformidade (D112) | **Contas bancárias, fundos, orçamento, plano de contas**; unidades (ver conflito C2) |
| 2 Etapa 1 (A1) | Recepção, hash, duplicatas, versões, inventário, checklist | Upload/e-mail/link (D95, D101), SHA-256 e versões (D85), triagem (D95), classificação, cópias de nota (D120) | Inventário por competência e checklist esperado |
| 2 Etapa 2 (A2) | Fatos com página/trecho, método, confiança | `document.extracted` + `field_provenance` (origem, página, trecho, prova, D85/D120) | Registro **imutável** de fatos (`audit_fact`) com versão do extrator e vigência |
| 2 Etapa 3 (A3) | Vínculos documento→fato→entidade→obrigação→pagamento, sugerido × verificado | Casamento documento→despesa→contrato, despesa↔extrato, fila de ambiguidades (`match_issue`) | Grafo explícito (`evidence_edge`) com sugerido × verificado |
| 2 Etapa 4 (A4) | Conciliação por conta, saldos, continuidade, estornos | Importação OFX/CSV/CNAB idempotente; casamento débito↔despesa | **Conta bancária e saldos não são lidos**; sem estornos, sem níveis (a)–(e) |
| 2 Etapas 5–6 | Arrecadação, despesas/fiscal, contratos, fundos | R01–R12, contratos com reajuste (D66/D68), comprovante e guia (D120), pendências (D70) | Receitas, títulos, fundos, orçamento, parcelamentos |
| 2 Etapas 7–8 (A9/A0) | Revisão adversarial, política de status, publicação | Revisão proporcional ao risco (D74), Central de Validação (D93) | Seis estados do farol, revisão por controle, publicação versionada |
| 3 | Agentes A0–A9, `run_id`, versão do prompt, hash | Cliente LLM único com `llm_calls` e `prompt_sha256` (D121) | Execuções por agente e registro de prompts versionados |
| 4 | Registro de fatos e evidências | Documento, despesa, extrato, contrato, proveniência | Tabelas de auditoria (ver seção 3) |
| 5–6 | 25 controles, seis estados | — | Tudo |
| 7 | Dependências e reprocessamento seletivo | Jobs idempotentes, superação de achados (D61) | Grafo de dependências e reuso por impressão digital das entradas |
| 8 | Agentes & Prompts: texto integral, versões, diff, teste, aprovação, rollback | Tela "Regras e prompts" só leitura (D121) | Gestão versionada no banco, com governança |
| 9 | Telas Audit | Design System v1.0, menu por propósito (D115) | Farol, execução, conciliação, controle, revisão, agentes |
| 10 | APIs, eventos, papéis, LGPD | RBAC, RLS, `audit_log` só inclusão, fila com dedupe | Permissões de auditoria e de prompts |
| 11 | Cálculo determinístico, níveis de conciliação | `Decimal` (Numeric 14,2) em todo valor | Motor de saldos e níveis |
| 12 | Cenário Casa Jardim Flora | Não está no ambiente | Fixtures sintéticas (ver conflito C3) |

## 2. Conflitos com regras já aprovadas (registrados, CLAUDE.md regra 4)

- **C1 — Prompts editáveis × D121 (só leitura).** O pedido atual manda gerenciar prompts (rascunho, teste, aprovação, ativação, rollback). Prevalece o pedido do Marcio de 11/11/2026; a governança impede edição silenciosa: versão ativa nunca muda, quem escreve não aprova, toda mudança vira evento. Os prompts das telas atuais (extração, R04/R07, chat) continuam em `app/prompts/*.md`; os dos agentes A0–A9 nascem de `app/prompts/agents/A*.md` e passam a ser versionados no banco.
- **C2 — Dados de moradores.** O termo do piloto diz que dados de moradores não entram, e a relação de devedores é recusada (D120). REC-02 (boletos por unidade) e REC-04 (inadimplência por unidade) precisam de unidade e situação de pagamento por unidade. **Decisão necessária antes do Ciclo 2.** No Ciclo 1 não há tabela de unidades nem dado de morador; REC-02 e REC-04 aparecem como "Não avaliado".
- **C3 — Cenário de referência com nomes reais.** Casa Jardim Flora e os fornecedores citados não estão no ambiente e a regra do projeto é dado fictício. Os casos (TED devolvida e PIX, estorno, parcela 02/04, transferência de mudança de administradora) são reproduzidos com dados sintéticos e nomes inventados.
- **C4 — Migrações.** O pedido manda executar o Ciclo 1 no código; tomo isso como aprovação da migração 0029 descrita aqui. Migrações dos ciclos seguintes serão listadas antes.
- **C5 — Termos.** O farol usa "Divergente", "Pendente" etc.; os achados continuam com "indício/divergência/ponto de atenção" e as palavras proibidas seguem proibidas em todo texto.

## 3. Plano em quatro ciclos

### Ciclo 1 — núcleo documental e bancário (executado agora)
- **Banco (migração 0029):** `bank_account`, `bank_statement` (saldo inicial e final lidos do extrato, com origem), `bank_transaction.bank_account_id/statement_id`; `audit_period`, `audit_run`, `audit_stage_run`, `audit_agent_run`, `audit_control_result`, `audit_control_review`; `audit_fact`, `evidence_edge`; `agent_prompt_version`, `agent_prompt_event`, `prompt_test_run`. Todas as tabelas de condomínio com RLS; as de prompt são da plataforma.
- **Extratos:** OFX lê banco, agência, conta, período e saldo final (LEDGERBAL); CSV lê "saldo anterior" e o último saldo.
- **Motor (`app/audit/`):** catálogo dos 25 controles (IDs estáveis, versão de regra, fontes, critérios, dependências); orquestrador A0 por competência com etapas 1–8, reuso por impressão digital das entradas (só reabre o que mudou), A1 inventário, A2 registro de fatos, A3 vínculos, A4 conciliação por conta (equação de saldo, continuidade, classificação de débitos e créditos, estornos, níveis a–e), A9 política determinística de status e revisão humana. LLM só onde interpreta: A1/A2 (classificação e leitura, já existentes, agora com o prompt do agente), A4 (sugestão de classificação de lançamento não identificado, sempre "sugerido") e A9 (questionamento em texto, que nunca muda status).
- **Controles do ciclo:** DOC-01, DOC-02, BAN-01, BAN-02, BAN-03, BAN-04, BAN-05, REC-01, DES-01. Os outros 16 aparecem como "Não avaliado — previsto para o ciclo N".
- **Agentes & Prompts:** A0–A9 com finalidade, etapa, dependências, ferramentas, entradas, saídas, limites, dono e ativação; texto integral e copiável com as fronteiras (prompt do agente, regra de segurança fixa da aplicação, tarefa); versões imutáveis com SHA-256, autor, data, status; comparação entre versões; rascunho → teste → envio → aprovação por outra pessoa → ativação; rollback; histórico de execuções com a versão usada; aba "Regras, não prompts"; botão "Como este resultado foi produzido?" em cada controle.
- **Telas:** Farol, Auditoria do mês (etapas e inventário), Conciliação, Controle (detalhe com testes, evidências e revisão), Revisão, Agentes & Prompts. Upload continua em "Enviar documentos".
- **Concluído quando:** migração ida e volta; testes de aritmética, continuidade, estorno, política de status, IDs estáveis, sem verde sem fonte, extrato ausente = Pendente, reprocessamento só do impactado, isolamento entre condomínios, governança de prompt completa, execução guarda versão e hash; lint; telas conferidas na stack local.

### Ciclo 2 — arrecadação, despesas e fiscal
REC-02/03/04 (depende de C2), BAN-06/07, DES-02/03/04; alocação N:N entre lançamentos e obrigações, tributos agrupados, parcelamentos, títulos; pendências persistentes; memória de cálculo por item; A5 e A6 ativos.

### Ciclo 3 — contratos, fundos e governança
Fundos, orçamento e plano de contas; BAN-08/09, CON-01/02/03, GOV-01/02, DOC-03; A7 e A8 ativos; apreciação formal pelo síndico; revalidação histórica.

### Ciclo 4 — operação contínua
Reprocessamento por evento (upload, extrato, contrato), histórico e tendência do farol, SLA e escalonamento, relatório exportável, integração com Optimize e Operate, testes de custo, desempenho e rollback de prompt em produção.
