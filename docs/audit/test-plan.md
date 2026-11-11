# Plano de testes do CondoOS Audit (ciclo 1)

Testes automatizados em `api/tests/test_audit.py` (18), com dados sintéticos (condomínio, banco 999 e fornecedores inventados), e `web/tests/e2e/audit.spec.ts` (2).

| Caso | Teste | Resultado esperado |
|---|---|---|
| Catálogo com 25 IDs estáveis e grafo de dependências | `test_catalog_has_25_stable_controls` | 9 implementados; extrato reabre BAN, não GOV |
| Classificação e pareamento de estorno (TED devolvida e PIX) | `test_classification_and_reversal_pairing` | estorno pareado só até 10 dias, mesmo valor |
| Aritmética centesimal; extrato sem saldo inicial | `test_balance_equation_is_exact_and_never_assumes_zero` | 1 centavo diverge; sem saldo nunca vira zero |
| Verde sem teste ou sem evidência | `test_policy_blocks_green_without_tests_or_evidence` | barrado como Não avaliado |
| Prompts literais e validação | `test_prompts_are_the_literal_text_of_the_prompt_mestre`, `test_prompt_validation_rejects_injection_markers_and_secrets` | texto igual ao documento; marcadores e credenciais recusados |
| Mês completo de ponta a ponta | `test_month_end_to_end` | BAN-01 com ressalva, BAN-02/04/05, DOC-02, DES-01 validados, BAN-03 e REC-01 pendentes, 16 não avaliados, agentes com versão |
| Extrato ausente | `test_missing_statement_is_pending_never_zero` | Pendente, nenhum verde |
| Divergência de 1 centavo | `test_one_cent_divergence_goes_to_human_review` | Divergente, R$ 0,01, revisão humana |
| Reprocessamento | `test_rerun_reuses_and_new_evidence_reopens_only_what_it_affects` | 25 reaproveitados; mudança reabre só BAN-03; histórico mantido |
| Pagamento devolvido contado duas vezes | `test_returned_payment_counted_twice_is_divergent` | BAN-05 e DES-01 divergentes |
| Documento com instrução maliciosa | `test_injected_document_does_not_change_status` | nenhum verde |
| IA usa o prompt ativo e só sugere | `test_model_suggestions_use_the_active_prompt_and_stay_suggestions` | hash da execução = hash em `llm_calls`; BAN-03 segue pendente |
| Acesso, isolamento e revisão | `test_api_access_review_and_isolation` | síndica 403; outro condomínio 404; verde sem fonte recusado; reclassificação cria histórico |
| Governança de prompt | `test_prompt_governance_draft_test_approve_rollback` | sem teste não envia; autor não aprova; revisora não escreve; diff; rollback |
| Versão usada pela execução | `test_active_version_is_the_one_runs_use` | execução grava a versão ativa |
| Conta e saldos do OFX | `test_statement_import_keeps_account_and_balances` | conta criada, saldo final guardado, saldo inicial vazio |

Ainda não automatizados (ciclos seguintes): regressão de quatro meses com acervo real (não disponível), duplicata de PDF no inventário, duas contas com transferência (BAN-06), repasse sem comprovante (BAN-07), leitura de água ausente (REC-03), cenários do ciclo 4 (reprocessamento por evento, desempenho e custo).

## Ciclo 2 (`api/tests/test_audit_cycle2.py`, 16)

