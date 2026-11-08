# 10 — Registro de fontes e evidências

Todas as fontes acessadas em **08/11/2026**, salvo indicação. Qualidade: **alta** (órgão oficial, lei, registro, fonte primária do fornecedor) · **média** (estudo de empresa/entidade com metodologia parcial) · **baixa** (matéria sem metodologia, dado antigo, resumo de busca). **NV** = conteúdo visto só por resumo de busca ou bloqueado.

## 1. Fontes internas (repositório `marciocgil/condoos`)

| Fonte | Uso | Observação |
|---|---|---|
| `CLAUDE.md` | Estado do produto, regras, limites | Base para "o que existe" |
| `docs/condoos-planning/02_Contexto_Produto/CondoOS_Assessor_Inteligente_Especificacao_Mestra_v1.0.md` (06/11/2026) | Proposta de valor, módulos, personas, métricas, riscos | Lidas §§1–4, 17, 23 integralmente; demais por sumário |
| `docs/product-roadmap.md`, `docs/roadmap-status.md` (07/11/2026) | Marcos, gates, FR cobertos | — |
| `docs/decisions.md` (D72–D85) | Condomínio cliente, revisão proporcional, economia por estágio, política de ações | Lidos via `CLAUDE.md` e roadmap |
| `web/app/globals.css`, `web/app/layout.tsx`, `web/components/layout/Logo.tsx` | Design System e pontos visíveis da marca | — |
| `git log` | Primeiro commit: 05/11/2026 | — |

**Materiais citados no prompt e não encontrados no repositório:** "CondoOS Launch — Prompt Mestre Unificado"; pesquisas anteriores de modelo de negócio, público e concorrência. O Plano Diretor (.docx) existe mas não foi relido nesta etapa (o roadmap derivado dele foi).

## 2. Usos do nome "CondoOS" e domínios

| Fonte | URL | Conteúdo de suporte | Qualidade | Limitação |
|---|---|---|---|---|
| CondoOS (SL20) | https://condoos.sl20.com.br/ | Gestão condominial, preços R$ 89/189, © 2026 | alta (uso) | Sem CNPJ |
| SL20 Sistemas | https://sl20.com.br/ | Portfólio "XxxOS", CondoOS para síndicos e administradoras | alta | — |
| GitHub `csnegrao/condoos` | https://github.com/csnegrao/condoos | Criado em 24/05/2026 | alta | — |
| crt.sh | https://crt.sh/?q=condoos.sl20.com.br | 1º certificado em 24/05/2026 | alta | Certificado ≠ início de vendas |
| CondoOS Chile | https://www.condoos.cl/ (+ termos e privacidade) | "El sistema operativo de los edificios modernos en Latinoamérica"; CondoOS Tecnología SpA | alta | RUT não conferido em registro oficial |
| NIC Chile | https://www.nic.cl/ | condoos.cl em nome da SpA desde 15/06/2026 | alta | — |
| CondoOS by Sphere | https://condoos.sphereinc.com/ (+ pricing, terms) | Flórida, Comply/Operate/Maintain, "from $99 a month", termos de 28/05/2026 | alta | — |
| RDAP Registro.br | https://rdap.registro.br/domain/condoos.com.br | Registrado em 15/02/2026, pessoa física | alta | Disponibilidade ≠ ausência de registro |
| RDAP Verisign | https://rdap.verisign.com/com/v1/domain/condoos.com | Registrado em 05/05/2026 (DropCatch) | alta | — |
| USPTO tmsearch (API) | https://tmsearch.uspto.gov/ | 0 resultados para CONDOOS e variantes | alta | Pedidos muito recentes podem faltar |
| INPI pePI | https://busca.inpi.gov.br/pePI/ | **NV** — conexão recusada/503 | — | Refazer de rede brasileira |
| WIPO GBD | https://branddb.wipo.int/ | **NV** — captcha | — | Manual |
| TMview | https://www.tmdn.org/tmview/ | **NV** — rejeitado | — | Manual |
| INAPI | https://www.inapi.cl/ | **NV** — bloqueado | — | Manual |

## 3. Triagem dos nomes candidatos

