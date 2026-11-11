# Rotina mensal e reprocessamento

1. Receber os documentos do mês pelos canais existentes (upload, e-mail, link) e o **extrato em OFX** de cada conta (o OFX identifica a conta e traz o saldo final; CSV com linhas "saldo anterior" e "saldo" também serve).
2. Corrigir a fila de exceções da leitura.
3. No desktop, **Audit › Farol**, escolher condomínio e mês e **Rodar auditoria do mês**. Pode rodar quantas vezes quiser: o que não mudou é reaproveitado.
4. Abrir cada controle Pendente ou Divergente: o motivo diz o que falta; "Pedir documento" abre o pedido já preenchido.
5. **Audit › Revisão da auditoria**: a equipe CondoOS (ou o gerente, se o condomínio permitir) confirma ou reclassifica com motivo.
6. Novo documento ou extrato: rodar de novo; só os controles afetados mudam e o histórico fica.

Publicação ao síndico e aprovação formal das contas entram no ciclo 3. Não há execução automática por evento no ciclo 1 (ciclo 4).
