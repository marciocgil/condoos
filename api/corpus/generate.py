"""Generate the fictitious 30-document corpus used to measure extraction (milestone 2).

    uv run python -m corpus.generate          # writes tests/fixtures/corpus/

Everything is invented: companies, CNPJs (valid check digits, random), people, CPFs,
amounts. The condominium is "Jardim das Acácias" from the seed. Output is deterministic.

Corpus (30): 8 NFS-e PDF, 6 boletos PDF, 2 utility bills PDF, 3 receipts PDF, 1 contract PDF,
3 NF-e XML, 2 NFS-e XML, 5 low-quality photos (rotated, blurred, noisy, low resolution).
``ground_truth.json`` holds the expected type and fields of each file.
"""

import io
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from app.core.br import format_cnpj, generate_cnpj
from app.db.models import Condominium, Supplier
from app.extraction.boleto import build_arrecadacao, build_bancario, format_bancario
from app.seed.data import build_seed

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "corpus"
RNG = random.Random(4242)
W, H = A4


def brl(value: Decimal) -> str:
    s = f"{value:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def dbr(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def fake_cpf(rng: random.Random) -> str:
    base = [rng.randint(0, 9) for _ in range(9)]
    for weight_start in (10, 11):
        total = sum(d * (weight_start - i) for i, d in enumerate(base))
        rest = total % 11
        base.append(0 if rest < 2 else 11 - rest)
    return "".join(map(str, base))


def fmt_cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


@dataclass
class Ctx:
    condo: Condominium
    suppliers: dict[str, Supplier]


def load_ctx() -> Ctx:
    seed = build_seed()
    objs = [o for phase in seed.objects for o in phase]
    condo = next(o for o in objs if isinstance(o, Condominium) and o.slug == "jardim-das-acacias")
    suppliers = {s.trade_name or s.legal_name: s for s in objs if isinstance(s, Supplier)}
    return Ctx(condo=condo, suppliers=suppliers)


