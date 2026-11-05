# Mockups de referência

Descrição das 4 telas enviadas pelo Marcio em 05/11/2026 (páginas 5 e 6 do PDF de arquitetura). Os dados das telas são fictícios. As telas implementadas devem seguir esta estrutura.

## Síndico — Resumo do mês (celular)

- Cabeçalho: nome do condomínio e, abaixo, o mês por extenso ("outubro 2026").
- Cartão de destaque com fundo azul-claro e borda azul: valor grande ("R$ 18.420"), "em risco este mês" e "7 achados · 2 graves".
- Três chips com borda colorida: "2 graves" (vermelho), "3 médios" (amarelo/âmbar), "2 baixos" (cinza).
- "Principais achados": cartões com título em negrito ("Pagamento duplicado"), segunda linha "Fornecedor · R$ valor" e um ponto colorido de severidade à direita.
- Botão "Pergunte ao CondoOS" largo, contornado em azul, no fim do conteúdo (não flutuante).
- Abas inferiores: Resumo · Achados · Contratos · Histórico, com a aba ativa em negrito.
- Valores arredondados para reais inteiros nos destaques ("R$ 6.200").

## Síndico — Detalhe do achado (celular)

- Link "‹ Achados" para voltar.
- Selo de severidade contornado ("Grave", em vermelho).
- Título grande ("Pagamento duplicado") e, abaixo, "Fornecedor · CNPJ ativo".
- Valor em risco em destaque ("R$ 6.200,00") com a legenda "valor em risco".
- Seção "Por que foi apontado": explicação curta em linguagem simples.
- Seção "Evidências": uma linha por evidência, em cartões ("NF 4471 · 03/10 · R$ 6.200", "Extrato · 2 débitos iguais").
- Três botões lado a lado: Confirmar (primário, azul) · Contestar · Ignorar.
- Rodapé "Validado pela administradora" nos achados graves.

## Síndico — Chat "Pergunte ao CondoOS" (celular)

- Título "Pergunte ao CondoOS" e o nome do condomínio.
- Pergunta do usuário em balão cinza à direita.
- Resposta em cartão com borda azul; o número principal em negrito ("R$ 4.880").
- "Fontes": chips clicáveis ("Contrato §5.2", "NF 3981").
- Ação sugerida como botão largo azul-claro ("Abrir achado de reajuste").
- Campo "Pergunte sobre o condomínio…" e a nota "Só dados deste condomínio".

## Administradora — Carteira (desktop)

- Barra superior: "CondoOS · Nome da administradora".
- Menu lateral: Carteira (item ativo com fundo azul-claro) · Fila de exceções (contador em círculo amarelo) · Fornecedores · Contratos · Configurações. Botão "Pergunte à IA" contornado no pé do menu.
- Título "Carteira" e o subtítulo "4 condomínios · outubro 2026".
- Três indicadores em cartões contornados: "R$ 60.910 em risco na carteira", "22 achados abertos · 5 graves", "2 itens na fila de exceções".
- Tabela: Condomínio · Em risco · Achados · Graves · Status. Status em pílula: "Revisar" (borda amarela) ou "Enviado" (borda verde).
- Abaixo da tabela, a seção "Fila de exceções", com uma linha por item, ponto colorido e botão à direita:
  - amarelo: "Extração com baixa confiança: NF ilegível · Condomínio" → **Corrigir**
  - vermelho: "Grave: sócio do fornecedor é conselheiro · Condomínio" → **Validar**

## Paleta observada

- Azul de ação: borda `#2f7bd8` aproximado, fundo azul-claro `#e6f0fb`.
- Vermelho (grave): `#d64545`. Âmbar (médio): `#f2b51c`. Verde (enviado): `#2e9e3e`. Cinza (baixo): `#c9c6bb`.
- Cartões brancos com borda cinza-clara e cantos arredondados; tipografia sem serifa, pesos regular e semibold.
