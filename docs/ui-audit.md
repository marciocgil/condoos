# Auditoria da interface × Design System v1.0

Data: 05/11/2026. Referência: `CondoOS_Design_System_v1.0.md` (fornecido pelo Marcio). Escopo: adaptar a interface existente ao design system **sem mudar o escopo funcional** e concluir o Marco 4 (achados, decisões, telas).

## 1. O que existe hoje (verificado no código)

- **Framework:** Next.js 15 (App Router), React 19, TypeScript strict, Tailwind CSS 4 (`@theme` em `app/globals.css`). Sem bibliotecas de componentes, ícones ou gráficos.
- **Dados:** componentes de servidor chamam a API por `lib/api.ts` (`apiGet`, repassando o cookie de sessão). Componentes de cliente usam `fetch('/api/...')` (proxy do Next). Formatação em `lib/format.ts`; rótulos em `lib/labels.ts`; tipos em `lib/types.ts`.
- **Áreas:**
  - `(sindico)/condominio/[id]/*`: mobile-first, cabeçalho verde, abas inferiores (Resumo · Achados · Contratos · Histórico), botão flutuante "Pergunte ao CondoOS" desabilitado. Telas: Resumo (com dados), Contratos (com dados), Enviar, Achados e Histórico (placeholders).
  - `(admin)/admin/*`: sidebar verde-escura fixa (sem header). Telas: Carteira (KPIs, tabela, fila resumida), Fila de exceções, correção de extração (documento lado a lado), casamento ambíguo, Enviar. Fornecedores, Contratos, Configurações e Pergunte à IA são placeholders.
  - Login e verificação do link mágico: cartão claro centralizado.
- **Componentes compartilhados:** `AdminNav`, `BottomTabs`, `QueueList`, `ReviewForm`, `ResolveForm`, `UploadForm`, `AdminUpload`, `MonthSelect`, `LogoutButton`, `AskButton`, `Placeholder`.
- **Padrão visual:** tema claro (`#f7f8f8`), paleta própria `brand-*` (verde) e `sev-*`. Classes Tailwind repetidas em cada tela, sem componente de botão, cartão, badge ou tabela.

## 2. Matriz

| Área ou componente | Situação atual | Adaptação necessária | Prioridade | Risco |
| --- | --- | --- | --- | --- |
| Tokens e tema | Tema claro, paleta `brand-*` própria, cores fixas nas telas | Tokens do DS (§2.1) em `@theme`, tema escuro padrão, Inter, números tabulares, raios e espaçamentos do DS | Alta | Baixo: só estilos, mas toca todas as telas |
| Layout (admin) | Sidebar fixa de 256 px, sem header, sem modo recolhido | App shell do DS: sidebar de 232/64 px com logo, seletor de condomínio e navegação; header de 64 px com breadcrumb, título e usuário; área de conteúdo com padding de 24–32 px | Alta | Médio: rotas e testes E2E dependem dos rótulos do menu |
| Layout (síndico) | Coluna de 448 px, cabeçalho verde, abas inferiores | Mesmo tema e tokens; **mantém as abas inferiores** (fluxo exigido pelo prompt original) e o seletor de mês; ações sem depender de hover | Alta | Baixo |
| Navegação | Itens do prompt original (Carteira, Fila, Fornecedores, Contratos, Configurações, Pergunte à IA) | Manter os itens e rótulos (o escopo do Marco 4 é o do prompt); aplicar estilo do DS, contador da fila como badge, estado ativo em accent | Alta | Baixo |
| Dashboard / Resumo | Resumo com cartão de destaque, chips e top 3 | KPI Cards do DS; chips de severidade como Status Badge com ícone e texto; lista "Principais achados" como AI Insight Card resumido | Alta | Baixo |
| Cards | Classes soltas (`rounded-xl bg-white shadow-sm`) | Componentes `Card`, `KpiCard`, `InsightCard` (raio de 14 px, borda sutil, sem sombra forte) | Alta | Baixo |
| Badges | Pílulas soltas ("Revisar", "Em dia", severidade com ponto) | `StatusBadge` e `SeverityBadge` com ícone e texto, nunca só cor | Alta | Baixo |
| Gráficos | Não existem | Fora do escopo funcional do Marco 4; nenhum gráfico novo, para não inventar indicadores | Baixa | — |
| Tabelas | Tabela HTML da Carteira | `DataTable` simples (cabeçalhos semânticos, números tabulares, linha clicável, estado vazio), usada em Carteira, Fornecedores e Contratos | Média | Baixo |
| Filtros | Não existem (só seletor de mês) | `FilterChips` na lista de achados (severidade, status, categoria), removíveis e visíveis | Média | Baixo |
| Formulários | Inputs e selects soltos (correção, upload, login, resolução) | `Input`, `Select`, `Textarea`, `Button` (altura de 40 px, raio de 8 px, foco visível); estados de erro por campo | Média | Médio: os testes E2E usam rótulos, que devem ser preservados |
| Painel lateral / modais | Não existem | `SidePanel` com `<dialog>` nativo (foco controlado, Esc fecha) para o detalhe do achado na fila do gerente; o síndico usa página própria (mobile, tela cheia, como o DS prevê) | Média | Baixo |
| Timeline | Não existe | `Timeline` para o histórico de decisões do achado e a trilha do condomínio (autor humano ou IA, data e hora, ação, comentário) | Alta (Marco 4) | Baixo |
| Estados | Placeholder genérico; erros mínimos | `EmptyState`, mensagens de erro e de falta de permissão, skeleton nas listas assíncronas | Média | Baixo |
| Login / verificação | Cartão claro | Mesmo fluxo com o tema escuro | Baixa | Baixo |
| Telas placeholder (Achados, Histórico, Fornecedores, Contratos, Configurações) | Placeholders | Implementar com os componentes do DS: escopo do Marco 4 (seções 8 e 9 do prompt) | Alta | Médio |
| Pergunte à IA | Botão desabilitado | Fica para o Marco 5; aparece no estilo do DS, desabilitado e com "disponível em breve" | Baixa | — |