| Fonte | URL | Achado | Qualidade |
|---|---|---|---|
| RDAP Registro.br / Verisign | rdap.registro.br, rdap.verisign.com | Resultados da tabela `06`, §3 | alta |
| USPTO tmsearch (API) | tmsearch.uspto.gov | Contagens e registros citados em `05`/`06` (ex.: PROBO, Probo Inc., pedido 06/2026; PILASTRA, pedido classe 42, 19/08/2026) | alta |
| App Store (API de busca) | https://itunes.apple.com/search | Apps "Aprumo" (24/09/2026), "Aprumo Financeiro" (20/09/2026), "Tino – Finanças com IA" (28/08/2026), "Condora – Gestão de Condomínios", "Zelo Condomínios – Facilities", "Zello Administradora", "CIENT Contabilidade" | alta |
| useaprumo.com | https://www.useaprumo.com/ | "Aprumo · your personal hub for money, workouts, travel and studying" | alta |
| pilastra.com.br | https://pilastra.com.br/ | "Pilastra — Infraestrutura de IA privada e conforme para educação" | alta |
| pilastraapp.com | https://pilastraapp.com/ | "Pilastra — Construction Field Management App" | alta |
| vertio.com.br | https://vertio.com.br/ | "Vertio - Infraestrutura Técnica e Marketing Ops" | alta |
| Lastro (proptech) | https://startups.com.br/negocios/proptechs/proptech-lastro-levanta-serie-a-de-r-85m-liderada-pela-prosus/ ; https://exame.com/negocios/lastro-quer-mudar-aluguel-no-brasil-captacao-4-milhoes-dolares/ | Proptech de SP, Série A R$ 85 mi (Prosus), agente de IA "Lais" | média (imprensa) |
| Atesta CFM | https://agenciabrasil.ebc.com.br/saude/noticia/2024-09/cfm-lanca-plataforma-para-combater-emissao-de-atestados-falsos/ | Plataforma oficial do CFM | média-alta |
| Esteio Gestão (App Store) | https://apps.apple.com/us/app/id6633447896 | App agro, 2025 | alta |
| Condora (App Store) | https://apps.apple.com/br/app/condora/id6758959663 | "Condora – Gestão de Condomínios", Rocketbr | alta |
| Zelo Facilities / Zello | https://apps.apple.com/us/app/id6444430939 ; https://apps.apple.com/app/id6476882276 | Apps de condomínio | alta |

## 4. Concorrência (ver `02`)

| Marca | URL | Dado usado | Qualidade | Limitação |
|---|---|---|---|---|
| Superlógica | https://superlogica.com/condominios | Categoria, tagline, "+3 mil" administradoras, "+100 mil" condomínios | alta | Nexus via SíndicoNet (NV no fornecedor) |
| Group Software | https://www.groupsoftware.com.br/ | Tagline, IA genérica | alta | — |
| uCondo | https://www.ucondo.com.br/ | Tagline, "700 mil clientes", Móra, Copiloto (beta) | alta | — |
| TownSq | https://www.townsq.com.br/ | "Pare de apagar incêndios.", 35 mil condomínios | alta | — |
| Winker | https://www.winker.com.br/ | Tagline, IA de atendimento | alta | — |
| Condomob | https://condomob.net/ | Tagline, números | alta | Números divergentes no próprio site |
| Plin | (via SíndicoNet) | "Sistema operacional do gestor", preço 2022 | baixa (NV) | Dado antigo |
| CondoConta / Sindia | https://www.condoconta.com.br/ | Tagline; Sindia via publieditorial SíndicoNet (22/09/2026) | alta / baixa (NV) | /sindia 404 |
| SíndicoNet PRO | https://www.sindiconet.com.br/ | R$ 97/117/147 por mês (14/09/2025) | alta | — |
| Lello | https://www.lellocondominios.com.br/ | Tagline | alta | — |
| Hubert | https://www.hubert.com.br/ | Tagline | alta | — |
| Condofy | https://www.condofy.com.br/ | Tagline, 140+ condomínios, depoimento ~20% | alta | Depoimento |
| BRCondos | https://www.brcondos.com.br/ | Tagline | alta | — |
| Easy Alert | https://easyalert.com.br/ | R$ 249–599/mês + R$ 500 | alta | Preço em 2026 |
| Auditores autônomos | https://www.ohub.com.br/ | Formatos de auditoria | baixa | Diretório |
| Consultorias por êxito | (matéria 2016) | ~50% da economia | baixa (NV) | Dado antigo |
| AppFolio | https://www.appfolio.com/ | Tagline, IA agêntica | alta | — |
| Buildium | https://www.buildium.com/pricing/ | US$ 65/202/420 | alta | — |
| Vantaca | https://www.vantaca.com/ | "An AI workforce that does the work" | alta | — |
| CINC Systems | https://www.cincsystems.com/ | "while keeping people in control" | alta | — |
| FRONTSTEPS | https://www.frontsteps.com/ | ALLi | alta | — |
| EliseAI | https://eliseai.com/ | Tagline | alta | — |
| PRGX | https://www.prgx.com/ | US$ 1,8 bi recuperados/ano | alta (autodeclarado) | — |

## 5. Mercado e voz do cliente (ver `01`)