class Pdf:
    def __init__(self) -> None:
        self.buf = io.BytesIO()
        self.c = Canvas(self.buf, pagesize=A4, invariant=1)
        self.y = H - 50

    def text(
        self, value: str, size: int = 10, bold: bool = False, x: float = 50, gap: float = 15
    ) -> None:
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.drawString(x, self.y, value)
        self.y -= gap

    def line(self) -> None:
        self.c.line(45, self.y + 8, W - 45, self.y + 8)
        self.y -= 6

    def bytes(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


# --------------------------------------------------------------------------- NFS-e PDF


def nfse_pdf(
    ctx: Ctx,
    n: int,
    sup: Supplier,
    desc: str,
    gross: Decimal,
    ret: dict[str, Decimal],
    issued: date,
    layout: int,
) -> tuple[bytes, dict[str, Any]]:
    net = gross - sum(ret.values(), Decimal("0"))
    numero = str(2000 + n * 37)
    p = Pdf()
    if layout == 0:
        p.text("PREFEITURA MUNICIPAL DE CIDADE MODELO", 12, True)
        p.text("NOTA FISCAL DE SERVIÇOS ELETRÔNICA - NFS-e", 12, True)
        p.text(f"Número da Nota: {numero}")
        p.text(f"Data e Hora de Emissão: {dbr(issued)} 10:{n:02d}:00")
        p.text(f"Competência: {issued:%m/%Y}")
        p.line()
        p.text("PRESTADOR DE SERVIÇOS", 10, True)
        p.text(f"Razão Social: {sup.legal_name}")
        p.text(f"CNPJ: {format_cnpj(sup.cnpj)}")
        p.line()
        p.text("TOMADOR DE SERVIÇOS", 10, True)
        p.text(f"Razão Social: {ctx.condo.name}")
        p.text(f"CNPJ: {format_cnpj(ctx.condo.cnpj)}")
        p.line()
        p.text("DISCRIMINAÇÃO DOS SERVIÇOS", 10, True)
        p.text(desc)
        p.line()
        p.text(f"Valor Total dos Serviços: {brl(gross)}")
        for k, label in (
            ("inss", "INSS"),
            ("ir", "IRRF"),
            ("pis", "PIS"),
            ("cofins", "COFINS"),
            ("csll", "CSLL"),
            ("iss", "ISS Retido"),
        ):
            if k in ret:
                p.text(f"{label}: {brl(ret[k])}")
        p.text(f"Valor Líquido: {brl(net)}", 10, True)
    else:
        p.text("NFS-e  Nota Fiscal de Serviço Eletrônica", 13, True)
        p.text("Município de Cidade Modelo - Secretaria da Fazenda", 9)
        p.text(
            f"Nº da NFS-e: {numero}        Emissão: {dbr(issued)}        Competência: {issued:%m/%Y}"
        )
        p.line()
        p.text(f"Prestador: {sup.legal_name}   CNPJ {format_cnpj(sup.cnpj)}", 9)
        p.text(f"Tomador: {ctx.condo.name}   CNPJ {format_cnpj(ctx.condo.cnpj)}", 9)
        p.line()
        p.text(f"Descrição do serviço: {desc}", 9)
        p.line()
        p.text(f"Valor dos serviços {brl(gross)}")
        p.text(
            "Retenções: "
            + (", ".join(f"{k.upper()} {brl(v)}" for k, v in ret.items()) or "nenhuma"),
            9,
        )
        p.text(f"Valor líquido da nota {brl(net)}", 10, True)
    truth = {
        "numero": numero,
        "data_emissao": issued.isoformat(),
        "competencia": f"{issued:%Y-%m}",
        "cnpj_prestador": sup.cnpj,
        "razao_social_prestador": sup.legal_name,
        "cnpj_tomador": ctx.condo.cnpj,
        "valor_servicos": str(gross),
        "valor_liquido": str(net),
        "discriminacao": desc,
        **{f"retencao_{k}": str(v) for k, v in ret.items()},
    }
    return p.bytes(), truth


# --------------------------------------------------------------------------- boletos


def boleto_pdf(
    ctx: Ctx, n: int, sup: Supplier, amount: Decimal, due: date
) -> tuple[bytes, dict[str, Any]]:
    bank = RNG.choice(["341", "237", "001"])
    free = "".join(str(RNG.randint(0, 9)) for _ in range(25))
    linha = build_bancario(bank, amount, due, free)
    doc_number = f"{due:%Y%m}{n:03d}"
    p = Pdf()
    p.text(
        {"341": "Itaú 341-7", "237": "Bradesco 237-2", "001": "Banco do Brasil 001-9"}[bank]
        + "   "
        + format_bancario(linha),
        10,
        True,
    )
    p.line()
    p.text("Local de pagamento: Pagável em qualquer banco até o vencimento")
    p.text(f"Beneficiário: {sup.legal_name}")
    p.text(f"CNPJ do Beneficiário: {format_cnpj(sup.cnpj)}")
    p.text(f"Vencimento: {dbr(due)}")
    p.text(f"Nº do Documento: {doc_number}")
    p.text(f"Valor do Documento: {brl(amount)}")
    p.line()
    p.text(f"Pagador: {ctx.condo.name} - CNPJ {format_cnpj(ctx.condo.cnpj)}")
    p.text("Instruções: não receber após 30 dias do vencimento.", 8)
    truth = {
        "linha_digitavel": linha,
        "valor": str(amount),
        "vencimento": due.isoformat(),
        "cnpj_beneficiario": sup.cnpj,
        "nome_beneficiario": sup.legal_name,
        "cnpj_pagador": ctx.condo.cnpj,
        "numero_documento": doc_number,
    }
    return p.bytes(), truth


def utility_pdf(
    ctx: Ctx, sup: Supplier, segment: str, amount: Decimal, due: date, label: str
) -> tuple[bytes, dict[str, Any]]:
    company = "".join(str(RNG.randint(0, 9)) for _ in range(4))
    free = "".join(str(RNG.randint(0, 9)) for _ in range(25))
    code = build_arrecadacao(segment, amount, company, free)
    p = Pdf()
    p.text(f"{sup.trade_name} - {label}", 13, True)
    p.text(f"{sup.legal_name}  CNPJ {format_cnpj(sup.cnpj)}", 9)
    p.line()
    p.text(f"Cliente: {ctx.condo.name}")
    p.text(f"CNPJ do cliente: {format_cnpj(ctx.condo.cnpj)}")
    p.text(f"Referência: {due:%m/%Y}")
    p.text(f"Vencimento: {dbr(due)}", 11, True)
    p.text(f"Total a pagar: {brl(amount)}", 11, True)
    p.line()
    blocks = [code[i : i + 12] for i in range(0, 48, 12)]
    p.text("  ".join(f"{b[:11]}-{b[11]}" for b in blocks), 11)
    truth = {
        "linha_digitavel": code,
        "valor": str(amount),
        "vencimento": due.isoformat(),
        "cnpj_beneficiario": sup.cnpj,
        "nome_beneficiario": sup.legal_name,
        "cnpj_pagador": ctx.condo.cnpj,
    }
    return p.bytes(), truth


# --------------------------------------------------------------------------- receipts / contract


def recibo_pdf(
    ctx: Ctx, name: str, amount: Decimal, when: date, what: str
) -> tuple[bytes, dict[str, Any]]:
    cpf = fake_cpf(RNG)
    p = Pdf()
    p.text("RECIBO", 16, True, gap=25)
    p.text(f"Valor: {brl(amount)}", 12, True, gap=22)
    p.text(f"Recebi de {ctx.condo.name}, CNPJ {format_cnpj(ctx.condo.cnpj)},")
    p.text(f"a importância de {brl(amount)}, referente a {what}.")
    p.text(f"Cidade Modelo, {dbr(when)}", gap=40)
    p.text("_______________________________________")
    p.text(f"{name} - CPF {fmt_cpf(cpf)}")
    truth = {
        "data": when.isoformat(),
        "valor": str(amount),
        "nome_recebedor": name,
        "documento_recebedor": cpf,
        "descricao": what,
    }
    return p.bytes(), truth


def contrato_pdf(ctx: Ctx, sup: Supplier) -> tuple[bytes, dict[str, Any]]:
    scope = ["limpeza de áreas comuns", "limpeza de garagem", "recolhimento de lixo"]
    p = Pdf()
    p.text("CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE LIMPEZA E CONSERVAÇÃO", 11, True, gap=22)
    p.text(f"CONTRATANTE: {ctx.condo.name}, CNPJ {format_cnpj(ctx.condo.cnpj)}.", 9)
    p.text(f"CONTRATADA: {sup.legal_name}, CNPJ {format_cnpj(sup.cnpj)}.", 9, gap=20)
    p.text("Cláusula 1ª - Do objeto: limpeza e conservação das áreas comuns do condomínio,", 9)
    p.text("compreendendo: " + "; ".join(scope) + ".", 9, gap=20)
    p.text("Cláusula 2ª - Do preço: a CONTRATANTE pagará mensalmente à CONTRATADA o valor", 9)
    p.text("mensal de R$ 9.200,00 (nove mil e duzentos reais).", 9, gap=20)
    p.text("Cláusula 3ª - Do reajuste: o valor será reajustado anualmente em janeiro pela", 9)
    p.text("variação acumulada do IPCA nos doze meses anteriores.", 9, gap=20)
    p.text("Cláusula 4ª - Da vigência: de 01/01/2023 a 31/12/2026.", 9)
    truth = {
        "cnpj_contratada": sup.cnpj,
        "razao_social_contratada": sup.legal_name,
        "cnpj_contratante": ctx.condo.cnpj,
        "objeto": "limpeza e conservação das áreas comuns do condomínio",
        "itens_escopo": scope,
        "valor_mensal": "9200.00",
        "indice_reajuste": "IPCA",
        "mes_base_reajuste": 1,
        "data_inicio": "2023-01-01",
        "data_fim": "2026-12-31",
    }
    return p.bytes(), truth


# --------------------------------------------------------------------------- XML


def nfe_xml(
    ctx: Ctx, n: int, emit_name: str, emit_cnpj: str, items: list[tuple[str, Decimal]], issued: date
) -> tuple[bytes, dict[str, Any]]:
    total = sum((v for _, v in items), Decimal("0"))
    numero = str(15000 + n)
    chave = (
        "35"
        + issued.strftime("%y%m")
        + emit_cnpj
        + "55"
        + "001"
        + numero.zfill(9)
        + "1"
        + "12345678"
        + "0"
    )
    dets = "".join(
        f'<det nItem="{i}"><prod><xProd>{name}</xProd><vProd>{value}</vProd></prod></det>'
        for i, (name, value) in enumerate(items, start=1)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe>'
        f'<infNFe Id="NFe{chave}" versao="4.00"><ide><nNF>{numero}</nNF>'
        f"<dhEmi>{issued.isoformat()}T09:30:00-03:00</dhEmi></ide>"
        f"<emit><CNPJ>{emit_cnpj}</CNPJ><xNome>{emit_name}</xNome></emit>"
        f"<dest><CNPJ>{ctx.condo.cnpj}</CNPJ><xNome>{ctx.condo.name}</xNome></dest>"
        f"{dets}<total><ICMSTot><vNF>{total}</vNF></ICMSTot></total></infNFe></NFe></nfeProc>"
    )
    truth = {
        "chave_acesso": chave,
        "numero": numero,
        "data_emissao": issued.isoformat(),
        "cnpj_emitente": emit_cnpj,
        "razao_social_emitente": emit_name,
        "cnpj_destinatario": ctx.condo.cnpj,
        "valor_total": str(total),
        "itens": [name for name, _ in items],
    }
    return xml.encode(), truth


def nfse_nacional_xml(
    ctx: Ctx, sup: Supplier, gross: Decimal, inss: Decimal, issued: date
) -> tuple[bytes, dict[str, Any]]:
    net = gross - inss
    desc = "Manutenção preventiva mensal de elevadores - outubro/2026"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.00"><infNFSe Id="NFS1">'
        f"<nNFSe>881</nNFSe><emit><CNPJ>{sup.cnpj}</CNPJ><xNome>{sup.legal_name}</xNome></emit>"
        f"<valores><vLiq>{net}</vLiq></valores>"
        f'<DPS versao="1.00"><infDPS Id="DPS1"><dhEmi>{issued.isoformat()}T08:00:00-03:00</dhEmi>'
        f"<dCompet>{issued.isoformat()}</dCompet>"
        f"<prest><CNPJ>{sup.cnpj}</CNPJ></prest><toma><CNPJ>{ctx.condo.cnpj}</CNPJ></toma>"
        f"<serv><cServ><xDescServ>{desc}</xDescServ></cServ></serv>"
        f"<valores><vServPrest><vServ>{gross}</vServ></vServPrest>"
        f"<trib><tribMun><tpRetISSQN>1</tpRetISSQN></tribMun><tribFed><vRetCP>{inss}</vRetCP></tribFed></trib>"
        "</valores></infDPS></DPS></infNFSe></NFSe>"
    )
    truth = {
        "numero": "881",
        "data_emissao": issued.isoformat(),
        "competencia": f"{issued:%Y-%m}",
        "cnpj_prestador": sup.cnpj,
        "razao_social_prestador": sup.legal_name,
        "cnpj_tomador": ctx.condo.cnpj,
        "valor_servicos": str(gross),
        "valor_liquido": str(net),
        "retencao_inss": str(inss),
        "discriminacao": desc,
    }
    return xml.encode(), truth


