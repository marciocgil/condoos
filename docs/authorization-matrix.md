# Matriz de autorização — papéis, permissões e ações

Data: 07/11/2026. Decisão de origem: D77 (DV-05); implementado em D79 (`api/app/auth/rbac.py`). `manage_cases` e `update_task` têm rota desde a VS-01 (D80). `view_opportunity_draft`, `review_opportunity` e `approve_in_condo` têm rota desde a VS-03 (D81).

Princípios (DV-05):
- Escopo sempre por condomínio; usuário de plataforma só vê condomínios atribuídos (`condo_assignment`).
- Ler ≠ editar ≠ validar ≠ aprovar ≠ executar: cada um é uma permissão separada.
- Validar uma recomendação (revisor) **não** dá poder de aprovar no condomínio (síndico), e vice-versa.
- Vários papéis por usuário (união das permissões, como hoje).
- Nada é aprovado só pelo nome do papel: alçadas (`approval_limits`) e política de revisão (`review_policy`) também precisam permitir.
- Acesso externo temporário e revogável (`membership.expires_at`, `revoked_at`).
- Toda ação de escrita gera `audit_log` (só ids).

## 1. Permissões × papéis

Legenda: ✅ tem · ◐ condicionado (ver nota) · — não tem. Colunas: Sín = síndico · Sub = subsíndico · Cons = conselheiro · Ger = administradora gerente · Ana = administradora analista · Adm = CondoOS Admin (novo) · Rev = CondoOS Reviewer (novo). Zelador, fornecedor e morador: reservados, sem permissão até serem ativados.

| Permissão | O que libera | Sín | Sub | Cons | Ger | Ana | Adm | Rev |
|---|---|---|---|---|---|---|---|---|
| `view` | Resumo, achados publicados, contratos, histórico, chat | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `view_pending_findings` | Achados aguardando revisão ou evidência | — | — | — | ✅ | ✅ | ✅ | ✅ |
| `decide_finding` | Confirmar, contestar, ignorar | ✅ | — | — | ✅⁶ | — | — | — |
| `comment_finding` | Comentar | ✅ | ✅ | ✅ | ✅ | — | — | ✅ |
| `validate_finding` | Validar/descartar/reabrir achado em revisão | — | — | — | ◐¹ | — | — | ✅ |
| `upload_document` | Enviar documentos | ✅ | — | — | ✅ | ✅ | ✅ | ✅ |
| `correct_extraction` | Corrigir extração, resolver casamento | — | — | — | ✅ | ✅ | ✅ | ✅ |
| `record_approval` | Registrar aprovação passada (R12) | — | — | — | ✅ | ✅ | — | ✅ |
| `close_competence` | Fechar o mês | — | — | — | ✅ | — | — | ✅² |
| `configure` | Dados, corpo diretivo, acessos, contratos | — | — | — | ✅ | — | ✅ | — |
| `export` | Relatórios e trilha | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `manage_cases` **(novo)** | Criar/editar assunto, vincular, atribuir tarefa | ✅ | — | — | ◐³ | ◐³ | ✅ | ✅ |
| `update_task` **(novo)** | Atualizar tarefa atribuída a si | ✅ | — | — | ✅ | ✅ | ✅ | ✅ |
| `manage_launch` **(D90)** | Escolher o objetivo da jornada, adiar passo, ocultar o cartão (preferências; a leitura da jornada é `view`) | ✅ | — | — | — | — | ✅ | — |
| `view_opportunity_draft` **(novo)** | Ver oportunidade antes da revisão | — | — | — | — | — | ✅ | ✅ |
| `review_opportunity` **(novo)** | Aprovar/ajustar/devolver/rejeitar oportunidade; registrar "estimada validada" | — | — | — | — | — | — | ✅ |
| `review_finding` **(novo)** | Solicitar evidência; revisar achado conforme política | — | — | — | ◐¹ | — | — | ✅ |
| `approve_in_condo` **(novo)** | Aprovar decisão do condomínio dentro da alçada (ex.: avançar com oportunidade) | ✅⁴ | — | — | — | — | — | — |
| `configure_policy` **(novo)** | Política de revisão, autorizações operacionais e pausa de automações (kill switch, D83) do condomínio | ✅⁵ | — | — | — | — | ✅ | — |
| `manage_platform` **(novo)** | Onboarding, atribuições de reviewer, integrações, suporte | — | — | — | — | — | ✅ | — |

Notas:
1. Só quando `condominium.management_company_reviews = true` e a regra da política lista `gerente` como revisor (padrão para os condomínios atuais, D74). Sem isso, o gerente não valida.
2. Proposta: no condomínio contratado direto (sem administradora), o fechamento do mês passa ao reviewer, que já trata a fila. **Decisão tomada pelo Claude, reversível**; registrada em D77.
3. Só em assuntos/tarefas em que a administradora foi envolvida (atribuição ou vínculo), não em todos.
4. Sempre dentro das alçadas e competências; valores acima da alçada pedem aprovação do órgão competente (conselho/assembleia), registrada como hoje (R12).
5. Síndico configura só as autorizações operacionais do próprio condomínio; a regra "recomendação de economia exige revisão interna" não é editável por condomínio no piloto.
6. Mantido do comportamento anterior a D77, quando o gerente tinha todas as permissões. Rever quando a administradora deixar de ser o operador padrão.

## 2. Ações sensíveis e quem decide

| Ação | Quem pode | Condição extra | Situação |
|---|---|---|---|
| Publicar oportunidade ao condomínio | Reviewer | Revisão aprovada da versão atual (hash) | Proposta (VS-03) |
| Aprovar avanço de oportunidade no condomínio | Síndico | Alçada; revisão aprovada | Proposta |
| Validar achado grave | Reviewer; gerente se permitido | Política vigente | Hoje: só gerente |
| Pedir ação (cobrar fornecedor, orçamento sem custo, visita técnica) | `manage_cases` (síndico, Admin, Reviewer) | Política v1 aceita o tipo e o teto | Entregue (D83) |
| Aprovar, recusar ou pedir ajuste de ação | Síndico (`approve_in_condo`) | Hash da versão na tela; teto dentro da alçada; vale 7 dias | Entregue (D83) |
| Registrar execução de ação aprovada | `manage_cases` | Aprovação válida; custo final dentro do teto | Entregue (D83) |
| Pausar/retomar automações | `configure_policy` (síndico, Admin) | Motivo; auditado | Entregue (D83) |
| Pagamento, contratação, multa, envio externo | **Ninguém pelo sistema** | — | Proibido (CLAUDE.md); a política nega (D83) |
| Dar acesso a condomínio | Gerente (como hoje) ou Admin | Auditado; externo com prazo | Parcial |
| Atribuir reviewer a condomínio | Admin | Motivo, prazo opcional, auditado | Proposta |
| Acesso de suporte | Admin | Atribuição temporária com motivo | Proposta |

## 3. Papéis reservados (ativação futura)

| Papel | Primeira interface prevista | Pré-requisito |
|---|---|---|
| Zelador | Link autenticado para tarefas e fotos | VS-01 (tarefa) + WP-18 |
| Fornecedor | Link autenticado por OS/cotação | G4 + WP-18/21 |
| Morador | Formulário/canal oficial | WP-20 + política de comunicação |
| Conselho com aprovação | Aprovação formal registrada | Atribuição formal (ata) + WP-10 |
