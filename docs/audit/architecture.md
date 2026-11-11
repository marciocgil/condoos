# CondoOS Audit — arquitetura (ciclo 1)

Decisão D122. Um único motor dentro do CondoOS (FastAPI + PostgreSQL com RLS + fila de jobs + cliente LLM único), sem aplicativo paralelo. Os fatos vêm do registro já existente (documentos com proveniência, despesas, lançamentos, contratos) e o Audit acrescenta contas e extratos, execuções, resultados de controle, fatos imutáveis, vínculos e prompts versionados.

## Pipeline de uma execução (A0, `app/audit/run.py`)

```
POST /condominiums/{id}/audit/runs {competencia}
  │
  ├─ carrega o mês uma vez (app/audit/data.py: documentos, despesas, lançamentos, extratos)
  ├─ Etapa 1  A1 inventário ............ documentos da competência, cópias, versões, extratos
  ├─ Etapa 2  A2 fatos ................. audit_fact imutável (página, trecho, método, versão)
  ├─ Etapa 3  A3 vínculos .............. evidence_edge: verificado (casamento) × sugerido (ambíguo)
  ├─ Etapa 4  A4 conciliação ........... por conta: equação do saldo, continuidade, classificação,
  │                                      estornos; IA só sugere classificação (nunca muda estado)
  ├─ Etapa 5  regras dos controles ..... app/audit/controls.py (determinístico)
  ├─ Etapa 6  A8 ....................... pulada no ciclo 1 (fundos e orçamento, ciclo 3)
  ├─ Etapa 7  A9 ....................... política dos seis estados (código) + questionamento (IA)
  └─ Etapa 8  A0 publica ............... resultado novo só se a impressão digital das entradas mudou;
                                         o anterior fica como substituído; rascunho ou revisão humana
```

Cada etapa grava `audit_stage_run`; cada agente grava `audit_agent_run` (versão do prompt, hash do prompt montado, IA chamada ou não, entradas, saída, não resolvidos, avisos, duração). Toda chamada à IA também grava `llm_calls.prompt_sha256` (D121), igual ao hash da execução do agente.

## Dependências e reprocessamento

Cada controle declara de que entradas depende (`catalog.py`: documentos, extrato, saldos, despesas, pagamentos…; `impacted_by()` dá o grafo). Na execução, o controle calcula a impressão digital (SHA-256) das entradas que de fato leu, com a versão da regra e do motor. Igual à do resultado atual: o resultado é reaproveitado (nada muda, nada duplica). Diferente: resultado novo, o anterior recebe `superseded_by_id`. Assim um extrato novo reabre BAN-01..05 e o que depender deles, e não toca em DOC-02 nem nos controles de outros meses. Parecer antigo nunca é apagado.

## Limites

- Nenhum agente aprova contas, paga, envia mensagem, altera lançamento ou contrato.
- O status vem da regra versionada; a IA não soma dinheiro nem decide status.
- Falta de extrato é "Pendente", nunca saldo zero; saldo que o arquivo não declara fica vazio (OFX não traz saldo inicial: a continuidade usa a abertura implícita, declarada como tal).
- Conciliação é sempre por conta; lançamento de arquivo sem conta identificada aparece separado.
- Documento de fornecedor é dado: o prompt montado traz a regra de segurança fixa e os dados vão entre delimitadores.

## Onde fica cada coisa

| Parte | Código |
|---|---|
| Catálogo dos 25 controles | `api/app/audit/catalog.py` |
| Carga do mês e classificação de lançamentos | `api/app/audit/data.py` |
| Regras dos controles do ciclo 1 | `api/app/audit/controls.py` |
| Orquestrador A0 e agentes | `api/app/audit/run.py` |
| Agentes, prompts e governança | `api/app/audit/agents.py`, `api/app/prompts/agents/A*.md` |
| API | `api/app/routers/audit.py` |
| Telas | `web/app/(admin)/admin/audit/**`, `web/components/audit/*` |
| Leitura de conta e saldo dos extratos | `api/app/ingestion/bank/ofx.py`, `csv_parser.py`, `service.py` |
