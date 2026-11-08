# 04 — Arquitetura de marca

Pesquisa de 08/11/2026. Depende de `03` (tese) e `06` (triagem do nome CondoOS). Legenda: **F** fato · **I** inferência · **H** hipótese.

## 1. Termos usados neste pacote

| Termo | Definição | Exemplo hoje |
|---|---|---|
| **Marca comercial** | Nome que o cliente vê, compra e recomenda; objeto de registro no INPI | "CondoOS" no título da web (`web/app/layout.tsx`) e no logo (`web/components/layout/Logo.tsx`) |
| **Nome de produto/módulo** | Nome de uma oferta dentro da marca | "Optimize", "Advisor" (só em documentos internos; não aparecem na interface) |
| **Nome interno / codename** | Nome do projeto para a equipe | "CondoOS" no repositório, na especificação e no plano |
| **Identificadores técnicos** | Strings no código, banco, infraestrutura | `condoos_app`, `condoos_reviewer`, `condoos-web`, `condoos.example.com`, `condoos_session`, repositório `marciocgil/condoos` (151 arquivos versionados citam "condoos", contagem de 08/11/2026) |

Separar os quatro é o que torna barata uma troca de marca comercial: **a marca pode mudar sem tocar em identificador técnico** (ver §5).

## 2. Ponto de partida (F)

- O produto **não foi lançado**: não há piloto real (gate G0 aberto), site público, cliente pagante, domínio do projeto ou registro de marca conhecido. O valor de marca acumulado de "CondoOS" com clientes é, portanto, **zero** (I). O custo de trocar agora é o menor que jamais será.
- "CondoOS" é usado por terceiros no mesmo setor em pelo menos três países, e os domínios `condoos.com.br` e `condoos.com` pertencem a terceiros (detalhe em `06`).
- Os módulos Advisor, Optimize, Operate, Launch e Procurement são nomes funcionais em inglês, sem uso na interface.

## 3. Comparação das arquiteturas

Notas 1–5 (I). "Risco jurídico" considera a triagem de `06`.

| Opção | Descrição | Clareza para o síndico | Risco jurídico/digital | Custo e tempo | Expansão (Operate, compras, outros ativos) | Veredito |
|---|---|---|---|---|---|---|
| **A. Manter CondoOS** (empresa e produto) | Nada muda | 2 — "OS" é jargão; soa ERP | **1 — alto**: homônimos no setor (BR, CL, EUA), sem domínio `.com.br`/`.com` | 5 — zero agora; caro depois | 3 — "Condo" limita a condomínio | **Não recomendado** |
| **B. Nova marca corporativa + CondoOS como produto** | Empresa X, produto "CondoOS" | 2 | **1 — alto**: o risco está no produto, que é o que aparece | 3 | 3 | **Não recomendado**: mantém o problema onde ele dói |
| **C. Nova marca única** (empresa = plataforma = serviço), módulos descritivos | "X", com "Conferência", "Economia", "Assuntos", "Hoje" | 4 — um nome, funções em português | Depende do nome (ver `06`) | 3 — esforço único, antes do lançamento | 5 — o nome não amarra a função | **Recomendado** |
| **D. Guarda-chuva + soluções com nomes próprios** | "X Conferência", "X Compras", com submarcas comerciais | 3 | Multiplica buscas e registros | 2 — mais nomes para registrar e explicar | 5 | Só quando houver ofertas vendidas separadamente |
| **E. Endossada/dupla de transição** ("X, antes CondoOS") | Usar as duas | 2 | Herda o risco do CondoOS | 3 | 4 | **Desnecessária**: não há base de clientes para transicionar |

## 4. Recomendação: **opção C — marca única nova, com funções descritivas**

1. **Uma marca** para empresa, aplicativo, site, relatórios, proposta e WhatsApp. O síndico lembra um nome só (I: compra de baixa frequência e baixo envolvimento técnico favorece marca única).
2. **Módulos com nomes descritivos em português**, não marcas:

