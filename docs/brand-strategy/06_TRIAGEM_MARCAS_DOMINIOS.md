# 06 — Triagem preliminar de marcas, domínios e linguagem

> **Atualização (rodada 2, 08/11/2026):** triagem de Ciente, Síndico Ciente, Conferi, Sossego, Escudeiro e outros em `11_VARREDURA_COMPLEMENTAR.md`. Os finalistas para o advogado passam a ser **Ciente, Síndico Ciente e Prumea**.

Pesquisa de 08/11/2026. **Isto não é parecer jurídico.** É uma triagem técnica de buscas abertas e bases públicas para decidir o que levar a um advogado de marcas. Ausência de resultado **não** significa disponibilidade; existência de site **não** significa registro de marca.

Legenda: **F** fato verificado na fonte (com data) · **I** inferência · **NV** não verificado. Risco: **baixo aparente / atenção / alto / NV**.

Dados pessoais: domínios registrados por pessoa física aparecem como "pessoa física" (o nome está no RDAP público, mas não é necessário para a decisão).

## 1. O nome atual: "CondoOS"

### 1.1 Usos encontrados por terceiros

| # | Onde | O que a fonte mostra (F, 08/11/2026) | País / setor | Situação | Limite da evidência |
|---|---|---|---|---|---|
| 1 | `condoos.sl20.com.br` | Página "CondoOS": sistema de gestão para vários condomínios (financeiro, portaria, reservas, comunicados, portal do morador, ocorrências). Preços: Básico R$ 89/mês, Profissional R$ 189/mês, Enterprise sob consulta. Rodapé "© 2026 CondoOS". Demo pública. Sem CNPJ, e-mail ou telefone na página | Brasil / gestão condominial para síndicos e administradoras | No ar, com preço publicado | Alta para o uso; nula para titularidade |
| 1b | `sl20.com.br` | "SL20 Sistemas — Soluções Digitais", cerca de 12 produtos no padrão "XxxOS" (BarberOS, NailOS, GymOS…); descreve o CondoOS como "Plataforma completa para síndicos e administradoras". Assinatura de desenvolvedor individual; WhatsApp com DDD 12. Repositório público `csnegrao/condoos` criado em 24/05/2026; primeiro certificado TLS de `condoos.sl20.com.br` em 24/05/2026 (crt.sh) | Brasil | No ar | I: desenvolvedor individual ou microempresa; clientes pagantes NV |
| 2 | `www.condoos.cl` | "El sistema operativo de los edificios modernos en Latinoamérica." Cobrança de gastos comuns, conciliação com extrato, comprovante de cada saída, 4 portais; preço de lançamento 0,5–1,35 UF/mês. Termos e privacidade: "CondoOS Tecnología SpA", RUT informado no site, Santiago; política de privacidade de 10/07/2026. NIC Chile: `condoos.cl` em nome de CONDOOS TECNOLOGÍA SpA desde 15/06/2026 | Chile, ambição declarada para a América Latina / gestão condominial **com foco em prestação de contas** | No ar, em lançamento | Registro de empresa e INAPI NV. **É o uso mais próximo da nossa proposta** |
| 3 | `condoos.sphereinc.com` | "CondoOS, by Sphere": condomínios e HOAs da Flórida; site de documentos exigido por lei e prazos (cita Fla. Stat. 718.111(12)(g), 720.303(4)); módulos Comply (disponível), Operate e Maintain (acesso antecipado); "from $99 a month"; implantação desde US$ 750; termos de 28/05/2026; "© 2026 Sphere Inc. · Sphere Partners, LLC" | EUA (Flórida) / conformidade de condomínios | No ar, vendendo | Empresa de engenharia estabelecida. Termos citam marcas "property of Sphere", o que **não prova registro** |
| 4 | GitHub | 8 repositórios com "condoos" no nome, todos de 2026 (ex.: `stefanogebara/condoos`, "AI-powered condominium OS", 23/04/2026) | Vários | Projetos pessoais | Baixa relevância comercial; mostra saturação do nome |
| 5 | App Store, Google Play, redes | Nenhum app "CondoOS" encontrado | — | — | Perfis sociais NV diretamente |

**Nosso uso:** o primeiro commit no histórico atual do repositório `marciocgil/condoos` é de 05/11/2026 (F, `git log`); a data de criação do repositório no GitHub foi informada como 16/09/2026 (NV). A Especificação Mestra é de 06/11/2026. Não há site, piloto ou venda com o nome. **Todos os três usos de terceiros são anteriores ao nosso primeiro uso documentado (I, pelas datas acima).**

