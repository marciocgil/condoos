# Fluxos de referência após DV-01..DV-05

Data: 07/11/2026. Decisões D73–D77. Complementa a Especificação (§8, §14, FL-02) com o que vale para o produto atual. Itens marcados **(proposto)** dependem das migrações de `docs/data-model.md`.

## F1 — Condomínio contratante direto (D73)

1. CondoOS Admin cadastra o condomínio (Carteira ou `app.onboarding`), com ou sem administradora (`management_company_id` opcional, D3).
2. Admin dá acesso ao síndico e atribui um CondoOS Reviewer ao condomínio **(proposto)**.
3. Se houver administradora, o gerente dá ou recebe acesso como colaborador externo, com prazo opcional **(proposto)**. Ela envia documentos e responde solicitações, e valida achados só se o condomínio permitir (`management_company_reviews`).
4. Documentos chegam por upload, e-mail ou administradora. A fila de exceções é tratada pelo reviewer (ou pela analista, se houver).

O trabalho da analista se divide em três:

| Grupo | Exemplos | Quem faz |
|---|---|---|
| Automatizável | Leitura, classificação, cruzamento, divergências, pendências | CondoOS (pipeline e regras atuais) |
| Exige validação | Correção de extração ambígua, casamento ambíguo, achados graves, recomendações | CondoOS Reviewer (ou administradora, se permitido) |
| Fica na administradora | Boletos, folha, contabilidade, pagamentos | Administradora, fora do sistema |

## F2 — Achado: identificar, qualificar, revisar proporcionalmente (D74)

```
regras R01–R12 ──► achado criado ──► qualificação (código) ──► política de revisão
                                     categoria, severidade,     │
                                     confiança, valor,          ├─ none ──────────────► publicado (corpo diretivo vê)
                                     IA envolvida               ├─ qualified_review ──► aguardando_validacao ─► reviewer (ou gerente, se permitido)
                                                                │                         validar → publicado / descartar (motivo)
                                                                └─ pending_evidence ──► pendente_evidencia ─► nova evidência → reavaliação
```
- A identificação nunca espera pessoa. A qualificação é determinística (dados da regra) e registra a versão da política usada.
- Com a política padrão, o resultado é idêntico ao de hoje: graves aguardam validação, os demais publicam.
- Alerta urgente (futuro, incidentes) segue protocolo sem esperar revisão.
- Depois de publicado, o ciclo do síndico (confirmar/contestar/ignorar, D48) e a superação (D61) seguem iguais.

## F3 — Do achado ao resultado medido (D76)

```
Achado(s) ──► Qualificação ──► Oportunidade (identificada) ──► economia POTENCIAL (código)
        ──► em_revisao_interna ──► Reviewer: aprovar | ajustar | devolver | rejeitar  [obrigatório no piloto]
        ──► aprovada_para_cliente + economia ESTIMADA VALIDADA (congelada por hash)
        ──► apresentada ao síndico ──► síndico aprova dentro da alçada ──► economia APROVADA
        ──► execução fora do sistema (negociação, aditivo, contestação pela administradora/síndico)
        ──► documento do acordo ──► economia CONTRATADA
        ──► faturas posteriores conferidas contra o baseline ──► economia REALIZADA
```
- Uma oportunidade pode reunir vários achados ou nascer de análise sem achado.
- O sistema não negocia, não envia e não paga: os passos de execução são registrados, não disparados.
- Cada estágio de economia é uma linha nova, nunca sobrescrita; a interface rotula cada um e não soma estágios.
- Mudança material após a aprovação do reviewer devolve à revisão.

## F4 — Assunto (D75)

Origens: achado, oportunidade, pedido humano, manutenção, obrigação, evento externo.

1. Pedido de criação (pessoa ou sistema) → busca de duplicidade (vínculos e categoria) → "vincular ao existente" ou "criar mesmo assim" com motivo.
2. Assunto nasce `novo`, com dono, próxima ação e prazo (ou `suspenso_justificadamente` com motivo e data de reavaliação).
3. Vínculos N:N com achados, oportunidades, documentos, contratos, fornecedores, despesas e outros assuntos; desvincular preserva o histórico.
4. Tarefas com responsável e prazo; mudança de prazo pede motivo.
5. Estados da Especificação §8.2; `resolvido` exige o critério do tipo (evidência quando exigida); "o fornecedor disse que fez" leva a `aguardando_validacao`, não a `resolvido`.
6. Timeline (`case_event`) registra tudo, só inclusão.

Exemplo da decisão DV-03: achado R11 (conta de água acima do padrão) + reclamações + manutenção pendente da bomba → um assunto "Investigar anormalidade no abastecimento de água" com os três vínculos. O achado continua com o próprio ciclo; resolver o assunto não muda o status do achado.

## F5 — Acesso externo temporário (D77)

Gerente ou Admin concede acesso por e-mail com papel e prazo **(proposto)** → convite fica pendente até o primeiro login → vale até `expires_at` ou revogação → cada concessão, aceite e revogação gera auditoria → a próxima requisição após a revogação já é recusada (SEC-10).
