"""The 25 controls of the monthly "farol" (D122): stable ids, pillar, agents, required sources,
acceptance criteria, rule version, the cycle that implements them and what they depend on.

A control not implemented yet is always "Não avaliado" with the cycle that will bring it:
never green by absence. The ids never change between months.
"""

from dataclasses import dataclass

# Inputs a control reads; a change in one of them can reopen the control (dependency graph).
DOCUMENTOS = "documentos"
EXTRATO = "extrato"
SALDOS = "saldos"
DESPESAS = "despesas"
PAGAMENTOS = "pagamentos"
RECEITAS = "receitas"
CONTRATOS = "contratos"
TRIBUTOS = "tributos"
FUNDOS = "fundos"
ORCAMENTO = "orcamento"
UNIDADES = "unidades"
OBRIGACOES = "obrigacoes"
APROVACOES = "aprovacoes"


# Controls of cycles up to this one are evaluated; later ones are "Não avaliado".
CURRENT_CYCLE = 2


@dataclass(frozen=True)
class ControlDef:
    id: str
    pillar: str
    name: str
    agents: tuple[str, ...]
    sources: tuple[str, ...]  # what must be received for the control to be tested
    criteria: tuple[str, ...]  # acceptance criteria of "Validado"
    inputs: tuple[str, ...]
    cycle: int
    rule_version: str
    parameters: dict[str, str] | None = None

    @property
    def implemented(self) -> bool:
        return self.cycle <= CURRENT_CYCLE


PILLARS = {
    "DOC": "Documental",
    "BAN": "Bancário",
    "REC": "Arrecadação",
    "DES": "Despesas e fiscal",
    "CON": "Contratos",
    "GOV": "Governança",
}

