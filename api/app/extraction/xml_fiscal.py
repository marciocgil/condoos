"""Deterministic reading of fiscal XML: NF-e, NFS-e Padrão Nacional and NFS-e ABRASF.

Values read from a well-formed XML are what the tax authority received, so they are
trusted (confidence 1.0); cross-checks in ``confidence.py`` still apply. Elements are found
by local name, ignoring namespaces, because municipal layouts vary in prefixes.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from app.db.enums import DocumentType


class NotFiscalXml(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter(root: Element, name: str) -> Iterator[Element]:
    for el in root.iter():
        if _local(el.tag) == name:
            yield el


def _first(root: Element | None, *path: str) -> Element | None:
    """Follow local names: _first(root, "emit", "CNPJ") = first emit's first CNPJ."""
    node = root
    for name in path:
        if node is None:
            return None
        node = next(_iter(node, name), None)
    return node


def _text(root: Element | None, *path: str) -> str | None:
    node = _first(root, *path)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _coalesce(*elements: Element | None) -> Element | None:
    """First element that exists. (``a or b`` is wrong: a childless Element is falsy.)"""
    return next((el for el in elements if el is not None), None)


@dataclass(frozen=True)
class XmlExtraction:
    doc_type: DocumentType
    values: dict[str, Any]
    layout: str


def parse_fiscal_xml(data: bytes) -> XmlExtraction:
    try:
        root = ElementTree.fromstring(data)
    except Exception as exc:  # defusedxml raises several types
        raise NotFiscalXml("XML inválido ou inseguro") from exc
    names = {_local(el.tag) for el in root.iter()}
    if "infNFe" in names:
        return _nfe(root)
    if "infNFSe" in names:
        return _nfse_nacional(root)
    if "InfNfse" in names or "CompNfse" in names:
        return _nfse_abrasf(root)
    raise NotFiscalXml("XML não é NF-e nem NFS-e")


def _nfe(root: Element) -> XmlExtraction:
    inf = _first(root, "infNFe")
    chave = (inf.get("Id") or "").removeprefix("NFe") if inf is not None else ""
    itens = [el.text.strip() for el in _iter(root, "xProd") if el.text and el.text.strip()]
    return XmlExtraction(
        doc_type=DocumentType.NFE,
        layout="nfe",
        values={
            "chave_acesso": chave or None,
            "numero": _text(root, "ide", "nNF"),
            "data_emissao": (_text(root, "ide", "dhEmi") or _text(root, "ide", "dEmi") or "")[:10]
            or None,
            "cnpj_emitente": _text(root, "emit", "CNPJ"),
            "razao_social_emitente": _text(root, "emit", "xNome"),
            "cnpj_destinatario": _text(root, "dest", "CNPJ"),
            "valor_total": _text(root, "ICMSTot", "vNF"),
            "itens": itens,
        },
    )


def _nfse_nacional(root: Element) -> XmlExtraction:
    inf = _first(root, "infNFSe")
    dps = _first(root, "infDPS")
    valores_dps = _first(dps, "valores")
    trib = _first(valores_dps, "trib")
    iss_retido = _text(trib, "tribMun", "tpRetISSQN") in ("2", "3")
    values = {
        "numero": _text(inf, "nNFSe"),
        "data_emissao": (_text(dps, "dhEmi") or "")[:10] or None,
        "competencia": (_text(dps, "dCompet") or "")[:7] or None,
        "cnpj_prestador": _text(inf, "emit", "CNPJ") or _text(dps, "prest", "CNPJ"),
        "razao_social_prestador": _text(inf, "emit", "xNome"),
        "cnpj_tomador": _text(dps, "toma", "CNPJ"),
        "valor_servicos": _text(valores_dps, "vServPrest", "vServ"),
        "valor_liquido": _text(inf, "valores", "vLiq"),
        "retencao_iss": _text(inf, "valores", "vISSQN") if iss_retido else None,
        "retencao_inss": _text(trib, "tribFed", "vRetCP"),
        "retencao_ir": _text(trib, "tribFed", "vRetIRRF"),
        "retencao_csll": _text(trib, "tribFed", "vRetCSLL"),
        "retencao_pis": (
            _text(trib, "tribFed", "piscofins", "vPis")
            if _text(trib, "tribFed", "piscofins", "tpRetPisCofins") == "1"
            else None
        ),
        "retencao_cofins": (
            _text(trib, "tribFed", "piscofins", "vCofins")
            if _text(trib, "tribFed", "piscofins", "tpRetPisCofins") == "1"
            else None
        ),
        "discriminacao": _text(dps, "serv", "cServ", "xDescServ"),
    }
    return XmlExtraction(doc_type=DocumentType.NFSE, layout="nfse_nacional", values=values)


def _nfse_abrasf(root: Element) -> XmlExtraction:
    inf = _first(root, "InfNfse")
    decl = _coalesce(_first(root, "InfDeclaracaoPrestacaoServico"), inf)
    servico = _first(decl, "Servico")
    valores = _first(servico, "Valores")
    iss_retido = (_text(servico, "IssRetido") or _text(valores, "IssRetido")) == "1"
    prestador = _coalesce(_first(inf, "PrestadorServico"), _first(decl, "Prestador"))
    tomador = _coalesce(_first(decl, "Tomador"), _first(decl, "TomadorServico"))
    values = {
        "numero": _text(inf, "Numero"),
        "data_emissao": (_text(inf, "DataEmissao") or "")[:10] or None,
        "competencia": (_text(decl, "Competencia") or _text(inf, "Competencia") or "")[:7] or None,
        "cnpj_prestador": _text(prestador, "Cnpj"),
        "razao_social_prestador": _text(prestador, "RazaoSocial"),
        "cnpj_tomador": _text(tomador, "Cnpj"),
        "valor_servicos": _text(valores, "ValorServicos"),
        "valor_liquido": _text(inf, "ValorLiquidoNfse") or _text(valores, "ValorLiquidoNfse"),
        "retencao_iss": (
            (_text(valores, "ValorIssRetido") or _text(valores, "ValorIss")) if iss_retido else None
        ),
        "retencao_inss": _text(valores, "ValorInss"),
        "retencao_ir": _text(valores, "ValorIr"),
        "retencao_pis": _text(valores, "ValorPis"),
        "retencao_cofins": _text(valores, "ValorCofins"),
        "retencao_csll": _text(valores, "ValorCsll"),
        "discriminacao": _text(servico, "Discriminacao"),
    }
    return XmlExtraction(doc_type=DocumentType.NFSE, layout="nfse_abrasf", values=values)