### 1.2 Bases oficiais

| Base | Consulta | Resultado |
|---|---|---|
| INPI (busca.inpi.gov.br/pePI) | condoos, "condo os", condos | **NV**: conexão recusada/HTTP 503 a partir desta rede (bloqueio aparente de acesso automatizado ou de fora do Brasil). Duas tentativas independentes |
| USPTO (API do tmsearch) | condoos, condo-os, "condo os", hoaos, condoai, condosys | **F: nenhum pedido ou registro** para "CONDOOS" (validado com consulta de controle que retornou registros reais). Pedidos muito recentes podem não aparecer |
| WIPO Global Brand Database | "condoos" | **NV**: exige captcha e JavaScript |
| TMview (EUIPO) | "condoos" | **NV**: requisição rejeitada |
| INAPI (Chile) | — | **NV**: conexão recusada pelo proxy |

### 1.3 Domínios "CondoOS" (RDAP oficial, 08/11/2026)

| Domínio | Resultado |
|---|---|
| `condoos.com.br` | **Registrado** por pessoa física em 15/02/2026 (RDAP Registro.br); DNS padrão do Registro.br, sem site |
| `condoos.com` | **Registrado** em 05/05/2026 via DropCatch; redireciona para revendedor (HugeDomains), aparentemente **à venda** (I) |
| `condoos.app` | Registrado em 09/05/2026 (GoDaddy, Cloudflare); conteúdo atrás de verificação, desconhecido |
| `condo-os.com` | Registrado em 07/09/2026; conteúdo desconhecido |
| `condoos.cl` | CONDOOS TECNOLOGÍA SpA, desde 15/06/2026 |
| `condoos.ai`, `condoos.io`, `condoos.net`, `condoos.co` | RDAP 404 / NXDOMAIN (sem registro no momento da consulta; disponibilidade para compra **NV**) |

### 1.4 Avaliação preliminar do nome "CondoOS"

| Mercado | Risco | Razão |
|---|---|---|
| **Brasil** | **Alto** | Uso idêntico, mesmo público e mesmo tipo de serviço, desde maio/2026 (SL20). O Brasil adota o sistema atributivo (registro), mas o usuário anterior de boa-fé tem direito de precedência ao registro (Lei 9.279/96, art. 129, §1º; aplicação ao caso **a confirmar por advogado**). `.com.br` com terceiro. "Condo" e "OS" são elementos fracos/descritivos, o que reduz a exclusividade para qualquer um, inclusive para nós (art. 124, VI, a confirmar). Situação no INPI: **NV** |
| **EUA** | **Alto** | Sphere vende "CondoOS" no mesmo setor desde maio/2026; sem pedido no USPTO, mas o uso comercial gera direitos de common law (I, confirmar). `.com` com revendedor |
| **Chile / América Latina** | **Alto** | Empresa com o nome como razão social e produto, mesma proposta de prestação de contas, ambição latino-americana declarada |

**Conclusão da triagem (I):** continuar com "CondoOS" como marca comercial expõe o projeto a conflito com usuário anterior no Brasil, impede um domínio principal coerente e dificulta diferenciação em busca. Mesmo que o registro fosse possível, a marca seria fraca. **Recomenda-se não investir no nome** antes de parecer jurídico — e, salvo parecer em contrário, substituí-lo antes do primeiro piloto.

## 2. Triagem dos semifinalistas e finalistas

Fontes por nome: busca web (pt/en/es), App Store (API de busca, BR e US), USPTO (API do tmsearch), RDAP `.com.br` (Registro.br) e `.com` (Verisign). **INPI: NV para todos.**