## 3. Conflitos e como foram resolvidos

1. **Tema claro dos mockups × tema escuro do DS.** O DS proíbe trocar a identidade escura por um "dashboard branco" (§12), e o Marcio pediu para seguir o DS nas telas. Tema escuro nas duas áreas; a estrutura dos mockups (o que aparece e em que ordem) é mantida.
2. **Drawer no mobile (DS §3.2) × abas inferiores (prompt §8).** O prompt de refatoração manda preservar fluxos e navegação. O síndico mantém as abas inferiores, com o estilo do DS. A administradora (desktop-first) ganha o app shell completo.
3. **Vocabulário do Optimize (oportunidades, economia, kanban) × domínio atual (achados de auditoria).** O DS descreve a direção visual, não o escopo. Os componentes são reaproveitados com o vocabulário do produto atual: um "achado" usa o AI Insight Card e o Side Detail Panel. Nenhuma funcionalidade nova de economia ou kanban.
4. **Verde-lima com moderação.** Usado só em ação primária, item ativo do menu e foco. Severidade usa as cores semânticas (danger, warning, info) sempre com texto e ícone.

## 4. Plano incremental (executado no Marco 4)

1. **Fundações:** tokens do DS em `app/globals.css` (cores, raios, tipografia Inter via `next/font`, números tabulares), `color-scheme: dark`, foco visível, `prefers-reduced-motion`.
2. **Componentes compartilhados** em `web/components/ui/` (genéricos, sem regra de negócio): `Button`, `Card`, `KpiCard`, `Badge`, `Input`/`Select`/`Textarea`/`Field`, `DataTable`, `FilterChips`, `SidePanel`, `Timeline`, `EmptyState`. Componentes do domínio em `web/components/condoos/`: `SeverityBadge`, `FindingStatusBadge`, `InsightCard`, `EvidenceList`, `DecisionBar`.
3. **Estrutura global:** app shell da administradora (sidebar 232/64 + header 64); shell mobile do síndico. Rotas, rótulos e testes preservados.
4. **Telas:** reaplicar os componentes nas telas existentes; implementar as do Marco 4 (detalhe e lista de achados, decisões, histórico/trilha, validação de graves, fornecedores, contratos e configurações da administradora).
5. **Validação:** typecheck, lint, Playwright (fluxos antigos e os 4 novos do Marco 4), capturas em 390 px e 1280 px, contraste dos tokens (WCAG AA) checado por script.

Ícones: `lucide-react` (licença ISC, permissiva). Sem Radix, shadcn ou Recharts: o painel lateral usa `<dialog>` nativo, e o Marco 4 não tem gráficos.

## 5. Etapa A — componentes a modificar, riscos e escopo

