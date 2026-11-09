# Proposta: hospedagem do CondoOS para o piloto (AWS São Paulo)

Data: 09/11/2026. **Decidida em 09/11/2026 (D106): VPS KVM 4 da Hostinger** (seção 7), já contratada. O Marcio achou as opções da AWS caras. Passo a passo em `docs/deploy.md`, seção 9.

## 1. O que precisa rodar

| Peça | O que é | Recurso necessário |
|---|---|---|
| `web` | Next.js (as telas) | pouca memória |
| `api` | FastAPI | ~1 GB |
| `worker` | fila de jobs, com Docling (leitura de PDF e foto) e o modelo local de busca | **o mais pesado: 3 a 4 GB de memória** |
| Banco | PostgreSQL 16 com pgvector | pequeno no piloto (< 5 GB) |
| Arquivos | S3 (`cond/<condomínio>/…`) | já usamos S3 para a entrada de e-mail |
| HTTPS | certificado para `app.condoos.ia.br` | gratuito (Let's Encrypt) |

O e-mail (SES) e o bucket de entrada já estão em São Paulo (D105). Ficar na mesma região mantém os dados no Brasil e evita custo de tráfego entre regiões.

## 2. Opções

Preços sob demanda em `sa-east-1`, de tabelas públicas de terceiros conferidas em 09/11/2026 (São Paulo custa cerca do dobro dos EUA). **Confirmar na calculadora da AWS antes de criar.**

| | **A. Uma máquina só** | **B. Máquina + banco gerenciado** (recomendada) | C. Tudo gerenciado (contêineres) |
|---|---|---|---|
| Como | EC2 `t4g.large` (2 vCPU, 8 GB) rodando o `docker compose` de hoje, inclusive o PostgreSQL | EC2 `t4g.large` com `web`, `api` e `worker`; PostgreSQL no **RDS** `db.t4g.micro` | ECS Fargate para os 3 serviços, balanceador (ALB) e RDS |
| Custo/mês aproximado | **~US$ 90** (EC2 ~US$ 78 + disco + IP) | **~US$ 120** (EC2 ~US$ 78 + RDS ~US$ 25 + disco, backup e IP) | **US$ 250 a 350** |
| Backup do banco | por nossa conta (dump diário para o S3 e snapshot do disco) | **automático, com volta a qualquer ponto dos últimos 7 dias** (PITR) | automático |
| Se a máquina cair | sai tudo do ar, **inclusive o banco** | as telas param; **o banco e os arquivos ficam intactos** | reinicia sozinho |
| Trabalho para montar | o menor | pequeno | grande |
| Quando faz sentido | demonstração | **piloto com dados reais** | depois do piloto, com vários condomínios |

Por que **B**: o piloto terá dados reais de um condomínio, e o guia de implantação (`docs/deploy.md`) e o checklist da LGPD pedem banco gerenciado com backup e PITR. A diferença para A é de cerca de US$ 30 por mês, e um problema na máquina não arrisca o banco. C fica para quando houver escala.

**Para reduzir depois:** com o piloto validado, um *Savings Plan* de 1 ano costuma baixar EC2 e RDS em 30 a 40%. A primeira fatura pode usar os créditos que a conta ainda tiver.

## 3. Como fica a opção B

```
Internet ──HTTPS──> app.condoos.ia.br (IP fixo da EC2)
                     │  Caddy (Apache-2.0): HTTPS automático, só portas 80 e 443 abertas
                     ├── web (Next.js)
                     ├── api (FastAPI) ──┐
                     └── worker ─────────┼──> RDS PostgreSQL 16 + pgvector (rede privada, sem acesso da internet)
                                         ├──> S3 condoos-documentos (privado, versionado)
                                         ├──> S3 condoos-entrada (e-mail recebido)
                                         └──> SES (envio e recebimento)
```

- **Acesso à máquina:** sem SSH aberto para a internet. Entra-se pelo **Session Manager** do próprio console da AWS.
- **Segredos:** num `.env` só no servidor (ou no Parameter Store da AWS), nunca no Git.
- **Banco:** em rede privada; só a EC2 conversa com ele. Senhas fortes para os papéis `condoos_app` e `condoos_worker` (`docs/deploy.md`, seção 2).
- **Arquivos:** bucket `condoos-documentos` privado e versionado; o navegador baixa por link assinado de 5 minutos.
- **Atualizar o sistema:** no servidor, `git pull` e `docker compose up -d --build`, com o arquivo de produção. Um deploy automático pelo GitHub fica para depois.
- **Saúde:** alarme do CloudWatch para CPU e disco, e um verificador gratuito de `/health` que avisa por e-mail se o site cair.

## 4. O que muda no código (pequeno)

- `docker-compose.prod.yml`: sem PostgreSQL, SeaweedFS e Mailpit locais; com o **Caddy** na frente; `ENVIRONMENT=production`, `SEED_ON_START=false`, cookie seguro, SES para envio e recebimento.
- `Caddyfile` para `app.condoos.ia.br`.
- `docs/deploy.md`: seção da AWS com o passo a passo exato.
- O CI continua igual.

## 5. Antes de colocar dados reais

Isto não é hospedagem, mas o piloto real depende disto (`docs/lgpd.md` e `CLAUDE.md`, item 8):

- autorização do condomínio piloto para tratar os dados;
- contrato de operador com a administradora e com os subprocessadores (AWS, Anthropic), item 22 da LGPD;
- revisão da licença do executável do Claude Code embutido no chat (D54);
- teste de restauração do backup do banco.

## 6. Decisões que preciso

1. **Opção B?** (A sai mais barata; C fica para depois.)
2. **Endereço:** `app.condoos.ia.br`?
3. **Limite de gastos da AWS:** o limite configurado no upgrade precisa comportar uns US$ 120 a 150 por mês. Com "Suspender lançamento de novos recursos" marcado, um limite baixo impede criar a máquina.
4. **Quem executa:** eu não tenho acesso à sua conta AWS. Ou você clica guiado por mim, como fizemos no e-mail, ou roda um script que eu preparo, conferindo cada passo antes.

## 7. Alternativa: VPS da Hostinger em São Paulo (pedida pelo Marcio)

Preços do site da Hostinger em 09/11/2026 (o valor mensal vale para **24 meses pagos adiantado**; depois renova pelo preço cheio). A existência de data center em São Paulo vem de um teste independente (VPSBenchmarks); confirmar no checkout.

| Plano | vCPU | Memória | Disco | Promoção (24 meses) | Renovação |
|---|---|---|---|---|---|
| KVM 2 | 2 | 8 GB | 100 GB NVMe | R$ 42,99/mês (R$ 1.031,76 no total) | R$ 77,99/mês |
| **KVM 4** | 4 | 16 GB | 200 GB NVMe | **R$ 59,99/mês** (R$ 1.439,76 no total) | R$ 149,99/mês |

É a **opção A** (tudo numa máquina, PostgreSQL em contêiner) a uma fração do preço da AWS. O que muda:

- **O e-mail continua na AWS** (SES e o bucket `condoos-entrada`, já pagos por uso, centavos por mês), e os **documentos também vão para um bucket S3 em São Paulo** (`condoos-documentos`, centavos por mês). Assim os arquivos ficam fora da máquina e sobrevivem a ela.
- **Backup do banco por nossa conta:** o backup semanal incluído pela Hostinger não basta para dados reais. Proposta: `pg_dump` diário cifrado enviado ao S3 em São Paulo, com retenção de 30 dias, e teste de restauração antes do piloto.
- **Manutenção do servidor por nossa conta:** atualizações automáticas de segurança do sistema, firewall só com 80 e 443, SSH só por chave (sem senha) e bloqueio de tentativas repetidas.
- **Se a máquina cair, tudo sai do ar** até ela voltar; o banco volta pelo último backup diário (perda de até um dia, contra 5 minutos no RDS).
- **Memória:** o KVM 2 (8 GB) funciona, mas fica no limite durante a leitura de documentos e a atualização do sistema (montar as imagens com o Docling pede memória). O **KVM 4 (16 GB)** dá folga e lê documentos mais rápido; recomendo o KVM 4.

| | Hostinger KVM 4 + S3/SES | AWS opção B |
|---|---|---|
| Custo no piloto | **~R$ 60/mês** + centavos da AWS | ~US$ 120/mês |
| Pagamento | R$ 1.440 adiantado (24 meses) | mensal, por uso |
| Backup do banco | diário, montado por nós (perda de até 1 dia) | automático, PITR (perda de até 5 min) |
| Manutenção do servidor | nossa | do banco, da AWS; da máquina, nossa |
| Dados no Brasil | sim (data center em São Paulo, a confirmar) | sim |

**Recomendação revisada:** para o piloto, **Hostinger KVM 4** com documentos e e-mail na AWS São Paulo e backup diário do banco no S3. Migrar para o RDS (opção B) quando houver mais condomínios ou exigência de recuperação mais rápida; a troca é só apontar o banco para outro endereço e restaurar o backup.
