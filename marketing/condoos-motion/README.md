# CondoOS Optimize: filme de apresentação (Remotion)

Filme vertical (1080 × 1920, 30 fps) que conta a história de um condomínio perdendo dinheiro com custos que ninguém vê e do CondoOS Optimize analisando contratos, priorizando oportunidades, passando pela **revisão interna CondoOS** e chegando à **decisão do condomínio**.

Projeto **independente** da aplicação: não importa nada de `web/` nem de `api/`, não precisa de backend e renderiza sem rede (a fonte Inter fica em `public/assets/fonts`). Todos os dados são fictícios e o filme diz isso na tela.

## Uso

```bash
cd marketing/condoos-motion
npm install
npm run studio      # prévia editável (Remotion Studio, http://localhost:3000)
npm run render      # out/CondoOS-Hero-Film-60s-9x16.mp4 e out/CondoOS-Hero-Film-15s-9x16.mp4
npm run stills      # quadros de QA em out/stills/ (node scripts/stills.mjs <id> <quadros>)
npm run typecheck
```

Sem download do Chrome (ambiente fechado), aponte para um Chrome headless shell local:
`REMOTION_BROWSER=/caminho/chrome-headless-shell npm run render`.

## O que dá para editar no Studio

No painel de propriedades (à direita), sem mexer no código:

- `headlines.*`: o texto de cada cena. `/` quebra a linha e `*palavras*` ficam em destaque (âmbar no problema, verde-lima depois que o CondoOS entra).
- `brand.tagline1` e `brand.tagline2`: a assinatura final.
- `demoLabel`, `showHud`: aviso de dados de demonstração e moldura.
- `audioSrc` e `audioVolume`: trilha opcional. Coloque um arquivo **licenciado** em `public/assets/audio/` e informe o caminho (ex.: `assets/audio/trilha.mp3`). Vazio = filme sem áudio. Entra e sai em fade.

Números e nomes ficam em `src/data/demoFixtures.ts`. Os valores derivados são calculados ali, nunca digitados duas vezes: a diferença de R$ 956,80 por mês que aparece no custo, na varredura e na revisão vem de `18.400 × (9,8% − 4,6%)`.

## Estrutura

```
src/
  Root.tsx                    composições HeroFilm60 e HeroFilm15 (mesmo esquema de props)
  schema.ts                   props editáveis (zod) e valores padrão
  compositions/Film.tsx       fundo, cenas com cross-fade, HUD, áudio
  compositions/HeroFilm60.tsx linha do tempo do master (1.800 quadros)
  compositions/HeroFilm15.tsx corte de 15 s: as mesmas cenas, aceleradas (speed) ou recortadas (startAt)
  scenes/                     uma cena por arquivo, cada uma no seu próprio relógio base
  components/CondoOSMockUI.tsx reconstruções visuais dos componentes reais (Badge, OpportunityCard,
                              SavingsStageCard, EvidenceItem, KpiCard, Button, AdminShell, Logo)
  components/Building.tsx     o prédio (motivo de abertura e fechamento)
  components/KineticText.tsx  tipografia cinética
  design/condoosTokens.ts     tokens do Design System v1.0 (copiados de web/app/globals.css)
```

## Roteiro (60 s)

| Tempo   | Cena                                                                                   | Texto                                                     |
| ------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 0–6 s   | Planta do prédio; gotas âmbar escapam nas junções (contratos)                          | Nem todo vazamento faz barulho.                           |
| 6–12 s  | A câmera atravessa 12 faturas mensais; a diferença acumula                             | Alguns aparecem no orçamento. Todo mês.                   |
| 12–20 s | Os vazamentos convergem no "C"; varredura do contrato, cláusula 7.2, evidências        | E se fosse possível encontrar o que ninguém percebeu?     |
| 20–29 s | A tela do produto se abre em quatro camadas 3D                                         | Uma inteligência que analisa seus contratos.              |
| 29–39 s | Três oportunidades, ordenadas pelo valor; detalhe; a revisora aprova para o condomínio | Detecta. Prioriza. Recomenda.                             |
| 39–49 s | KPIs contam; fluxo Análise → Revisão interna → Recomendação → Decisão do condomínio    | Do diagnóstico à decisão.                                 |
| 49–55 s | Volta ao prédio: cada junção é selada e o fluxo corre limpo                            | Mais controle. Menos desperdício.                         |
| 55–60 s | As linhas formam o logo CondoOS                                                        | Menos desperdício. Mais inteligência para seu condomínio. |

O corte de 15 s usa: gancho (prédio), varredura, aprovação na revisão, prédio selado e assinatura.

## Cuidados de conteúdo

- Empresas com "Fictícia" no nome, sem CNPJ ou CPF; aviso "Dados de demonstração" em todos os quadros.
- Achado, oportunidade e estágios da economia aparecem separados; a soma de R$ 29.241,60 é só do estágio "potencial" das três oportunidades e é rotulada como ilustrativa, não como economia capturada.
- A revisão interna CondoOS acontece antes de a oportunidade chegar ao condomínio; a decisão é sempre do condomínio e o sistema não paga nem contrata nada.
- Linguagem: "divergência", nunca "fraude" ou "desvio".

## Licenças

- Remotion 4.0.538: licença própria da Remotion (gratuita para pessoas físicas, empresas com até 3 funcionários e entidades sem fins lucrativos; acima disso exige licença de empresa). Uso aprovado pelo Marcio em 11/11/2026 (D88), só nesta peça de marketing, fora do produto.
- Inter: SIL Open Font License 1.1 (`public/assets/fonts/LICENSE-Inter-OFL.txt`).
- lucide-react: ISC. React: MIT. zod: MIT.
- Nenhuma música incluída; use apenas trilhas licenciadas.