**Componentes existentes adaptados (mesmo comportamento, novo visual):** `AdminNav` (vira a sidebar do app shell), `BottomTabs`, `QueueList`, `ReviewForm`, `ResolveForm`, `UploadForm`, `AdminUpload`, `MonthSelect`, `LogoutButton`, `AskButton`, `Placeholder` (substituído por `EmptyState`, porque o placeholder só dizia "chega no Marco N" e o DS pede estado vazio com próximo passo).

**Componentes novos (justificativa: não existiam e os padrões estavam duplicados em cada tela):** `ui/Button`, `ui/Card`, `ui/KpiCard`, `ui/Badge`, `ui/Field` (+ `Input`, `Select`, `Textarea`), `ui/DataTable`, `ui/FilterChips`, `ui/SidePanel`, `ui/Timeline`, `ui/EmptyState`, `layout/AppShell` (sidebar + header), `layout/MobileShell`; domínio: `condoos/SeverityBadge`, `condoos/FindingStatusBadge`, `condoos/InsightCard`, `condoos/EvidenceList`, `condoos/DecisionBar`, `condoos/DecisionTimeline`.

**Dependência nova:** `lucide-react` (ISC), a iconografia indicada no DS (§10), para que status nunca dependa só de cor. Fonte Inter via `next/font` (já no Next, sem dependência).

**Riscos:**
- Os testes E2E localizam elementos por rótulo e papel. Rótulos de botões, campos e links são preservados, e a suíte roda ao fim de cada fase.
- Contraste: os tokens do DS são verificados por script (WCAG AA); se algum par falhar, o ajuste é registrado.
- O tema escuro substitui o claro dos mockups (conflito 1); a estrutura dos mockups é mantida.

**Fora do escopo (o DS descreve, mas o produto ainda não tem e o prompt não autoriza):** busca global e notificações no header; Central de Oportunidades e kanban; KPIs de economia potencial e realizada; gráficos; módulo de Atividades; seletor de módulo. O header terá breadcrumb, título e menu do usuário.

**Backend:** a refatoração visual não muda nenhum contrato de API existente. Os endpoints novos são do escopo funcional do Marco 4 (decisões, detalhe e lista de achados, trilha, carteira consolidada, configurações), autorizado pelo Marcio.

## 6. Etapa C — resultado

**Componentes criados** (`web/components/ui/`): `Button`/`ButtonLink`, `Card`/`CardTitle`, `KpiCard`, `Badge`, `Field` (+ `controlClass`, `textareaClass`), `DataTable`, `FilterChips`, `SidePanel` (`<dialog>` nativo), `Timeline`, `EmptyState`. Em `layout/`: `Logo`, `AdminHeader`, `PageHeader`. Em `condoos/`: `SeverityBadge`, `FindingStatusBadge`, `InsightCard`, `EvidenceList`, `DecisionBar`, `CommentForm`, `FindingDetailView`, `SupplierTable`, `SettingsForm`.

**Componentes adaptados:** `AdminNav` (sidebar 232/64 px), `BottomTabs`, `AskButton`, `LogoutButton`, `MonthSelect`, `QueueList` (três tipos de item: extração, casamento e achado grave), `UploadForm`, `AdminUpload`, `ReviewForm`, `ResolveForm`. Removido: `Placeholder` (substituído por `EmptyState`).

**Telas atualizadas:**
- Login, verificação, 404 e erro.
- Síndico: Resumo, Achados (lista com filtros), Detalhe do achado (com decisões), Contratos, Histórico (trilha) e Enviar.
- Administradora: Carteira, Fila de exceções, Validar achado, Corrigir extração, Resolver casamento, Fornecedores (com painel lateral), Contratos, Configurações, Enviar e Pergunte à IA.

**Verificações:**
- `tsc` strict e `eslint`/`prettier` limpos.
- 179 testes do backend.
- Playwright: login, link inválido, envio + correção de extração, síndico confirma, síndico contesta com comentário, gerente valida grave.
- Contraste dos tokens conferido por script (D47).
- Capturas em 390 px e 1280 px conferidas.

**Limitações:**
- Os elementos fixos do celular (abas e "Pergunte ao CondoOS") aparecem repetidos em capturas de página inteira; no uso real ficam presos ao rodapé.
- Sem verificação automática de acessibilidade (axe); a revisão foi manual (rótulos, foco visível, status com texto e ícone, cabeçalhos de tabela).
- O "Pergunte ao CondoOS" continua desabilitado até o Marco 5.
