# PROMPT 09 — Descoberta, desenho experimental, pilotos e comprovação de ROI

Atue como **UX Researcher + Product Analyst + Pilot Operations Lead**. O CondoOS precisa provar que economiza trabalho e dinheiro sem aumentar risco. Não trate hipóteses, amostras reduzidas ou métricas simuladas como resultados reais.

## Escopo de pesquisa

1. Selecionar perfis de condomínios individuais com complexidades distintas (hipótese inicial: três pilotos; a seleção real deve ser acordada).
2. Estruturar entrevistas com síndico morador, profissional, zelador, administradora, fornecedor e conselho. Perguntar sobre os últimos casos concretos, não só sobre preferência por funcionalidades.
3. Obter autorização legítima para documentos, observação e dados pessoais. Usar dados minimizados/anonimizados para avaliação de IA sempre que possível.
4. Medir baseline do processo atual: volume de solicitações, tempo por etapa, horas de coordenação, retrabalho, pedidos sem status, eventos fora de horário, despesas comparáveis.
5. Executar piloto em camadas: shadow mode (sem envio); Optimize revisado; automação L3 supervisionada; avaliação de impacto.
6. Criar conjunto ouro de perguntas, casos, contratos e faturas com resposta validada por humano, incluindo dados insuficientes.
7. Medir precisão das recomendações e alertas; falsos positivos; falhas críticas; custo do LLM e de revisão humana.
8. Fazer análise antes/depois com volume e sazonalidade; registrar efeitos de mudanças de pessoal, reformas ou período de chuvas.
9. Recomendar Go/Iterar/No-go por módulo e segmento, com justificativa.

## Métricas e fórmulas

- `coverage = demandas registradas / demandas identificadas`.
- `ownership = casos ativos com responsável e prazo / casos ativos`.
- `tempo_liquido_poupado = tempo comparável anterior - tempo posterior - supervisão adicional`.
- `economia_liquida_realizada = redução de custo com escopo equivalente - custos da mudança`.
- `precision_alerta = alertas realmente relevantes / alertas avaliados`.
- `autonomia_segura = tarefas concluídas sob política sem intervenção / tarefas elegíveis`.
- `falhas_criticas_autorizacao = número de ações fora da política` (meta absoluta zero).

## Desenho do protocolo

Para cada experimento, estabelecer: hipótese, segmento, período, dados mínimos, intervenção, controle ou comparação, métricas, eventos instrumentados, limites éticos, riscos, critério de sucesso, custo de operação e decisão de saída. Informar limitação estatística de pilotos pequenos.

## Saídas

`docs/pilot-protocol.md`, `docs/measurement-spec.md`, `docs/evaluation-golden-set.md`, `docs/pilot-diary-template.md`, `docs/roi-methodology.md`, `docs/go-no-go-report-template.md`.

Produza modelo de entrevista e ficha de acompanhamento de caso com timestamps. Ao final, reporte o que foi realmente observado, o que é inferência e o que permanece desconhecido.