CONTROLS: list[ControlDef] = [
    ControlDef(
        "DOC-01",
        "DOC",
        "Integridade do acervo do mês",
        ("A1", "A2", "A9"),
        ("documentos do mês", "extrato de cada conta conhecida"),
        (
            "Há documentos recebidos para a competência.",
            "Cada conta conhecida tem extrato que cobre o mês.",
            "Todos os documentos foram lidos (nenhum ilegível ou aguardando correção).",
            "Cópias e versões ficam registradas, nunca descartadas.",
        ),
        (DOCUMENTOS, EXTRATO),
        1,
        "1.0",
    ),
    ControlDef(
        "DOC-02",
        "DOC",
        "Comprovação de lançamentos",
        ("A1", "A2", "A9"),
        ("despesas do mês", "documento fiscal, recibo ou guia de cada despesa"),
        (
            "Toda despesa do mês tem documento fiscal, recibo ou guia.",
            "Ter documento não prova pagamento válido (isso é DES-01).",
        ),
        (DESPESAS, DOCUMENTOS),
        1,
        "1.0",
    ),
    ControlDef(
        "DOC-03",
        "DOC",
        "Aprovação formal das contas",
        ("A7", "A9"),
        ("termo, ata ou decisão de aprovação",),
        ("Aprovação com signatários, data, abrangência e poderes.",),
        (DOCUMENTOS, APROVACOES),
        3,
        "—",
    ),
    ControlDef(
        "BAN-01",
        "BAN",
        "Saldo bancário recalculado",
        ("A4", "A8"),
        ("extrato com saldo inicial e final de cada conta", "saldo contábil do demonstrativo"),
        (
            "Saldo inicial + créditos − débitos = saldo final, ao centavo, em cada conta.",
            "Todas as contas conhecidas têm extrato com saldos declarados.",
            "Saldo do extrato confere com o saldo contábil do demonstrativo.",
        ),
        (EXTRATO, SALDOS),
        1,
        "1.0",
        {"tolerancia": "R$ 0,00 (exatidão centesimal)"},
    ),
    ControlDef(
        "BAN-02",
        "BAN",
        "Continuidade entre meses",
        ("A4", "A8"),
        ("extrato do mês anterior e do mês, por conta",),
        (
            "O saldo de abertura do mês é igual ao de fechamento do mês anterior, em cada conta.",
            "Ajustes e transferências entre os dois saldos explicados.",
        ),
        (EXTRATO, SALDOS),
        1,
        "1.0",
        {"tolerancia": "R$ 0,00"},
    ),
    ControlDef(
        "BAN-03",
        "BAN",
        "Débitos bancários identificados",
        ("A4", "A3"),
        ("extrato do mês",),
        (
            "100% dos débitos ligados a uma despesa ou classificados como movimento que não é "
            "despesa (tarifa, IOF, aplicação, transferência entre contas, estorno).",
            "Pagamentos a intermediário ficam marcados como indiretos.",
        ),
        (EXTRATO, DESPESAS, PAGAMENTOS),
        1,
        "1.0",
    ),
    ControlDef(
        "BAN-04",
        "BAN",
        "Créditos bancários identificados",
        ("A4", "A5"),
        ("extrato do mês",),
        (
            "100% dos créditos classificados (arrecadação, rendimento, resgate, transferência, "
            "estorno ou empréstimo).",
            "Transferência e estorno nunca contam como receita operacional.",
        ),
        (EXTRATO,),
        1,
        "1.0",
    ),
    ControlDef(
        "BAN-05",
        "BAN",
        "Estornos e tentativas",
        ("A4",),
        ("extrato do mês",),
        (
            "Cada estorno ou devolução tem o débito original pareado (mesmo valor, até 10 dias "
            "antes).",
            "O débito devolvido não é contado como pagamento de despesa.",
        ),
        (EXTRATO, PAGAMENTOS),
        1,
        "1.0",
        {"janela_dias": "10"},
    ),
    ControlDef(
        "BAN-06",
        "BAN",
        "Transferências entre contas",
        ("A4",),
        ("extratos das contas de origem e destino",),
        (
            "Cada transferência tem a contrapartida na outra conta (mesmo valor, sinal oposto, "
            "até 3 dias).",
            "Transferência de ou para conta não apresentada fica com ressalva: crédito recebido "
            "não é origem comprovada.",
        ),
        (EXTRATO,),
        2,
        "1.0",
        {"janela_dias": "3"},
    ),
    ControlDef(
        "BAN-07",
        "BAN",
        "Pagamentos por intermediário",
        ("A4", "A6"),
        ("comprovante de liquidação ao favorecido final",),
        (
            "Todo pagamento feito por intermediário (administradora, plataforma de cobrança) tem "
            "comprovante cujo beneficiário final é o fornecedor da despesa (CNPJ).",
            "Saída ao intermediário não é liquidação final comprovada.",
        ),
        (EXTRATO, PAGAMENTOS, DOCUMENTOS),
        2,
        "1.0",
    ),
    ControlDef(
        "BAN-08",
        "BAN",
        "Lastro dos fundos",
        ("A8",),
        ("saldos por fundo e contas de suporte",),
        ("Cada fundo com lastro próprio demonstrado, não pela soma do consolidado.",),
        (FUNDOS, SALDOS),
        3,
        "—",
    ),
    ControlDef(
        "BAN-09",
        "BAN",
        "Aplicações e rendimentos",
        ("A4", "A8"),
        ("extrato próprio da aplicação",),
        ("Aportes, resgates, IR/IOF, rendimentos e saldos conciliados.",),
        (EXTRATO, FUNDOS),
        3,
        "—",
    ),
    ControlDef(
        "REC-01",
        "REC",
        "Receitas efetivas",
        ("A5", "A4"),
        ("extrato do mês", "demonstrativo de receitas"),
        (
            "Créditos de arrecadação conferem com o demonstrativo de receitas.",
            "Transferências e estornos separados da receita.",
            "Todos os créditos classificados (BAN-04).",
        ),
        (EXTRATO, RECEITAS, DOCUMENTOS),
        1,
        "1.0",
    ),
    ControlDef(
        "REC-02",
        "REC",
        "Boletos por unidade",
        ("A5",),
        ("títulos emitidos por unidade", "extrato ou retorno de cobrança"),
        (
            "Toda unidade cadastrada tem título na competência.",
            "Nenhum título repetido (mesma unidade, tipo e competência).",
            "Todo título pago tem confirmação: liquidação no retorno de cobrança (nosso número) "
            "ou crédito do extrato cujo valor fecha a soma dos pagamentos do dia.",
        ),
        (UNIDADES, RECEITAS, EXTRATO),
        2,
        "1.0",
        {"janela_credito_dias": "3"},
    ),
    ControlDef(
        "REC-03",
        "REC",
        "Consumo e rateios",
        ("A5",),
        ("fatura da concessionária", "rateio por unidade", "leituras por unidade"),
        (
            "A soma do rateio por unidade é igual à fatura do consumo, ao centavo.",
            "Com leituras: cada unidade paga fatura × consumo da unidade ÷ consumo total, com "
            "diferença de no máximo R$ 0,01 por arredondamento.",
            "Sem leituras: só a aritmética é validada; a medição fica pendente (ressalva).",
        ),
        (UNIDADES, DESPESAS, RECEITAS),
        2,
        "1.0",
        {"arredondamento_por_unidade": "R$ 0,01"},
    ),
    ControlDef(
        "REC-04",
        "REC",
        "Inadimplência",
        ("A5",),
        ("títulos por unidade com situação de pagamento",),
        (
            "Saldo em aberto no início + títulos vencidos no mês − pagamentos − cancelamentos = "
            "saldo em aberto no fim, por unidade.",
            "Título marcado como pago tem data e valor pagos; pagamento parcial fica em aberto "
            "pela diferença.",
            '"Não há inadimplentes" só depois de reconciliar os títulos em aberto.',
        ),
        (UNIDADES, RECEITAS),
        2,
        "1.0",
    ),
    ControlDef(
        "DES-01",
        "DES",
        "Despesas liquidadas",
        ("A6", "A4", "A3"),
        ("despesas do mês com documento", "débito bancário de cada pagamento"),
        (
            "Toda despesa vencida no mês tem documento e débito bancário ligado.",
            "O valor pago é igual ao valor da despesa, ao centavo.",
            "Pagamento a intermediário fica com ressalva até a liquidação final.",
        ),
        (DESPESAS, PAGAMENTOS, DOCUMENTOS),
        1,
        "1.0",
        {"tolerancia": "R$ 0,00"},
    ),
    ControlDef(
        "DES-02",
        "DES",
        "Tributos retidos e guias federais",
        ("A6",),
        ("retenções das notas da competência", "guia federal (DARF) da competência paga"),
        (
            "Soma das retenções federais (IR, PIS, COFINS, CSLL) das notas da competência = "
            "soma das guias federais da competência, ao centavo.",
            "Cada guia tem débito bancário ligado.",
            "Alíquotas não são calculadas: só a aritmética entre notas, guia e pagamento.",
        ),
        (TRIBUTOS, DOCUMENTOS, PAGAMENTOS),
        2,
        "1.0",
    ),
    ControlDef(
        "DES-03",
        "DES",
        "Encargos e tributos periódicos",
        ("A6",),
        ("perfil de auditoria", "guias FGTS, INSS/DCTFWeb e ISS da competência"),
        (
            "Com funcionários próprios: guia de FGTS e de INSS/DCTFWeb da competência.",
            "Com ISS retido nas notas: guia de ISS da competência com o total retido.",
            "Cada guia vencida tem débito bancário; guias de meses anteriores pagas no mês "
            "aparecem separadas.",
        ),
        (TRIBUTOS, PAGAMENTOS),
        2,
        "1.0",
    ),
    ControlDef(
        "DES-04",
        "DES",
        "Parcelamento fiscal",
        ("A6",),
        ("perfil de auditoria", "guias das parcelas"),
        (
            "Parcelas numeradas em sequência, com o mesmo total (02/04 depois de 01/04).",
            "Total diferente entre parcelas (02/02 e depois 03/04) exige documento do novo "
            "acordo: fica com ressalva até ser apresentado.",
            "Cada parcela vencida tem débito bancário.",
        ),
        (TRIBUTOS, PAGAMENTOS),
        2,
        "1.0",
    ),
    ControlDef(
        "CON-01",
        "CON",
        "Contrato vigente e preço",
        ("A7",),
        ("contrato aplicável à competência",),
        ("Valor bruto, escopo e reajuste conferidos com a nota.",),
        (CONTRATOS, DESPESAS),
        3,
        "—",
    ),
    ControlDef(
        "CON-02",
        "CON",
        "Serviço extraordinário e aceite",
        ("A7",),
        ("proposta, autorização, ordem de serviço e aceite",),
        ("Autorização dentro da alçada e serviço fora do escopo recorrente.",),
        (CONTRATOS, APROVACOES),
        3,
        "—",
    ),
    ControlDef(
        "CON-03",
        "CON",
        "Parcelas contratuais",
        ("A7",),
        ("cronograma e pagamentos",),
        ("Sequência, total e saldo futuro coerentes.",),
        (CONTRATOS, PAGAMENTOS),
        3,
        "—",
    ),
    ControlDef(
        "GOV-01",
        "GOV",
        "Orçado × realizado e caixa",
        ("A8",),
        ("orçamento aprovado",),
        ("Desvios explicados e projeção com premissas declaradas.",),
        (ORCAMENTO, DESPESAS),
        3,
        "—",
    ),
    ControlDef(
        "GOV-02",
        "GOV",
        "Seguros e obrigações técnicas",
        ("A7", "A8"),
        ("apólice, AVCB, laudos",),
        ("Vigência na competência e plano de renovação.",),
        (OBRIGACOES,),
        3,
        "—",
    ),
]

CONTROLS_BY_ID = {c.id: c for c in CONTROLS}
assert len(CONTROLS) == 25 and len(CONTROLS_BY_ID) == 25


def impacted_by(inputs: set[str]) -> list[str]:
    """Controls that read any of these inputs (the dependency graph, D122)."""
    return [c.id for c in CONTROLS if set(c.inputs) & inputs]
