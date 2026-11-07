# PROMPT 05 — UX/UI contextual, jornadas e adaptação do Design System CondoOS

Atue como **Product Designer + UX Engineer**. O CondoOS já possui uma interface e um Design System; seu papel é **adaptá-los**, não redesenhar a marca. Leia os arquivos reais da interface e dos componentes antes de propor alterações.

## Perfis

Síndico morador/profissional (decisões), revisor interno Optimize (validar oportunidades), zelador (tarefas/evidências), administradora (dados/financeiro), fornecedor (OS/propostas), morador (seus protocolos), conselheiro (consulta autorizada).

## Jornadas prioritárias

1. Primeiro acesso e seleção explícita de condomínio.
2. Tela Hoje: prioridades fundamentadas, atividades realizadas, pendências e aprovações.
3. Caixa de entrada: classificar/confirmar mensagem e convertê-la em caso.
4. Assunto 360°: caso → documentos → tarefas → responsáveis → timeline → conclusão.
5. Documento: upload → estado de processamento → campos extraídos e evidências → revisão.
6. Pergunta à IA: resposta curta, link para fonte, data/versão e incerteza.
7. Aprovação: ver efeito, valor, risco, versão e escopo; aprovar/recusar/solicitar revisão.
8. Optimize: cláusula → fatura → divergência → revisão interna → oportunidade publicada.
9. Futuro: OS do zelador/fornecedor e estado em canal do morador.

## Instruções de design

- Inventariar telas e tokens existentes; mapear o que reusar, adaptar e construir.
- Para cada jornada criar fluxograma de estados normais, loading, vazio, erro, falta de acesso, fonte ausente, ação cancelada, revisão, atraso e conflito.
- Desenhar hierarquia visual por **urgência, responsabilidade e ação necessária**, não por quantidade de módulos.
- Distinguir semanticamente `identificado`, `proposto`, `aguardando aprovação`, `solicitado`, `aceito`, `em execução`, `executado` e `validado`.
- Mostrar `quem precisa agir`, `até quando`, `por quê`, `qual prova` e `o que acontece ao clicar`.
- Nunca usar cartão verde 'concluído' quando só houve envio de mensagem.
- Suportar desktop/mobile, teclado, leitores de tela, contraste, tabelas responsivas e dados vazios.
- Exibir informações financeiras e de moradores somente para papéis autorizados.

## Saídas

Criar `docs/ux-journeys.md`, `docs/ui-inventory.md`, `docs/screen-specs.md`, fluxos Mermaid, mapa de componentes atuais/novos, contratos de API por tela e critérios de UX testáveis.

Para **cada tela**, entregue: persona, objetivo, dados necessários, ações, regras de autorização, estados, erros, métricas e testes visuais. Se receber autorização para codar, implemente a próxima fatia vertical com reutilização de componentes; não entregue apenas mock visual quando o objetivo for fluxo funcional.
