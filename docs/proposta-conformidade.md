# Proposta: conformidade e vencimentos (FR-057, WP-16, primeiro corte)

Data: 09/11/2026. **Aguardando decisão do Marcio.** Nada foi escrito no código ainda.

Base: Especificação Mestra CAP-08 (conformidade, segurança e legal), FR-057 (P1: "vigência/aplicabilidade validada e lembretes"), Plano Diretor WP-16 (depende de WP-05 documentos e WP-07 assuntos/tarefas, ambos prontos) e Plano D-10 ("obrigações aplicáveis por condomínio: cadastro validado manualmente").

## 1. O problema

Documentos com validade (AVCB, apólice de seguro, laudos, certificados de manutenção) ficam espalhados entre pastas, fornecedores e administradora. Um documento vencido passa despercebido até alguém pedir. E a falta de registro no sistema **não** prova que a obrigação não foi cumprida (Especificação CAP-08).

## 2. O que já existe e é reaproveitado

| Peça | Onde | Uso aqui |
|---|---|---|
| Tipos de documento `apolice` e `laudo` | D91, `extraction/fields.py` | viram evidência de uma obrigação |
| Agenda com eventos previstos | D71, `app/agenda.py` | ganha o tipo de evento "vencimento de documento" |
| Hoje (briefing) | D82, `app/briefing/` | mostra o que vence nos próximos 30 dias |
| Pedido de documentos com link | D95, D103 | pedir a renovação ao fornecedor, já preenchido |
| Assuntos e tarefas | D80, `app/cases/` | "renovar o AVCB" vira um assunto com responsável e prazo |

## 3. O primeiro corte

**3.1 Obrigações do condomínio.** Cada condomínio tem uma lista de obrigações (ex.: "AVCB", "Seguro obrigatório da edificação", "Limpeza da caixa d'água"). Uma obrigação tem nome, categoria, periodicidade (em meses), antecedência do aviso (padrão 60 dias), responsável (fornecedor ou pessoa) e **aplicabilidade**: `a_validar`, `aplicavel` ou `nao_aplicavel`, sempre com quem validou, quando e por quê.

**3.2 Catálogo de candidatas.** Uma lista fixa no código com as obrigações mais comuns em condomínios (cerca de 12: AVCB/CLCB, seguro da edificação, extintores, mangueiras e hidrantes, SPDA/para-raios, elevadores, caixa d'água, controle de pragas, gás, instalações elétricas, inspeção predial, bombas e geradores). Ao ativar, elas entram como `a_validar`. **O sistema não afirma que uma obrigação se aplica nem cita norma:** regras mudam por município, estado e equipamento (Especificação CAP-08). A periodicidade aparece como "sugestão, confirme com o responsável técnico" até uma pessoa confirmar. O síndico também cria obrigações próprias.

**3.3 Evidência.** Para cada obrigação, a pessoa liga um documento (apólice, laudo, certificado, AVCB) e informa **emissão e validade**. Sem validade informada, a situação é "documento sem validade registrada". Cada evidência é uma linha nova; a mais recente vale. Nada é apagado.

**3.4 Situação, calculada a cada leitura** (como a prontidão do Launch, nunca gravada):

| Situação | Quando | Texto na tela |
|---|---|---|
| Em dia | validade depois da antecedência | "Documento válido até 12/08/2027" |
| Vence em breve | dentro da antecedência | "Vence em 45 dias (12/08/2027)" |
| Vencido | validade já passou | "Documento registrado venceu em 12/08/2026" |
| Sem documento | aplicável e sem evidência | "Nenhum documento registrado no CondoOS" (nunca "não cumprida") |
| A validar | catálogo ainda não confirmado | "Confirme se se aplica ao condomínio" |

Palavras proibidas na tela e no chat: "irregular", "em conformidade", "conforme". Declarar conformidade é proibido à IA (Especificação §9, tabela de autonomia).

**3.5 Onde aparece.**
- **Conformidade** (nova tela; no celular, em Ajustes; no desktop, menu lateral): lista por situação, com o vencido e o "vence em breve" no topo.
- **Agenda**: evento "vencimento" na data de validade e "aviso" na data da antecedência.
- **Hoje**: "2 documentos vencem nos próximos 30 dias".
- **Ações rápidas** numa obrigação: "Pedir documento ao fornecedor" (abre o pedido de D95 preenchido) e "Criar assunto" (renovação com responsável e prazo).
- **Chat**: ferramenta de leitura `list_compliance` (com `ref`, caso novo na avaliação).

**3.6 Quem pode o quê.**

| Ação | Síndico | Conselheiro | Gerente da administradora | Analista | Admin CondoOS |
|---|---|---|---|---|---|
| Ver | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ativar o catálogo, criar obrigação, registrar evidência | ✓ | — | ✓ | ✓ | ✓ |
| Validar aplicabilidade e periodicidade | ✓ | — | ✓ | — | — (pode sugerir) |

**3.7 Nada sai do sistema.** Os avisos ficam só dentro do app (Hoje e Agenda), como o briefing (D82). Lembrete por e-mail seria um segundo envio externo e pede decisão nova.

## 4. Modelo (migração 0024)

| Tabela | Campos principais | Regras |
|---|---|---|
| `compliance_obligation` | condomínio, chave do catálogo (ou nula), nome, categoria, periodicidade (meses, nula até validar), antecedência (dias), fornecedor responsável (opcional), aplicabilidade, validado por/em, motivo, `archived_at` | RLS; arquivar em vez de apagar |
| `compliance_evidence` | obrigação, documento (opcional), emissão, validade, registrado por/em, nota | RLS; só inclusão |
| `compliance_event` | obrigação, tipo (criada, validada, evidência, arquivada), autor, detalhe | RLS; só inclusão (trilha) |

A volta da migração apaga as três tabelas (nenhum dado existente é alterado).

## 5. Fora deste corte

- Leitura automática da validade pela IA na apólice e no laudo (segundo corte, sempre "a confirmar").
- Perfil da edificação que sugere obrigações por características (CAP-08.01 completo).
- Dossiê por obrigação em PDF (CAP-08.06), lembrete por e-mail ou WhatsApp, ordens de serviço (FR-051/052).

## 6. Testes previstos

Situação calculada nas 5 condições e na troca de evidência; catálogo entra como `a_validar` e não gera aviso até validar; `nao_aplicavel` some dos avisos; papéis (conselheiro só vê, analista não valida); isolamento entre condomínios (RLS); tabelas só de inclusão; nenhum texto com as palavras proibidas; Agenda e Hoje mostram o vencimento; chat com o caso novo; E2E: ativar o catálogo, validar o AVCB, ligar o documento com validade e ver "vence em breve" no Hoje.

## 7. Decisões que preciso

1. **Aprovar o primeiro corte e a migração 0024** como descritos (seções 3 e 4).
2. **Catálogo com periodicidade sugerida** marcada "confirme com o responsável técnico" (recomendo), ou sem nenhuma periodicidade até alguém informar?
3. **Quem valida a aplicabilidade:** síndico e gerente da administradora (recomendo), ou só o síndico?
4. **Validade digitada pela pessoa** neste corte, com a leitura pela IA no segundo (recomendo), ou já com a IA sugerindo a data "a confirmar"?
5. **Antecedência padrão de 60 dias**, ajustável por obrigação (recomendo)?
