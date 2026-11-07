# Launch — matriz de prontidão por capacidade

Data: 07/11/2026. **Proposta (ADR-L03).** Estados: `nao_configurado` → `analise_parcial` → `supervisionada` → `autorizada`. Requisitos são binários; nenhum percentual libera nada. Marco da jornada (LM1–LM5) não muda estado de capacidade.

Coluna "Sinal no código" diz de onde o requisito é lido hoje (✔ existe · ✚ novo).

| Capacidade | Requisitos indispensáveis | Sinal no código | Sem os requisitos (modo degradado) | Rebaixa quando |
|---|---|---|---|---|
| **C1 Perguntas sobre documentos** | Documento processado; trechos indexados; papel com `VIEW`; chat disponível | ✔ `extraction_status`, `document_chunk`, `resolve_mode()` | `analise_parcial`: mostra o sumário por campos com trechos; chat "indisponível agora" sem resposta inventada | Versão nova do documento (D85) até reindexar |
| **C2 Leitura de contrato** | Contrato extraído com fornecedor, valor, vigência ≥ 0,9 ou revisado por pessoa; fonte com trecho | ✔ `field_confidence`, `reviewed_at`, `field_provenance` | Campos abaixo de 0,9 "a confirmar"; nada calculado sobre eles | Aditivo novo ou conflito aberto (✚ `data_issue`) |
| **C3 Confronto de cobranças (Optimize)** | C2 em `supervisionada` para o contrato; fatura/despesa do mês casada; índice do BCB disponível; competência com fila do mês vazia para "relatório completo" | ✔ `expense_document`, `index_value`, `competence`, fila | Achados do que dá para avaliar + aviso de cobertura ("3 de 7 contratos com fatura"); relatório nunca diz "completo" | Fatura nova sem casamento; regra "não avaliada" (sem IA) |
| **C4 Recomendação de economia** | C3 `supervisionada`; revisor CondoOS atribuído; revisão interna aprovada | ✔ `condo_assignment`, `opportunity_review` (D81) | Oportunidade fica interna (404 para o condomínio, D81) | Revisor revogado; contrato substituído |
| **C5 Delegação** | Pessoa, papel, contato e escopo confirmados pelo síndico | ✔ `membership` (com login) · ✚ `delegation_request` (sem login) | Rascunho aguardando o síndico | Pessoa revogada; pedido expirado |
| **C6 Mensagem para terceiros** | Canal homologado; destinatário autorizado; tipo de ação permitido pela política; aprovação do síndico | ✚ (não existe envio) | Gera texto para o síndico enviar; nunca envia | Kill switch (`automation_pause`); falha de entrega |
| **C7 Ação operacional** (implementada em D90 como "Ações com sua aprovação": alçada vigente e kill switch) | Responsável; alçada vigente (`ctx.limits`, D85); política; aprovação com hash (D83) | ✔ `app/policy`, `action_request` | Só prepara e pede aprovação; despacho não envia (D83) | Troca de síndico; aprovação vencida (7 dias) |
| **C8 Documentos esperados** | Contrato com `billing_frequency`; canal de entrada conhecido; janela (`grace_days`) | ✔ `pending.py` | Lista "aguardando" sem acusar ausência | Canal sem documento há N dias (✚ monitor LF5) |
| **C9 Fechamento do mês** | Fila do mês vazia; quem fecha atribuído (gerente ou reviewer, D77) | ✔ `competence`, `close_competence` | Prévia rotulada "parcial" | Documento novo do mês fechado (já tratado) |

## Estados — definição operacional

| Estado | Significa | O usuário vê |
|---|---|---|
| `nao_configurado` | Falta requisito de entrada (nenhum documento, nenhum contrato) | "Ainda não configurado — envie *X* para ativar" |
| `analise_parcial` | Há dados, mas falta algum requisito ou há item a confirmar | "Análise parcial — *motivo*". Resultados com rótulo de cobertura |
| `supervisionada` | Todos os requisitos; ações exigem aprovação de pessoa em cada caso | "Funcionando com sua aprovação" |
| `autorizada` | Supervisionada + política explícita aprovada pelo síndico para aquele tipo de ação de baixo risco | Não existe no produto hoje: nenhuma regra responde "permite" (D83). **Fica fora até decisão.** |

## Grafo de dependências (próximo melhor passo)

```
C1 ← documento
C2 ← contrato (documento) ─┐
C3 ← C2 + faturas + extrato┼→ C4 ← revisor atribuído
C8 ← C2 (periodicidade)    │
C5 ← pessoa confirmada ────┴→ C6 ← canal + política (LF5)
C7 ← alçada + política
```

Próximo passo = requisito faltante de menor esforço que desbloqueia a capacidade ligada ao objetivo escolhido (`launch_state.goal`); empate → maior valor em risco conhecido.
