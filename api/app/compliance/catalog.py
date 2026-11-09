"""Candidate obligations common in Brazilian condominiums (D112).

Candidates only: whether one applies, and how often, depends on the city, the state, the
building and its equipment. Nothing here cites a norm or states that an obligation applies;
a person validates each one (Plano D-10). ``months`` is a suggestion shown as
"confirme com o responsável técnico"; None means it varies too much to suggest.
"""

from dataclasses import dataclass

from app.db.enums import ComplianceCategory as C


@dataclass(frozen=True)
class CatalogItem:
    key: str
    name: str
    category: C
    months: int | None
    # Building profile fields that make it probable (D113); empty: the profile says nothing.
    needs: tuple[str, ...] = ()
    needs_label: str = ""


CATALOG: tuple[CatalogItem, ...] = (
    CatalogItem("avcb", "AVCB ou CLCB (Corpo de Bombeiros)", C.SEGURANCA_INCENDIO, None),
    CatalogItem("seguro", "Seguro obrigatório da edificação", C.SEGURO, 12),
    CatalogItem("extintores", "Recarga e inspeção dos extintores", C.SEGURANCA_INCENDIO, 12),
    CatalogItem(
        "hidrantes",
        "Teste de mangueiras e hidrantes",
        C.SEGURANCA_INCENDIO,
        12,
        ("hidrantes",),
        "hidrantes e mangueiras",
    ),
    CatalogItem(
        "spda", "Inspeção do SPDA (para-raios)", C.ELETRICA, 12, ("spda",), "para-raios (SPDA)"
    ),
    CatalogItem(
        "elevadores", "Manutenção dos elevadores", C.ELEVADORES, 1, ("elevadores",), "elevadores"
    ),
    CatalogItem(
        "elevadores_inspecao",
        "Inspeção anual dos elevadores",
        C.ELEVADORES,
        12,
        ("elevadores",),
        "elevadores",
    ),
    CatalogItem(
        "caixa_agua",
        "Limpeza dos reservatórios de água",
        C.AGUA,
        6,
        ("reservatorios",),
        "caixa d'água ou cisterna",
    ),
    CatalogItem(
        "potabilidade",
        "Análise de potabilidade da água",
        C.AGUA,
        6,
        ("reservatorios",),
        "caixa d'água ou cisterna",
    ),
    CatalogItem("pragas", "Controle de pragas (dedetização e desratização)", C.SAUDE, 6),
    CatalogItem("gas", "Inspeção da rede de gás", C.GAS, None, ("gas_encanado",), "gás encanado"),
    CatalogItem("eletrica", "Inspeção das instalações elétricas", C.ELETRICA, None),
    CatalogItem("inspecao_predial", "Inspeção predial", C.ESTRUTURA, None),
    CatalogItem(
        "bombas_gerador",
        "Manutenção de bombas e gerador",
        C.EQUIPAMENTOS,
        6,
        ("gerador", "bombas"),
        "gerador ou bombas",
    ),
    CatalogItem(
        "piscina", "Tratamento e análise da água da piscina", C.SAUDE, None, ("piscina",), "piscina"
    ),
)

BY_KEY = {item.key: item for item in CATALOG}

CATEGORY_LABEL = {
    C.SEGURANCA_INCENDIO.value: "Incêndio",
    C.SEGURO.value: "Seguro",
    C.ELEVADORES.value: "Elevadores",
    C.AGUA.value: "Água",
    C.SAUDE.value: "Saúde",
    C.GAS.value: "Gás",
    C.ELETRICA.value: "Elétrica",
    C.ESTRUTURA.value: "Estrutura",
    C.EQUIPAMENTOS.value: "Equipamentos",
    C.OUTROS.value: "Outros",
}