| Nome interno (fica no código e nos docs) | Nome para o cliente | Status no produto | Visível hoje? |
|---|---|---|---|
| Optimize (conferência) | **Conferência das contas** / "Conferência do mês" | Existe | Sim |
| Optimize (oportunidades) | **Economia** ("oportunidades de economia", "economia medida") | Existe (com revisão interna) | Sim |
| Advisor (briefing, chat) | **Hoje** (já é o nome da aba, D82) e **Pergunte** / "Perguntar ao [marca]" | Existe | Sim |
| Advisor (assuntos) | **Assuntos** (já usado na interface, D80) | Existe | Sim |
| Launch | **Implantação** | Parcial | Só em proposta |
| Operate | **Acompanhamento** ("manutenção e fornecedores") | Não existe | Não |
| Procurement | **Compras** / "Cotações" | Não existe | Não |
| Core | — (nunca visível) | Existe | Não |

3. **"CondoOS" vira codename interno** até a migração técnica aprovada, e depois pode continuar só como nome de repositório. **Não usar CondoOS em nenhum material externo** (site, proposta, deck de piloto, perfil social) a partir da decisão.
4. **Planos comerciais** (quando houver) com nomes de nível, não de produto: "Essencial", "Completo", "Profissional (vários condomínios)". Evita multiplicar marcas.
5. **Submarca própria (opção D) só quando** uma oferta for vendida separadamente a um comprador diferente (ex.: compras para administradoras). Até lá, descritivo.

### Deve existir uma marca para o Optimize?

**Não** (I). Ele é a porta de entrada e a prova da tese T5; dar outro nome a ele dividiria a marca no momento em que ela precisa ser lembrada. "Optimize" em inglês também colide com a linguagem do síndico (que fala "conferir", "economizar", "prestar contas"). Fica como nome interno.

### E Advisor, Operate, Launch?

Ficam internos. Na interface já existem nomes em português ("Hoje", "Assuntos"); manter. "Assessor" pode descrever o papel da marca em texto ("seu assistente de gestão"), não nomear módulo.

## 5. Impacto técnico (para planejar; **não executar sem aprovação**)

Separar camadas permite trocar a marca comercial **sem** renomear identificadores técnicos no primeiro momento.

| Camada | Exemplos atuais | Precisa mudar no lançamento? | Observação |
|---|---|---|---|
| Interface visível | título `CondoOS` em `web/app/layout.tsx`, texto do `Logo.tsx`, rodapé de relatórios PDF/XLSX, e-mails do link mágico, textos de ajuda, prompts que se apresentam ao usuário | **Sim** | Centralizar o nome numa constante (`BRAND_NAME`) antes de trocar |
| Domínio e e-mail | `condoos.example.com` (seed), `ingest.condoos.local` | Sim, quando houver domínio real | Seed fictício pode esperar |
| Papéis e identificadores | `condoos_admin`, `condoos_reviewer`, `condoos_app`, `condoos_worker` | **Não** | Invisíveis ao cliente; renomear exige migração; manter |
| Repositório e pacotes | `marciocgil/condoos`, `condoos-web`, `condoos-api`, buckets | Não | Opcional depois |
| Documentos de planejamento | Especificação Mestra, Plano Diretor, este pacote | Não | São histórico; criar nota de nomenclatura |
| Jurídico/comercial | Termos de uso, política de privacidade, contrato de piloto, LGPD (`docs/lgpd.md`) | **Sim** | Revisar antes de qualquer piloto com o nome novo |

Plano detalhado e sequência: `09_ROADMAP_30_60_90.md`, §4.

## 6. O que não fazer

- Não registrar domínio nem marca "CondoOS" para "defender" o nome: aumenta custo afundado num nome com colisão.
- Não criar nomes comerciais para cada módulo agora.
- Não usar "OS", "IA" ou "AI" no nome comercial: datam rápido e posicionam como software genérico.
- Não renomear identificadores técnicos junto com a marca: risco operacional sem benefício para o cliente.
- Não lançar site ou proposta com o nome novo antes da triagem jurídica profissional (`06`, §6).
