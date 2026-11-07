# Launch LF3-b — proposta: conflitos de dados e Central de Validação (migração 0020)

Data: 07/11/2026. **Aprovada pelo Marcio em 07/11/2026 e implementada (D93).** O texto abaixo é a proposta original; diferenças da implementação estão em D93. Detalha a ADR-L05 (`03-arquitetura-e-dados.md`) e os itens LB-030, LB-032, LB-035 e LB-036 de `05-backlog.md`. A parte da LF3 sem migração já foi entregue (D92).

## 1. Problema

Hoje, quando dois documentos dizem coisas diferentes (por exemplo, um aditivo com data de efeito fora da vigência do contrato, ou dois contratos vigentes do mesmo fornecedor para o mesmo serviço), o sistema escolhe um caminho por regra fixa: vale o aditivo mais recente (D66). Ninguém fica sabendo do conflito, nada fica registrado e as funções que dependem do contrato (confronto de cobranças, agenda de reajuste, ações com o fornecedor) seguem como se o dado fosse firme. O prompt do Launch pede o oposto (fluxo F05): registrar a divergência com os trechos, rebaixar só o que depende dela, pedir validação e guardar a versão que prevalece, com quem decidiu e por quê.

`match_issue` não serve: é a ambiguidade de casamento de **um** documento com despesas. Achado também não: conflito de cadastro não acusa ninguém. Assunto pode receber o conflito por vínculo (D75), mas não o substitui.

## 2. Modelo proposto (migração 0020, toda aditiva)

### 2.1 `data_issue` (RLS por condomínio)

| Coluna | Tipo | Observação |
|---|---|---|
| `id`, `created_at`, `updated_at` | padrão | |
| `condominium_id` | uuid, FK | RLS e índice |
| `kind` | texto, CHECK | v1: `conflito_documentos`. Reservados (sem detector ainda): `duplicidade_suspeita`, `dado_vencido` |
| `status` | texto, CHECK | `aberto` → `resolvido` ou `descartado`; `reaberto` volta a `aberto` |
| `subject_type`, `subject_id` | texto + uuid | o que o conflito afeta: `contract` na v1 |
| `field` | texto, opcional | campo em disputa (`valor_mensal`, `data_fim`, `data_inicio`…) |
| `title`, `detail` | texto | pt-BR, linguagem de "divergência" |
| `evidence` | JSON | lista de `{document_id, page, excerpt, value}` — um item por lado |
| `capabilities` | JSON | funções rebaixadas enquanto aberto (ex.: `["C2", "C3"]`) |
| `amount_at_stake` | dinheiro, opcional | diferença mensal quando os lados são valores (prioridade na Central) |
| `detector` | texto | regra e versão (`aditivo_fora_da_vigencia_v1`, `contratos_sobrepostos_v1`) |
| `dedupe_key` | texto | único por condomínio: detectar de novo não duplica (jobs idempotentes) |
| `resolution` | JSON, opcional | `{prevailing: {document_id, value}, reason}` |
| `resolved_by_user_id`, `resolved_at` | opcional | |

### 2.2 `data_issue_event` (RLS, **só inclusão**, como `case_event`)

`issue_id`, `kind` (`detectado`, `redetectado`, `resolvido`, `descartado`, `reaberto`, `comentado`), `user_id` (nulo quando é o sistema), `payload`. Entra em `APPEND_ONLY_TABLES`.

### 2.3 Vínculo com Assunto

A migração acrescenta `data_issue` ao CHECK de `case_link.target_type`, para um conflito poder ser ligado a um assunto (D75: vínculo N:N, nunca apagado).

Volta da migração: apaga as duas tabelas e restaura o CHECK de `case_link`. Vínculos que apontem para `data_issue` são removidos antes, e isso fica dito no texto da migração.

## 3. Detecção v1 (determinística, sem IA)

Roda no job de casamento depois que um contrato ou aditivo entra, e de novo quando um documento é corrigido:

1. **Aditivo fora da vigência:** `contract_amendment.effective_date` anterior ao início ou posterior ao fim do contrato.
2. **Contratos sobrepostos:** dois contratos do mesmo condomínio e fornecedor, com períodos que se cruzam e sem um ser versão do outro (`supersedes_id`). Indício de versão antiga não marcada.
3. **Valor divergente entre aditivos do mesmo dia:** dois aditivos com a mesma data de efeito e valores mensais diferentes.

Cada detecção grava os trechos dos documentos (proveniência, D85). Se o conflito deixar de existir porque chegou um documento novo e ninguém tinha agido, ele vira `descartado` com o motivo "superado por novos dados" (como D61).

## 4. Efeitos enquanto aberto

- **Prontidão:** C2 e C3 ficam em "análise parcial" com o título do conflito. O cartão de primeiro valor marca o campo em disputa como **"conflitante"** (LB-036).
- **Política (LB-035):** ação cujo `supplier_id` tenha conflito aberto em contrato recebe `DENY` com o motivo "há divergência de dados aberta neste contrato". Só o pedido é recusado, e nada é apagado.
- **Regras:** continuam usando a versão em vigor (D66). Achados do contrato em conflito ganham uma linha na evidência dizendo que o contrato tem divergência aberta. Não mudo o resultado das regras na v1.

## 5. Central de Validação (LB-032)

- **Desktop**, para a equipe CondoOS e o gerente: tela "Validação" com os conflitos abertos ordenados por `amount_at_stake` e idade, os dois trechos lado a lado (componentes `SidePanel`, `EvidenceList`), "Manter este" / "Manter o outro" / "Descartar (não é conflito)", motivo obrigatório. A fila de exceções atual continua onde está; a Central mostra o contador dela e um link.
- **Celular do síndico:** só leitura no cartão "O que já funciona" ("1 divergência em validação: Portaria X") e o vínculo com assunto, se houver.

## 6. Quem pode o quê (proposta)

| Ação | Quem |
|---|---|
| Ver conflitos | quem vê o condomínio (`VIEW`) |
| Resolver ou descartar | revisora CondoOS e gerente (`CORRECT_EXTRACTION`, permissão já existente) |
| Reabrir | os mesmos |
| Ligar a um assunto | quem tem `MANAGE_CASES` |

O síndico não resolve conflito de cadastro (é trabalho de conferência). Se preferir que ele possa, é só acrescentar a permissão ao papel.

## 7. Testes previstos

- **Por detector:** um caso positivo e um negativo.
- **Idempotência:** detectar duas vezes não duplica.
- **Ciclo de estados:** resolver exige motivo e versão; descartar exige motivo.
- **Eventos:** só inclusão (`test_isolation.py::test_append_only_tables`).
- **Isolamento:** RLS, e conflito de outro condomínio responde 404.
- **Política:** nega ação com conflito aberto e volta a permitir depois de resolvido.
- **Prontidão:** C2 e C3 rebaixam e voltam.
- **E2E da Central:** o fluxo F05 de ponta a ponta.

## 8. Decisões que preciso

1. **Aprovar a migração 0020** como descrita (duas tabelas novas com RLS, eventos só inclusão, `data_issue` no CHECK de `case_link`).
2. **Quem resolve:** revisora CondoOS e gerente (proposta) ou também o síndico?
3. **Política:** negar ações com o fornecedor enquanto houver conflito aberto no contrato dele (proposta), ou só avisar?