def nfse_abrasf_xml(
    ctx: Ctx, sup: Supplier, gross: Decimal, iss: Decimal, issued: date
) -> tuple[bytes, dict[str, Any]]:
    net = gross - iss
    desc = "Serviço de jardinagem: poda, corte de grama e adubação"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd"><Nfse versao="2.04"><InfNfse Id="N1">'
        f"<Numero>4471</Numero><DataEmissao>{issued.isoformat()}T11:00:00</DataEmissao>"
        f"<ValoresNfse><ValorLiquidoNfse>{net}</ValorLiquidoNfse></ValoresNfse>"
        f"<PrestadorServico><IdentificacaoPrestador><CpfCnpj><Cnpj>{sup.cnpj}</Cnpj></CpfCnpj>"
        f"</IdentificacaoPrestador><RazaoSocial>{sup.legal_name}</RazaoSocial></PrestadorServico>"
        "<DeclaracaoPrestacaoServico><InfDeclaracaoPrestacaoServico>"
        f"<Competencia>{issued.isoformat()}</Competencia>"
        f"<Servico><Valores><ValorServicos>{gross}</ValorServicos><ValorIss>{iss}</ValorIss></Valores>"
        f"<IssRetido>1</IssRetido><Discriminacao>{desc}</Discriminacao></Servico>"
        f"<Tomador><IdentificacaoTomador><CpfCnpj><Cnpj>{ctx.condo.cnpj}</Cnpj></CpfCnpj>"
        f"</IdentificacaoTomador><RazaoSocial>{ctx.condo.name}</RazaoSocial></Tomador>"
        "</InfDeclaracaoPrestacaoServico></DeclaracaoPrestacaoServico></InfNfse></Nfse></CompNfse>"
    )
    truth = {
        "numero": "4471",
        "data_emissao": issued.isoformat(),
        "competencia": f"{issued:%Y-%m}",
        "cnpj_prestador": sup.cnpj,
        "razao_social_prestador": sup.legal_name,
        "cnpj_tomador": ctx.condo.cnpj,
        "valor_servicos": str(gross),
        "valor_liquido": str(net),
        "retencao_iss": str(iss),
        "discriminacao": desc,
    }
    return xml.encode(), truth


