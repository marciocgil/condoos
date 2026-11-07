# Launch — testes, pilotos e métricas

Data: 07/11/2026. Base: suíte atual (pytest com PostgreSQL 16 + pgvector, `tests/test_isolation.py`, Playwright em `web/tests/e2e`, LLM em replay). Nenhum teste novo foi escrito nesta fase.

## 1. Cenários de teste por fase

| Fase | Positivos | Negativos / segurança |
|---|---|---|
| LF2 | Contrato do corpus → primeiro valor com trechos; objetivo persiste entre dispositivos; marcos do seed (Acácias LM1–LM3; novo só LM1) | Campo < 0,9 nunca como fato; nota fiscal no lugar do contrato; arquivo corrompido/vazio/grande/duplicado; conselheiro não escolhe objetivo (403); outro condomínio (404 + evento); PDF com instrução maliciosa (SEC-02); condomínio sem alçada não pede ação |
| LF3 | Fatura casada com contrato; contrato sem cobrança aparece; conflito resolvido com versão prevalente | Contrato × aditivo divergentes bloqueiam C3; relatório com fila aberta nunca "completo"; fornecedores homônimos em dois condomínios |
| LF4 | Administradora envia pelo link; cobertura do pedido atualiza | Token expirado/revogado → 404 genérico; token de A não grava em B; link não lê nada; excesso de arquivos recusado |
| LF5 | E-mail real (mock) entrega documento; documento esperado chega por outro canal e não vira pendência | E-mail desconectado vira alerta; mensagem enviada ≠ entregue; duplicata não conta duas vezes |
| LF6 | Novo síndico assume com histórico preservado | Aprovação pendente do anterior suspensa; acesso residual negado; dados bancários sempre negados |

Regra mantida: mudança de regra exige teste positivo e negativo e `test_planted_cases.py` exato (CLAUDE.md).

## 2. Métricas (metas candidatas, não resultados)

| Métrica | Definição | Fonte | Meta candidata |
|---|---|---|---|
| Tempo até primeiro valor | primeiro login do síndico → `launch.first_value_shown` | `audit_log` | mesma sessão com documento elegível; ≤ 48 h após dados mínimos |
| Esforço do síndico | minutos ativos na jornada (eventos) | `audit_log` | medir; baseline no piloto |
| Horas humanas de implantação | horas da equipe CondoOS e administradora por condomínio | diário do piloto (fora do produto, como D84) | ≤ 2 h simples / ≤ 4 h padrão (hipótese) |
| Acurácia crítica | por campo e tipo, com amostra auditada | `make accuracy`, `extraction_correction` | definida por risco; hoje 12/30 sem revisão sem LLM |
| Correções por documento | `extraction_correction` / documentos | banco | medir |
| Cobertura | documentos esperados recebidos / esperados, por competência | `pending.py` | medir |
| Ativação | condomínios com capacidade em `supervisionada` e usada no mês | `readiness` + uso | medir |
| Retomada e abandono | dias sem evento com jornada ativa; retorno após adiar | `audit_log` | medir |
| Custo de IA por documento e por implantação | `llm_calls.cost_usd` | banco | medir (teto mensal já existe) |
| Ações críticas não autorizadas | ações L5 executadas | `action_decision` | **zero** |

Separar sempre: progresso visual × prontidão × uso real × economia realizada × trabalho manual evitado.

## 3. Experimentos (LF7, com pilotos autorizados)

1. Documento primeiro × cadastro primeiro (tempo, valor percebido).
2. Faça comigo × Faça por mim × Delegue (esforço, erros).
3. Conquistas funcionais × checklist (continuidade, compreensão).
4. Pedido automatizado × manual (tempo de obtenção) — só após Q-L02.
5. Prontidão por capacidade × barra global (ativações indevidas).

Privacidade: só ids e eventos; nenhum conteúdo de documento em métrica. Painel por piloto na tela Métricas existente (`/admin/metricas`).