| Nome | Usos encontrados (F, 08/11/2026) | USPTO | App Store | Risco BR | Risco EUA |
|---|---|---|---|---|---|
| **Arrimo** | Nenhum produto de software, finanças ou imobiliário encontrado na web | 0 resultados | Nenhum app homônimo | **Atenção** (INPI NV; `.com.br` com pessoa física desde 2011) | Baixo aparente |
| **Ciente** | Nenhum software homônimo; "CIENT Contabilidade" (app de finanças, 2026, grafia próxima); "Ciente Hair Salon" (app de salão, 2016) | 0 | Ver ao lado | **Atenção** (palavra comum; grafia próxima no setor contábil; INPI NV) | Baixo aparente |
| **Prumea** | Nenhum uso encontrado na web | 0 | Nenhum | **Atenção** (`prumea.com.br` registrado por pessoa física em 26/10/2026, uso desconhecido; proximidade com Prumo/Aprumo) | Baixo aparente |
| Aprumo | **useaprumo.com** (hub pessoal de finanças/treinos, PT/EN, R$; domínio de 01/10/2026); apps "Aprumo" (finanças, 24/09/2026) e "Aprumo Financeiro" (20/09/2026) | 0 | 2 apps de finanças | **Alto** | Atenção |
| Prumo | Prumo Logística (grande grupo); "Prumo Projetos e Obras" dona de `prumo.com.br` desde 2004 | 0 | — | **Alto** | NV |
| Esteio | Esteio Engenharia e Aerolevantamentos (desde 1997); app "Esteio Gestão" (agro, 2025); nome de município | 2 | 1 app | **Alto** | Baixo aparente |
| Vertio | Vertio (infraestrutura técnica e marketing, BR, `vertio.com.br` ativo); app "Vertios Sync" (BR) | 1 (classe 11, não relacionado) | 1 app próximo | Atenção/alto | Atenção |
| Síndico em Dia | `sindicoemdia.com.br` registrado por pessoa física em 23/10/2026 | — | — | Atenção (descritivo) | n/a |
| Cotejo | Palavra comum em PT/ES para comparar documentos | 0 | — | Atenção (descritivo) | n/a |
| Lastro *(eliminado)* | **Lastro: proptech de SP, assistente de IA "Lais", Série A de R$ 85 mi (Prosus)** | 2 | — | **Alto** | — |
| Zelo *(eliminado)* | **Zelo Facilities** (app de condomínio), **Zello Administradora** | 29 | 2 apps de condomínio | **Alto** | — |
| Pilastra *(eliminado)* | Pilastra (IA para educação, `pilastra.com.br` desde 20/07/2026); app "Pilastra — Construction Field Management" | Pedido classe 42 de 19/08/2026 | — | **Alto** | **Alto** |
| Tino *(eliminado)* | App "Tino – Finanças com IA" (BR, 28/08/2026) | 106 | Sim | **Alto** | — |
| Atesta *(eliminado)* | Atesta CFM (plataforma oficial de atestados) | 0 | — | **Alto** | — |
| Condara *(eliminado)* | App "Condora – Gestão de Condomínios" (BR, 2026) | 0 | Sim | **Alto** | — |

## 3. Tabela de domínios dos finalistas (RDAP, 08/11/2026)

"Sem registro no RDAP" = o registro não tinha o domínio no momento da consulta. **Não confirma que esteja à venda** (pode haver reserva, nome premium ou bloqueio) e muda a qualquer momento. **Nenhum domínio foi comprado.**

| Domínio | Resultado |
|---|---|
| `arrimo.com.br` | Registrado (pessoa física, 06/01/2011); sem site respondendo |
| `arrimo.com` | Registrado (2016); redireciona para revendedor (I: à venda) |
| `arrimoapp.com.br` · `usearrimo.com.br` · `arrimocondominios.com.br` | Sem registro no RDAP |
| `arrimoapp.com` · `usearrimo.com` · `arrimocondominios.com` | Sem registro no RDAP |
| `ciente.com.br` | Registrado (pessoa física, 21/01/2024); sem site respondendo |
| `ciente.com` | Registrado (2000) |
| `cienteapp.com.br` · `usaciente.com.br` · `fiqueciente.com.br` | Sem registro no RDAP |
| `cienteapp.com` · `usaciente.com` · `fiqueciente.com` | Sem registro no RDAP |
| `prumea.com.br` | Registrado (pessoa física, 26/10/2026) |
| `prumea.com` | Registrado (2023); redireciona para revendedor |
| `useprumea.com.br` · `useprumea.com` · `prumeaapp.com` | Sem registro no RDAP |

**Leitura (I):** nenhum finalista tem o `.com.br` exato livre. Para Arrimo, o caminho viável é `arrimo` + sufixo (`usearrimo.com.br`, `arrimoapp.com.br`) no curto prazo e, se o nome for aprovado, avaliar aquisição de `arrimo.com.br` por intermediário, **sem contato antes da decisão**.

## 4. Triagem linguística