| Afirmação | Fonte / URL | Data | Qualidade | Limitação |
|---|---|---|---|---|
| 13,3 mi de endereços em condomínios (12,4%) | IBGE CNEFE via SíndicoNet: https://www.sindiconet.com.br/informese/condominios-cnefe-censo-2022-noticias-mercado | 18/06/2024 | alta/média | Endereços, não condomínios |
| 12,5% em apartamento (2022) | IBGE Agência de Notícias: https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/39239-censo-2022-cerca-de-oito-a-cada-dez-pessoas-moravam-em-casas-mas-cresce-proporcao-de-moradores-em-apartamentos | fev/2024 | alta | Confirmar na página |
| 327.248 condomínios ativos | Censo Condominial uCondo via Estado de Minas: https://www.em.com.br/mundo-corporativo/2026/08/7474336-censo-2026-revela-dados-do-mercado-condominial-brasileiro.html | 05/08/2026 | média | Estudo de empresa |
| >520 mil condomínios | SíndicoNet/Folha: https://www.sindiconet.com.br/informese/cresce-demanda-sindicos-profissionais-noticias-mercado | 26/02/2024 | baixa | Sem fonte nomeada |
| SP: 31 mil condomínios, orçamento médio R$ 779.150, cota R$ 983, composição da despesa | Lello, Mapa dos Condomínios 2025: https://www.sindiconet.com.br/informese/mapa-dos-condominios-2025-noticias-radar-lello/amp | 07/04/2025 | média | Metodologia não informada |
| Boleto médio R$ 516 (+24,9%) | InfoMoney: https://www.infomoney.com.br/consumo/taxa-de-condominio-sobe-25-no-brasil-e-atinge-media-de-r-516-em-2025/ | 29/12/2025 | média | Base uCondo |
| 46% profissionais; 8 condomínios; 32 h vs 19 h; 67% decidem finanças sozinhos; 74% usam plataforma; canais Google 93%, YouTube 74%, Instagram 67% | Datafolha/Superlógica via SíndicoNet: https://www.sindiconet.com.br/informese/quase-a-metade-dos-sindicos-brasileiros-ja-sao-profissionais-noticias-administracao/amp | 04/12/2025 | média | 350 entrevistas; patrocinador do setor |
| "Boa gestão" 49,7%; "transparência, proatividade e planejamento" | Raio-X SíndicoNet 2026: https://www.sindiconet.com.br/informese/raio-x-sindiconet-boa-gestao-colunistas-leonardo-diniz-mascarenhas/amp | 25/03/2026 | média | Autosselecionada |
| 42,2% preferem IA + atendimento humano | SíndicoNet/Conami: https://www.sindiconet.com.br/informese/inteligencia-artificial-condominios-noticias-administracao | 11/11/2025 | baixa | Sem amostra |
| Código Civil arts. 1.347–1.350, 1.356 | via SíndicoNet: https://www.sindiconet.com.br/informese/integra-administracao-legislacao-codigo-civil-capitulo-sobre-condominios | — | alta (lei) | Planalto bloqueado; conferir texto oficial |
| Assessoria jurídica privativa da advocacia | Lei 8.906/94, art. 1º | — | alta | — |
| Cartilha OAB-GO sobre exercício ilegal da advocacia em relações condominiais | https://www.oabgo.org.br/wp-content/uploads/2026/09/CARTILHA-Exercicio-Ilegal-d-Advocacia-nas-Relacoes-Condominiais.pdf | set/2026 | **NV** (só resumo) | PDF não abriu |
| Auditoria: ~R$ 10 mil/ano investigativa; ~R$ 1 mil/mês preventiva | SíndicoNet: https://www.sindiconet.com.br/informese/auditoria-em-condominios-noticias-administracao-1/amp | 08/08/2012 | baixa | Dado de 2012 |
| Reclamações sobre prestação de contas | Reclame Aqui (URLs em `01`, §4.1; páginas com 403, títulos das URLs) | 2024–2026 | baixa como estatística | Quem reclama é condômino |
| Remuneração do síndico (uCondo R$ 1.520; CAGED R$ 2.977,58) | InfoMoney: https://www.infomoney.com.br/?p=3155148 | 29/12/2025 | média | Base não clara |

## 6. Referências de método

| Fonte | URL | Uso |
|---|---|---|
| INPI — classificação de marcas | https://www.gov.br/inpi/pt-br/servicos/marcas/classificacao-marcas | Classes Nice (`06`, §5) |
| INPI — Manual de Marcas | https://manualdemarcas.inpi.gov.br/ | Referência para o advogado (não consultado em detalhe) |
| Lei 9.279/96 (art. 124, VI; art. 129, §1º) | https://www.planalto.gov.br/ccivil_03/leis/l9279.htm | Citada; **texto não conferido nesta sessão** (Planalto bloqueado) |

## 7. Limitações gerais

1. **Nenhuma pesquisa primária** (entrevista, survey, teste) foi feita.
2. **INPI, WIPO, TMview e INAPI não foram acessíveis** desta rede: nenhuma conclusão sobre registro no Brasil.
3. A busca web disponível indexa mal sites pequenos e recentes (não indexou nem os três sites "CondoOS"); ausência em busca é evidência fraca.
4. Alguns dados de mercado vêm de empresas do setor com interesse comercial.
5. RDAP mostra registro de domínio no instante da consulta; não confirma disponibilidade para compra.
