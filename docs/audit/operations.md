# Rotina mensal e reprocessamento

0. Uma vez (e quando mudar): em **Audit › Unidades e receitas**, importar as unidades e responder o **perfil de auditoria** (funcionários próprios, parcelamento, ISS retido, rateios).
1. Importar a **lista de títulos** do mês (CSV da administradora; colunas de nome são descartadas) e, se houver rateio, as **leituras**.
2. Receber os documentos do mês pelos canais existentes (upload, e-mail, link) e o **extrato em OFX** de cada conta (o OFX identifica a conta e traz o saldo final; CSV com linhas "saldo anterior" e "saldo" também serve).
2. Corrigir a fila de exceções da leitura.
3. No desktop, **Audit › Farol**, escolher condomínio e mês e **Rodar auditoria do mês**. Pode rodar quantas vezes quiser: o que não mudou é reaproveitado.
4. Abrir cada controle Pendente ou Divergente: o motivo diz o que falta; "Pedir documento" abre o pedido já preenchido.
5. **Audit › Revisão da auditoria**: a equipe CondoOS (ou o gerente, se o condomínio permitir) confirma ou reclassifica com motivo.
6. Novo documento ou extrato: rodar de novo; só os controles afetados mudam e o histórico fica.

Não há execução automática por evento (ciclo 4).

## Fundos, orçamento e aprovação das contas (ciclo 3, D124)

Em **Audit → Fundos e orçamento**: marque o tipo de cada conta (a de aplicação tem extrato próprio), crie os fundos e indique as contas que os guardam, importe os saldos dos fundos do demonstrativo (CSV `fundo; competencia; saldo inicial; entradas; saidas; rendimentos; saldo final`), importe o orçamento aprovado do ano (CSV `categoria; mes; valor`, linha sem mês é anual) com a data e a ata, registre a explicação de cada desvio acima de 10% e a aprovação das contas (conselho ou assembleia, com o documento e os signatários).

## Apreciação pelo síndico (D124)

1. Rode o mês e revise o que aguarda revisão humana (Revisão da auditoria).
2. No Farol, quadro "Apreciação pelo síndico" → **Enviar ao síndico** (só `review_audit`; fica bloqueado enquanto houver revisão pendente). O conteúdo é congelado com SHA-256.
3. O síndico abre **Finanças → Auditoria** no app e aprova ou devolve com motivo. Quem enviou não aprova.
4. Se uma execução nova mudar um resultado depois do envio, o envio vira "substituído": revise e envie de novo.
5. Depois de aprovado, o conselho e o subsíndico leem o mês na mesma aba. Se uma revalidação mudar um mês aprovado, a tela avisa e a equipe reenvia.

## Revalidação histórica

No Farol, **Revalidar os últimos 6 meses** (ou `POST /condominiums/{id}/audit/revalidate` com `months` até 12): roda do mês mais antigo ao mais novo, reaproveita o que não mudou e substitui (sem apagar) o que mudou. Use depois de chegar a ata de aprovação das contas (DOC-03) ou um documento atrasado.
