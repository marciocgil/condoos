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

Ainda não automatizados (ciclos seguintes): regressão de quatro meses com acervo real (não disponível), duplicata de PDF no inventário, duas contas com transferência (BAN-06), repasse sem comprovante (BAN-07), leitura de água ausente (REC-03), contrato vencido e apólice renovada (ciclo 3).