| Nome | PT-BR | Espanhol | Inglês (EUA) | Áudio / WhatsApp |
|---|---|---|---|---|
| CondoOS | "côn-do-ô-ésse" ou "con-dôs": pronúncia instável; "OS" no setor também é **ordem de serviço** | "sistema operativo" (uso chileno) | "condo O-S" | Alto risco de grafia ("Condos", "Condo OS", "Kondos") |
| Arrimo | Muro de arrimo (construção); arrimo de família (sustento). Sem conotação negativa encontrada; verbo "arrimar-se" (apoiar-se) neutro | "arrimo" = apoio, amparo (positivo) | Sem significado; "ah-REE-moh" | Risco de "Arimo" (um r): testar |
| Ciente | Ciente = informado; registro formal | Não existe ("consciente") | Sem significado; pronúncia difícil | Confusão com "cliente": testar |
| Prumea | Sem significado; remete a "prumo" | Sem significado | "proo-MAY-ah" | Risco de "Prumeia", "Prumeya": testar |

Nenhuma conotação ofensiva encontrada nas três línguas para os finalistas (busca aberta; validação com falantes nativos **NV**).

## 5. Classes de Nice possivelmente pertinentes (a definir com especialista)

Referência: classificação de marcas do INPI (`https://www.gov.br/inpi/pt-br/servicos/marcas/classificacao-marcas`). **Não presumir que uma classe basta.**

| Classe | Escopo provável | Por quê |
|---|---|---|
| 9 | Software e aplicativo baixável | App móvel |
| 42 | SaaS, software como serviço, plataforma online | Produto principal |
| 35 | Gestão de negócios, administração, **auditoria de negócios**, processamento de dados | Conferência de despesas e relatórios (verificar se "auditoria" exige outra redação) |
| 36 | Assuntos financeiros e **imobiliários** (inclui administração de imóveis/condomínios) | Proximidade com administradoras; expansão para serviços |
| 45 | Serviços jurídicos | **Evitar** reivindicar: assessoria jurídica é privativa da advocacia (ver `01`, §4.3) |

## 6. Checklist para o advogado de marcas (*legal clearance*)

**Materiais a entregar:** este pacote (`00`–`10`); descrição do produto e dos serviços (incluindo revisão humana interna e economia por êxito); lista de finalistas com grafia e pronúncia; países de interesse (Brasil agora; EUA e América Latina depois); datas do nosso primeiro uso (`git log`, especificação de 06/11/2026).

**Perguntas:**
1. Há pedido ou registro no INPI para CONDOOS, CONDO OS ou similares nas classes 9, 35, 36, 42? Titular e situação?
2. O uso da SL20 desde maio/2026 dá direito de precedência (art. 129, §1º) contra eventual pedido nosso? E o uso chileno, se houver pedido via Madri?
3. "CondoOS" seria registrável ou cairia no art. 124, VI (sinal genérico/descritivo)? Só como marca mista?
4. Busca de anterioridade completa (fonética e gráfica) no INPI para **Arrimo, Ciente e Prumea**, nas classes acima, incluindo radicais (ARRIM*, CIENT*, PRUM*).
5. "Ciente" é registrável como nominativa para software, ou só mista? "CIENT" (contabilidade) é impedimento?
6. "Prumea" tem colidência com PRUMO/APRUMO registrados?
7. Estratégia de depósito: nominativa + mista? Quais classes primeiro? Custos e prazos atuais do INPI.
8. Para EUA: vale pedido baseado em intenção de uso (1(b)) ou via Madri após o depósito brasileiro?
9. Riscos de usar "assessor", "auditoria" e "conferência" na comunicação (OAB, CRC)?
10. Domínio de terceiro (`arrimo.com.br`, pessoa física): como abordar a aquisição sem expor o projeto?

## 7. Próximos testes desta frente

1. Busca no INPI a partir de rede brasileira (manual, `https://busca.inpi.gov.br/pePI/`), registrando data e telas, **antes** do advogado, para triagem rápida.
2. WIPO Global Brand Database e TMview manualmente (exigem navegador).
3. Busca de CNPJ por razão social/nome fantasia (Receita Federal ou serviço de consulta) para os três finalistas.
4. Instagram, LinkedIn, TikTok e YouTube: handles exatos dos finalistas.
5. Reconsultar RDAP dos domínios variantes na véspera da decisão (domínios mudam rápido; vários do estudo foram registrados em out/2026).
