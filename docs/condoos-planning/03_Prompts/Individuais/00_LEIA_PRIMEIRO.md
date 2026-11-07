# CondoOS — Pacote de prompts coordenados v1.0

**Uso:** conjunto de instruções para orquestrar uma IA de desenvolvimento em um repositório real, mantendo alinhamento entre produto, engenharia, segurança e validação.  
**Arquivos de referência obrigatórios:** `CondoOS_Assessor_Inteligente_Especificacao_Mestra_v1.0.md`, `CondoOS_Plano_Diretor_Produto_Engenharia_Validacao_v1.0.docx` e o CondoOS Design System existente.  
**Data:** 06/11/2026.

## Como executar, sem perder contexto

1. Coloque os arquivos de referência no projeto ou forneça-os à IA com acesso efetivo de leitura. Não basta somente citar os nomes dos arquivos.
2. Rode `01_PLANEJADOR_MESTRE.md` uma única vez para criar/reconciliar o plano com o estado real do código. A saída deve incluir diagnóstico e decisões; não autorize reescrita do projeto nesta etapa.
3. Rode `02_AUDITORIA_CODIGO.md` para mapear o que já está implementado. Se o passo 1 já fez parte da auditoria, use este para aprofundar riscos e provas, não duplicar o trabalho.
4. Rode `03_BACKLOG_DEPENDENCIAS.md` e `04_ARQUITETURA_DADOS_SEGURANCA.md` para estabelecer contratos, dependências, testes e arquitetura.
5. Rode `05_UX_FLUXOS.md` para adaptar o **Design System existente** às jornadas prioritárias.
6. Rode `06_CORE_ADVISOR.md` e `07_OPTIMIZE.md` em incrementos pequenos, com testes e gates explícitos.
7. Somente depois rode `08_OPERATE_AUTOMACOES.md` para ações externas e integrações.
8. Rode `09_PILOTOS_MEDICAO.md` antes e durante cada piloto e `10_QA_GATE_RELEASE.md` antes de qualquer expansão de autonomia ou produção.
9. Use `11_EXECUTAR_PROXIMA_FATIA.md` como prompt recorrente de cada ciclo. Ao fim de cada sessão, atualize o estado central.

## Disciplina de execução

- **A IA deve acessar o repositório real**. Se não tiver acesso, entregar proposta e checklist, sem afirmar que inspecionou, testou ou alterou código.
- **Não há autorização implícita para modificar produção, enviar mensagens, criar despesa, tratar dados reais de moradores ou alterar controles financeiros.** Pedir aprovação humana por canal apropriado.
- **Não presumir stack ou status do produto.** Avaliar o código e o Design System antes de introduzir novas bibliotecas ou arquiteturas.
- **Uma execução = uma fatia vertical.** Evitar transformar prompts em pedidos de implementar a plataforma inteira de uma vez.
- **Fontes com precedência:** requisitos aprovados > ADRs aceitas > código real (para estado de implementação) > este plano de trabalho > sugestões de IA. Se houver conflito, registrar e escalar, sem sobrescrever silenciosamente.
- **Estado por requisito:** `nao_iniciado`, `em_analise`, `em_desenvolvimento`, `em_teste`, `bloqueado`, `pronto_para_validar`, `validado`, `adiado`.
- **Status por evidência, não por redação:** `validado` requer link a teste, PR, demo ou aceite.

## Saída mínima de toda execução

1. Objetivo da execução e escopo excluído.
2. Referências lidas e arquivos de código realmente inspecionados.
3. IDs `CAP`, `FR`, `WP`, `VS`, histórias e testes associados.
4. Modificações (arquivos, migrações, endpoints, telas, integrações).
5. Testes executados, comandos e resultado real (passou/falhou/não executado).
6. Riscos, decisões, bloqueios e trabalho residual.
7. Próxima fatia indicada, respeitando dependências.
8. Atualização de `docs/roadmap-status.md` e `docs/traceability.md`.