| Caso | Teste | Esperado |
|---|---|---|
| Importação descarta nome e CPF; cópia guardada sem nomes; reimportar atualiza | `test_titles_import_drops_names_and_keeps_only_a_clean_copy` | colunas descartadas, nada de nome no arquivo guardado |
| Retorno de cobrança sem pagador | `test_collection_return_never_keeps_the_payer` | nome e documento vazios |
| REC-02 confirmado pelo crédito do dia; dia que não fecha; título repetido | `test_rec02_titles_confirmed_by_the_day_credit` | Validado; Pendente; Divergente R$ 500,00 |
| Sem títulos | `test_rec02_and_rec04_pending_without_titles` | Pendente |
| REC-04 por unidade e continuidade | `test_rec04_reconstructs_by_unit_and_checks_the_previous_month` | ressalva no primeiro mês; Validado; Divergente quando o título de maio muda depois |
| REC-03 com e sem leituras | `test_rec03_rateio_with_and_without_readings` | ressalva; Validado; Divergente |
| REC-03 não aplicável só por declaração | `test_rec03_not_applicable_only_by_declared_profile` | Pendente → Não aplicável |
| BAN-06 uma e duas contas | `test_ban06_transfer_between_two_accounts` | ressalva → Validado |
| BAN-07 comprovante final | `test_ban07_intermediary_needs_final_receipt` | Pendente → Validado; DES-01 com ressalva |
| DES-02 guia = retenções | `test_des02_federal_slip_equals_withholdings`, `test_des02_not_applicable_without_withholdings` | Validado; Divergente por 1 centavo; Pendente sem guia; Não aplicável sem retenção |
| DES-03 pelo perfil | `test_des03_follows_the_profile` | Pendente; Não aplicável; Pendente sem guias |
| DES-04 numeração 02/02 → 03/04 | `test_des04_installment_numbering_needs_the_agreement` | Não aplicável declarado; ressalva |
| Pagamento agrupado | `test_grouped_payment_is_allocated_only_when_unique` | combinação única verificada; ambígua só sugerida |
| Pendência persistente | `test_issues_persist_resolve_and_reopen_with_the_same_id` | aberta → resolvida → reaberta com o mesmo id |
| Acesso e API | `test_unit_data_is_internal_and_imports_drop_names` | síndica 403; nada de nome nas respostas |

## Ciclo 3 (D124) — `tests/test_audit_cycle3.py` (16)

| Controle / regra | Positivo | Negativo |
|---|---|---|
| CON-01 | nota igual ao contratado → Validado; sem contrato → Não aplicável | nota R$ 100 acima → Divergente e revisão humana; faturamento não apresentado e nota em contrato vencido → ressalva |
| CON-02 | dentro da alçada; autorização antes da nota + documento + aceite → Validado | sem autorização ou sem aceite → Pendente; autorização depois da nota → ressalva; aceite nunca responde à R12 |
| CON-03 | parcelas 1/3 e 2/3 → Validado, saldo futuro R$ 1.000 | parcela 2 cobrada duas vezes → Divergente |
| BAN-08 | fundo com conta de aplicação que cobre o saldo → Validado | sem fundo → Pendente; sem conta indicada → ressalva; lastro R$ 1.000 menor → Divergente |
| BAN-09 | aplicação com contrapartida, rendimento e IR, saldo fecha → Validado; sem aplicação → Não aplicável | aplicação sem o extrato próprio → Pendente; R$ 500 que saíram e não chegaram → Divergente |
| GOV-01 | desvios explicados e orçamento com ata → Validado | sem orçamento → Pendente; desvio de 50% sem explicação → ressalva |
| GOV-02 | seguro vigente com data confirmada → Validado | sem obrigações → Pendente; apólice vencida antes do fim do mês → Pendente |
| DOC-03 | conselheiro no mandato, depois do mês → Validado | sem aprovação → Pendente; síndico entre os signatários → ressalva; data no futuro recusada |
| Publicação | envio depois da revisão; o síndico aprova a versão vista; resultados ficam `APPROVED_FOR_PUBLICATION`; revalidação que muda marca "mudou depois" | envio com revisão pendente recusado; quem enviou não aprova; hash diferente recusado; execução nova substitui o envio |
| Acesso | só o síndico aprova; nenhum papel revisa e aprova; síndico sem `view_audit` | gerente não aprova (403); síndico não envia (403); conselho vê só aprovados e não aprova; outro condomínio → 404 |

