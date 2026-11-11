# Governança dos prompts dos agentes

- **Versão 1** de cada agente vem de `api/app/prompts/agents/A*.md`, texto literal do Prompt Mestre v1.0, criada uma vez no banco e ativa.
- **Ninguém edita uma versão.** Mudança é sempre versão nova: rascunho (Admin CondoOS, com o motivo) → teste no sandbox (verificações estáticas e casos fixos: documento com instrução maliciosa, fronteiras do prompt) → envio para revisão (só se o último teste passou) → aprovação por **outra pessoa** da equipe CondoOS (o autor não aprova), com motivo → ativa; a anterior vira arquivada.
- **Rollback:** o Admin reativa uma versão que já esteve ativa, com motivo. Fica como evento "rollback".
- **Verificações do texto:** começa com "Você é A…", diz o que o agente não faz, até 8.000 caracteres, sem palavras proibidas, sem credenciais, sem marcadores `{{…}}` (dados só entram na tarefa da chamada).
- **Prompt montado:** instruções do agente (versionadas) + regra de segurança fixa da aplicação + tarefa da chamada. O hash do prompt montado fica na execução do agente e em `llm_calls`. Instruções internas do provedor do modelo não são controladas pelo produto e não aparecem.
- **Quem vê:** só a equipe CondoOS lê o texto dos prompts. Gerente e analista veem, no controle, quais agentes e qual versão (número e hash) produziram o resultado.
- **Trilha:** cada passo grava `agent_prompt_event` e `audit_log` (`prompt.*`).
