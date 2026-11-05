# Execução do piloto — do upload ao relatório

Gerado por `make pilot` em 05/11/2026. Condomínio fictício **Bosque dos Ipês**, 30 documentos do corpus + extrato OFX de outubro/2026.

**Tempo total: 0:01:52** (limite: 15 minutos) — aceito.

| Etapa | Duração | Detalhe |
|---|---|---|
| 1. Condomínio cadastrado | 0.3 s | 9c529aec-0892-4ed5-b5ee-c2b506dc28d1 |
| 2. Contrato enviado e registrado | 21.5 s | 1 contrato(s), 1 correção(ões) |
| 3. 29 documentos e o extrato de outubro enviados | 0.3 s |  |
| 4. Extração, casamento e regras concluídos | 57.3 s | 0 job(s) com falha |
| 5. Fila de exceções tratada pela analista | 28.5 s | 18 documento(s) corrigido(s), 0 casamento(s) resolvido(s) |
| 6. Gerente validou os achados graves | 3.3 s | 1 validado(s) |
| 7. Competência 10/2026 fechada e relatório publicado | 0.2 s |  |
| 8. Síndica baixou o relatório | 0.2 s | 13 achado(s) no relatório |

## Resultado

- Documentos sem revisão manual: 12 de 29 (sem chave de API; ver `docs/extraction_accuracy.md`). Os demais foram corrigidos pela analista com o gabarito do corpus, pela mesma tela/API de correção.
- Achados no relatório: 13 (R01: 1, R10: 11, R12: 1); valor em risco: R$ 26.546,60.
- Arquivos: `relatorio-bosque-dos-ipes-2026-10.pdf` e `relatorio-bosque-dos-ipes-2026-10.xlsx` nesta pasta.

O tempo mede a execução do sistema (processamento, chamadas da interface e jobs); a leitura dos documentos pela analista é feita pelo script instantaneamente.