# --------------------------------------------------------------------------- photos


def degrade(pdf_bytes: bytes, angle: float, blur: float, scale: float, quality: int) -> bytes:
    pdf = pdfium.PdfDocument(pdf_bytes)
    image = pdf[0].render(scale=1.6).to_pil().convert("RGB")
    pdf.close()
    image = image.rotate(angle, expand=True, fillcolor=(205, 200, 190))
    image = ImageEnhance.Brightness(image).enhance(0.88)
    image = ImageEnhance.Contrast(image).enhance(0.8)
    image = image.filter(ImageFilter.GaussianBlur(blur))
    noise = Image.effect_noise(image.size, 22).convert("RGB")
    image = Image.blend(image, noise, 0.12)
    image = image.resize((int(image.width * scale), int(image.height * scale)))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=quality)
    return out.getvalue()


# --------------------------------------------------------------------------- build


def build() -> dict[str, dict[str, Any]]:
    ctx = load_ctx()
    s = ctx.suppliers
    truth: dict[str, dict[str, Any]] = {}
    files: dict[str, bytes] = {}

    def add(name: str, doc_type: str, data: bytes, fields: dict[str, Any], **meta: Any) -> None:
        files[name] = data
        truth[name] = {"doc_type": doc_type, "fields": fields, **meta}

    oct_ = date(2026, 10, 1)
    nfse_specs = [
        (
            "Vigilare Portaria",
            "Serviços de portaria 24 horas - outubro/2026",
            Decimal("19277.00"),
            {"inss": Decimal("2120.47")},
        ),
        (
            "Brilho Total",
            "Limpeza e conservação das áreas comuns - outubro/2026",
            Decimal("9614.00"),
            {"inss": Decimal("1057.54"), "iss": Decimal("192.28")},
        ),
        (
            "Ascende Elevadores",
            "Manutenção preventiva mensal de 4 elevadores",
            Decimal("2491.20"),
            {},
        ),
        (
            "Verde Vivo",
            "Manutenção de jardins - poda e corte de grama",
            Decimal("1500.00"),
            {"iss": Decimal("30.00")},
        ),
        ("Praga Zero", "Dedetização e desratização trimestral", Decimal("650.00"), {}),
        (
            "Fixa Bem",
            "Troca de quadro de distribuição elétrica da garagem",
            Decimal("3850.00"),
            {
                "ir": Decimal("57.75"),
                "pis": Decimal("25.03"),
                "cofins": Decimal("115.50"),
                "csll": Decimal("38.50"),
            },
        ),
        (
            "Ascende Elevadores",
            "Atendimento a chamado - troca de botoeira do elevador 2",
            Decimal("780.00"),
            {},
        ),
        ("Fixa Bem", "Reparo em bomba de recalque", Decimal("1240.00"), {"iss": Decimal("24.80")}),
    ]
    nfse_pdfs: dict[int, bytes] = {}
    for i, (sup_key, desc, gross, ret) in enumerate(nfse_specs, start=1):
        data, fields = nfse_pdf(
            ctx, i, s[sup_key], desc, gross, ret, oct_ + timedelta(days=i), i % 2
        )
        nfse_pdfs[i] = data
        add(f"{i:02d}_nfse.pdf", "nfse", data, fields)

    boleto_specs = [
        ("Vigilare Portaria", Decimal("17156.53")),
        ("Brilho Total", Decimal("8364.18")),
        ("Ascende Elevadores", Decimal("2491.20")),
        ("Verde Vivo", Decimal("1470.00")),
        ("Praga Zero", Decimal("650.00")),
        ("Fixa Bem", Decimal("3613.22")),
    ]
    boleto_pdfs: dict[int, bytes] = {}
    for i, (sup_key, amount) in enumerate(boleto_specs, start=9):
        data, fields = boleto_pdf(
            ctx, i, s[sup_key], amount, date(2026, 10, 15) + timedelta(days=i - 9)
        )
        boleto_pdfs[i] = data
        add(f"{i:02d}_boleto.pdf", "boleto", data, fields)

    data, fields = utility_pdf(
        ctx,
        s["CEF Energia"],
        "3",
        Decimal("8143.27"),
        date(2026, 10, 20),
        "Conta de energia elétrica",
    )
    add("15_conta_energia.pdf", "boleto", data, fields)
    data, fields = utility_pdf(
        ctx,
        s["Saneamento Exemplar"],
        "2",
        Decimal("11687.90"),
        date(2026, 10, 22),
        "Conta de água e esgoto",
    )
    add("16_conta_agua.pdf", "boleto", data, fields)

    recibos = [
        (
            "Marcos Antônio Pereira",
            Decimal("350.00"),
            date(2026, 10, 12),
            "conserto do portão da garagem",
        ),
        (
            "Joana Lúcia Ferreira",
            Decimal("180.00"),
            date(2026, 10, 18),
            "limpeza da caixa de gordura",
        ),
        (
            "Roberto Alves Nunes",
            Decimal("420.00"),
            date(2026, 10, 25),
            "pintura do hall do bloco B",
        ),
    ]
    recibo_pdfs: dict[int, bytes] = {}
    for i, (name, amount, when, what) in enumerate(recibos, start=17):
        data, fields = recibo_pdf(ctx, name, amount, when, what)
        recibo_pdfs[i] = data
        add(f"{i:02d}_recibo.pdf", "recibo", data, fields)

    data, fields = contrato_pdf(ctx, s["Brilho Total"])
    add("20_contrato.pdf", "contrato", data, fields)

    material = [
        (
            "Casa das Ferragens Fictícia Ltda",
            [("Lâmpada LED 9W", Decimal("312.00")), ("Reator eletrônico", Decimal("148.50"))],
        ),
        (
            "Limpa Mais Distribuidora Fictícia Ltda",
            [
                ("Detergente neutro 5L", Decimal("189.90")),
                ("Saco de lixo 100L", Decimal("96.00")),
                ("Desinfetante 5L", Decimal("142.30")),
            ],
        ),
        ("Hidro Peças Fictícia Ltda", [("Boia elétrica para caixa d'água", Decimal("219.00"))]),
    ]
    for i, (name, items) in enumerate(material, start=21):
        data, fields = nfe_xml(
            ctx, i, name, generate_cnpj(RNG), items, oct_ + timedelta(days=i - 15)
        )
        add(f"{i:02d}_nfe.xml", "nfe", data, fields)

    data, fields = nfse_nacional_xml(
        ctx, s["Ascende Elevadores"], Decimal("2491.20"), Decimal("274.03"), date(2026, 10, 5)
    )
    add("24_nfse_nacional.xml", "nfse", data, fields)
    data, fields = nfse_abrasf_xml(
        ctx, s["Verde Vivo"], Decimal("1500.00"), Decimal("30.00"), date(2026, 10, 6)
    )
    add("25_nfse_abrasf.xml", "nfse", data, fields)

    photos = [
        ("26_foto_nfse.jpg", nfse_pdfs[1], "01_nfse.pdf", 3.5, 1.2, 0.7, 55),
        ("27_foto_nfse.jpg", nfse_pdfs[6], "06_nfse.pdf", -6.0, 1.8, 0.55, 45),
        ("28_foto_boleto.jpg", boleto_pdfs[10], "10_boleto.pdf", 2.0, 1.0, 0.75, 60),
        ("29_foto_boleto.jpg", boleto_pdfs[13], "13_boleto.pdf", -8.0, 2.2, 0.5, 40),
        ("30_foto_recibo.jpg", recibo_pdfs[18], "18_recibo.pdf", 5.0, 1.5, 0.6, 50),
    ]
    for name, src, src_name, angle, blur, scale, quality in photos:
        add(
            name,
            truth[src_name]["doc_type"],
            degrade(src, angle, blur, scale, quality),
            truth[src_name]["fields"],
            photo_of=src_name,
        )

    assert len(files) == 30, len(files)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (OUT / name).write_bytes(data)
    (OUT / "ground_truth.json").write_text(
        json.dumps(
            {"condominium_cnpj": ctx.condo.cnpj, "documents": truth},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return truth


if __name__ == "__main__":
    result = build()
    print(f"{len(result)} documentos gerados em {OUT}")
