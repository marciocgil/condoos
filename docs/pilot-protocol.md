# Protocolo de piloto — plano inicial de validação

Data: 07/11/2026. Base: Especificação §17 e §19; Plano Diretor §10. **Hipóteses de trabalho, não compromissos.** Nenhum dado real de condomínio entra no sistema sem autorização escrita (CLAUDE.md, item 7); até lá, só o seed e o corpus fictícios.

## 1. Pré-condições (gate G0)

1. Respostas às divergências DV-01 (quem contrata e quem opera) e DV-02 (revisão interna) — `docs/03-decisions-register.md`.
2. Termo de uso do piloto e base legal (LGPD) definidos com assessoria jurídica; checklist `docs/lgpd.md` revisado.
3. Revisão jurídica do componente do Agent SDK (D54) e do processamento por fornecedor de IA (Espec. D-12).
4. Chave de API em ambiente de piloto e medições pendentes rodadas: `LLM_MODE=record make accuracy` e `make chat-eval` (aceite ≥ 90 %, zero vazamento).
5. CI ativo e G1 fechado (EP-01 do backlog).
6. Ambiente de piloto separado do de desenvolvimento, com backup e restauração testados (NFR-007).

## 2. Amostra (hipótese)

> **Atualizado em 11/11/2026 (D88, D93).** A amostra passa a ser de **5 a 10 condomínios de 2 a 4 síndicos profissionais** em São Paulo capital: residenciais, com despesa acima de R$ 1 milhão por ano e administradora que entrega pasta digital; preferência por condomínio assumido nos últimos 6 meses ou com contrato grande a renovar. Oferta: diagnóstico de entrada (12 meses) e três meses de conferência mensal gratuitos, com termo assinado pelo condomínio (itens na Fase 6, seção 5, de `docs/reconcepcao/`), incluindo a cláusula de uso anônimo de preços (D92). O modo sombra (V2) cobre 12 meses. Os critérios de parada K1 a K9 da Fase 6 somam-se ao Go/No-go da seção 6. O texto abaixo fica como registro da hipótese anterior.

Até 3 condomínios individuais: um pequeno (síndico morador), um médio (60–200 unidades, com administradora e zelador), um maior ou condomínio-clube. Não tratar três pilotos como prova estatística. Primeiro piloto sugerido: o médio com documentação minimamente organizada e síndico acessível (Espec. §19.1).

Participantes por condomínio: síndico, um conselheiro, quem processa as despesas hoje (administradora ou o próprio síndico) e, quando houver, o revisor interno CondoOS.

## 3. Fases

| Fase | O que fazer | Evidência | Instrumento |
|---|---|---|---|
| V0 Entrevistas | 8–12 entrevistas (roteiro Espec. §19.2), com foco em despesas, contratos e o que o síndico nunca delegaria | Mapa de dores e frequências | Notas anonimizadas |
| V1 Baseline | 2–4 semanas: horas do síndico em conferência de despesas, contratos e cobranças; nº de despesas/mês; divergências encontradas hoje | Referência por condomínio | Diário de tempo (amostragem) + contagem de documentos |
| V2 Shadow mode | CondoOS audita 1–3 competências passadas sem contato externo; nenhum achado chega ao síndico sem revisão interna (se DV-02 = sim) | Precisão, falso positivo, tempo de revisão | Métricas internas (D60) + revisão humana amostral |
| V3 Optimize assistido | Achados e oportunidades revisados pelo revisor; síndico recebe só o aprovado | Taxa de oportunidades válidas; economia **estimada** | `opportunity` (CB-061) quando existir |
| V4 Execução supervisionada | **Fora do escopo** até G4: o produto não envia nada para fora | — | — |
| V5 Avaliação | Comparar com o baseline, entrevistas de saída, incidentes, custos | Go / Iterar / No-go por módulo | Este protocolo |

## 4. Métricas

| Indicador | Fórmula | Fonte no produto | Limitação |
|---|---|---|---|
| Precisão dos achados | confirmados ÷ decididos pelo síndico | `app/metrics.py` (D60) | Depende do síndico decidir |
| Extração automática | fiscais sem revisão ÷ fiscais processados | `app/metrics.py` | Medido sem chave: 40 % |
| Tempo de revisão | mediana da publicação à 1ª decisão | `app/metrics.py` | Mede o síndico, não a qualidade |
| Custo de IA por condomínio | soma `llm_calls.cost_usd` | `app/metrics.py` | Dólares; câmbio fora |
| Falso positivo | achados descartados/contestados com motivo procedente ÷ achados avaliados | `decision` + revisão amostral | Exige revisão humana |
| Divergências válidas (R$) | valor em risco dos confirmados | `finding` | **Não é economia realizada** |
| Horas líquidas poupadas | baseline − tempo com CondoOS − tempo de revisão gerado | Diário + log | Controlar sazonalidade |
| Acessos entre tenants | contagem auditada | `audit_log` `security.access_denied` (CB-003) | Meta: zero |
| Ações fora da política | contagem auditada | Motor de política (CB-010) | Meta: zero |
| Uso recorrente | sessões/semana do síndico | `user_session` (agregado) | Proxy de valor |

Metas exploratórias (a calibrar com o baseline, Espec. §17.6): 0 vazamento; 0 execução não autorizada; 100 % das recomendações revisadas por humano interno no primeiro ciclo; ≥ 90 % dos documentos prioritários catalogados com lacunas explícitas.

## 5. Dados de entrada (minimização)

Pedir: contratos e aditivos vigentes, notas e boletos de 3–12 competências, extratos (OFX/CSV/CNAB), convenção e atas que tratem de alçada e despesas, lista do corpo diretivo (nome e cargo, para R08). Não pedir: dados de moradores, biometria, imagens, acesso bancário direto, grupos de WhatsApp.

## 6. Go / No-go

- **Go Optimize:** achados com cálculo reproduzível, revisados, com ao menos algumas divergências confirmadas que gerem ação real (contestação, ajuste de contrato) e zero incidente de isolamento.
- **Iterar:** precisão baixa por regra específica (ajustar a regra com teste positivo e negativo), revisão interna cara demais, extração exigindo correção em excesso.
- **No-go / parar:** qualquer falha de isolamento entre condomínios, achado apresentado como fato sem evidência, uso de "fraude/desvio" em texto ao cliente, custo operacional inviável ou síndico sem uso recorrente.

## 7. Registro

Cada execução de piloto registra: condomínio (id), período, versões (commit, prompts, política), métricas desta seção e incidentes. Resultados em `docs/pilot/` (como `docs/pilot/run.md`), sem dados pessoais.
