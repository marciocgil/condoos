"""Read-only tools of the "Pergunte ao CondoOS" agent (spec §10).

Every tool is bound to one ``CondoAccess``: the model never chooses the condominium, no
tool takes a condominium id, and every query filters by ``access.condominium_id`` while
RLS (scoped to that one condominium for the request) filters again. Nothing here writes.

Each record a tool returns carries a ``ref`` (e.g. ``despesa:<uuid>``). The agent cites
those refs; the service only accepts refs a tool actually returned in this conversation
turn (``ChatTools.seen``) and only numbers that appear in tool outputs.
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.chat.search import search
from app.core.br import format_cnpj
from app.core.time import add_months
from app.db.enums import NOT_AT_RISK, VISIBLE_TO_BOARD
from app.db.models import (
    BankTransaction,
    Competence,
    Condominium,
    Contract,
    Document,
    Expense,
    Finding,
    Supplier,
)
from app.enrichment.indices import load_index_table
from app.matching.categories import category_label
from app.rules.contracts import (
    amendments_by_contract,
    anniversaries,
    contract_value_at,
    value_at,
)

MAX_ROWS = 30


@dataclass(frozen=True)
class Citation:
    ref: str
    kind: str  # achado | despesa | contrato | documento | movimento | fornecedor | resumo
    id: str
    label: str


@dataclass(frozen=True)
class ScreenContext:
    """What the user is looking at, sent by the web app (validated by the router)."""

    screen: str = "resumo"
    finding_id: uuid.UUID | None = None
    competence: date | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{Decimal(value):.2f}"


def _month(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    try:
        year, month = int(text[:4]), int(text[5:7])
        return date(year, month, 1)
    except ValueError:
        return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except ArithmeticError:
        return None


@dataclass
class ChatTools:
    session: AsyncSession
    access: CondoAccess
    screen: ScreenContext = field(default_factory=ScreenContext)
    seen: dict[str, Citation] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)  # raw tool outputs (number check)
    calls: list[str] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ------------------------------------------------------------------ plumbing

    @property
    def condo(self) -> uuid.UUID:
        return self.access.condominium_id

    def _cite(self, kind: str, obj_id: Any, label: str, suffix: str = "") -> str:
        ref = f"{kind}:{obj_id}{suffix}"
        self.seen[ref] = Citation(ref=ref, kind=kind, id=str(obj_id), label=label[:160])
        return ref

    def _visible(self, stmt: Select[Any]) -> Select[Any]:
        if self.access.can(Permission.VIEW_PENDING_FINDINGS):
            return stmt
        return stmt.where(Finding.status.in_([s.value for s in VISIBLE_TO_BOARD]))

    async def run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run one tool by name (serialised: the database session is not concurrent)."""
        spec = next((s for s in self.specs() if s.name == name), None)
        if spec is None:
            return {"erro": f"ferramenta desconhecida: {name}"}
        async with self._lock:
            result = await spec.handler(args or {})
        self.calls.append(name)
        self.outputs.append(json.dumps(result, ensure_ascii=False, default=str))
        return result

    async def _supplier_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        rows = await self.session.execute(
            select(Supplier.id, Supplier.legal_name).where(Supplier.id.in_(ids))
        )
        return {r[0]: r[1] for r in rows}

    async def _supplier_ids_matching(self, text: str) -> list[uuid.UUID]:
        """Suppliers of THIS condominium (with an expense or contract here) by name or CNPJ."""
        digits = "".join(c for c in text if c.isdigit())
        like = f"%{text.strip()}%"
        cond = or_(Supplier.legal_name.ilike(like), Supplier.trade_name.ilike(like))
        if len(digits) == 14:
            cond = Supplier.cnpj == digits
        linked = or_(
            Supplier.id.in_(
                select(Expense.supplier_id).where(Expense.condominium_id == self.condo)
            ),
            Supplier.id.in_(
                select(Contract.supplier_id).where(Contract.condominium_id == self.condo)
            ),
        )
        return list(await self.session.scalars(select(Supplier.id).where(cond, linked)))

    async def _default_month(self) -> date | None:
        comps = list(
            await self.session.scalars(
                select(Competence)
                .where(Competence.condominium_id == self.condo)
                .order_by(Competence.month.desc())
            )
        )
        chosen = next((c for c in comps if c.status == "fechada"), comps[0] if comps else None)
        return chosen.month if chosen else None

    def _finding_row(self, f: Finding, supplier: str | None) -> dict[str, Any]:
        return {
            "ref": self._cite("achado", f.id, f.title),
            "id": str(f.id),
            "regra": f.rule_code,
            "gravidade": f.severity,
            "titulo": f.title,
            "valor_em_risco": _money(f.amount_at_risk),
            "status": f.status,
            "competencia": f"{f.competence:%Y-%m}",
            "fornecedor": supplier,
        }

    # ------------------------------------------------------------------ tools

    async def get_month_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        month = _month(args.get("month")) or await self._default_month()
        if month is None:
            return {"encontrado": False, "motivo": "nenhuma competência cadastrada"}
        comp = await self.session.scalar(
            select(Competence).where(
                Competence.condominium_id == self.condo, Competence.month == month
            )
        )
        findings = list(
            await self.session.scalars(
                self._visible(
                    select(Finding).where(
                        Finding.condominium_id == self.condo, Finding.competence == month
                    )
                ).order_by(Finding.amount_at_risk.desc(), Finding.id)
            )
        )
        open_ = [f for f in findings if f.status not in NOT_AT_RISK]
        exp = (
            await self.session.execute(
                select(func.count(), func.coalesce(func.sum(Expense.amount), 0)).where(
                    Expense.condominium_id == self.condo, Expense.competence == month
                )
            )
        ).one()
        names = await self._supplier_names({f.supplier_id for f in findings if f.supplier_id})
        return {
            "ref": self._cite("resumo", f"{month:%Y-%m}", f"Resumo de {month:%m/%Y}"),
            "competencia": f"{month:%Y-%m}",
            "status_competencia": comp.status if comp else None,
            "valor_em_risco": _money(sum((f.amount_at_risk for f in open_), Decimal("0"))),
            "achados": len(findings),
            "por_gravidade": {
                s: sum(f.severity == s for f in findings) for s in ("alta", "media", "baixa")
            },
            "despesas": int(exp[0]),
            "total_despesas": _money(Decimal(exp[1])),
            "principais_achados": [
                self._finding_row(f, names.get(f.supplier_id) if f.supplier_id else None)
                for f in findings[:5]
            ],
        }

    async def list_findings(self, args: dict[str, Any]) -> dict[str, Any]:
        stmt = self._visible(select(Finding).where(Finding.condominium_id == self.condo))
        if month := _month(args.get("month")):
            stmt = stmt.where(Finding.competence == month)
        if severity := args.get("severity"):
            stmt = stmt.where(Finding.severity == severity)
        if status := args.get("status"):
            stmt = stmt.where(Finding.status == status)
        if rule := args.get("rule_code"):
            stmt = stmt.where(Finding.rule_code == str(rule).upper())
        if supplier := args.get("supplier"):
            stmt = stmt.where(Finding.supplier_id.in_(await self._supplier_ids_matching(supplier)))
        rows = list(
            await self.session.scalars(
                stmt.order_by(Finding.amount_at_risk.desc(), Finding.id).limit(MAX_ROWS)
            )
        )
        names = await self._supplier_names({f.supplier_id for f in rows if f.supplier_id})
        return {
            "total": len(rows),
            "achados": [
                self._finding_row(f, names.get(f.supplier_id) if f.supplier_id else None)
                for f in rows
            ],
        }

    async def get_finding(self, args: dict[str, Any]) -> dict[str, Any]:
        raw = args.get("id") or (self.screen.finding_id and str(self.screen.finding_id))
        try:
            fid = uuid.UUID(str(raw))
        except ValueError:
            return {"encontrado": False, "motivo": "id de achado inválido"}
        f = await self.session.scalar(
            self._visible(
                select(Finding).where(Finding.id == fid, Finding.condominium_id == self.condo)
            )
        )
        if f is None:
            return {"encontrado": False, "motivo": "achado não encontrado neste condomínio"}
        names = await self._supplier_names({f.supplier_id} if f.supplier_id else set())
        row = self._finding_row(f, names.get(f.supplier_id) if f.supplier_id else None)
        evidence = []
        for e in f.evidence:
            kind = {"expense": "despesa", "contract": "contrato", "document": "documento"}.get(
                e.get("kind", ""), "movimento" if e.get("kind") == "bank_transaction" else None
            )
            if kind and e.get("id"):
                evidence.append(
                    {
                        "ref": self._cite(kind, e["id"], e.get("label", "")),
                        "tipo": kind,
                        "descricao": e.get("label", ""),
                        "trecho": e.get("excerpt", ""),
                    }
                )
        return {
            **row,
            "encontrado": True,
            "explicacao": f.explanation,
            "dados_da_regra": f.rule_inputs,
            "evidencias": evidence,
        }

    async def search_expenses(self, args: dict[str, Any]) -> dict[str, Any]:
        stmt = select(Expense).where(Expense.condominium_id == self.condo)
        if supplier := args.get("supplier"):
            stmt = stmt.where(
                Expense.supplier_id.in_(await self._supplier_ids_matching(str(supplier)))
            )
        if category := args.get("category"):
            stmt = stmt.where(Expense.category == str(category).lower())
        if start := _month(args.get("month_from")):
            stmt = stmt.where(Expense.competence >= start)
        if end := _month(args.get("month_to")):
            stmt = stmt.where(Expense.competence <= end)
        if (low := _decimal(args.get("min_amount"))) is not None:
            stmt = stmt.where(Expense.amount >= low)
        if (high := _decimal(args.get("max_amount"))) is not None:
            stmt = stmt.where(Expense.amount <= high)
        if text := args.get("text"):
            stmt = stmt.where(Expense.description.ilike(f"%{text}%"))
        # Count and sum over the filtered rows themselves (summing ``Expense.amount`` against
        # the subquery made a cartesian product: every expense times every match).
        filtered = stmt.subquery()
        totals = (
            await self.session.execute(
                select(func.count(), func.coalesce(func.sum(filtered.c.amount), 0))
            )
        ).one()
        rows = list(
            await self.session.scalars(
                stmt.order_by(Expense.competence.desc(), Expense.amount.desc()).limit(MAX_ROWS)
            )
        )
        names = await self._supplier_names({e.supplier_id for e in rows if e.supplier_id})
        paid: dict[uuid.UUID | None, uuid.UUID] = {
            r[0]: r[1]
            for r in (
                await self.session.execute(
                    select(BankTransaction.expense_id, BankTransaction.id).where(
                        BankTransaction.condominium_id == self.condo,
                        BankTransaction.expense_id.in_([e.id for e in rows]),
                    )
                )
            ).all()
        }
        out = []
        for e in rows:
            label = f"{e.description} — {names.get(e.supplier_id, '') if e.supplier_id else ''}"
            item: dict[str, Any] = {
                "ref": self._cite("despesa", e.id, label),
                "competencia": f"{e.competence:%Y-%m}",
                "emissao": e.issue_date.isoformat(),
                "vencimento": e.due_date.isoformat() if e.due_date else None,
                "valor": _money(e.amount),
                "categoria": e.category,
                "categoria_nome": category_label(e.category),
                "descricao": e.description,
                "fornecedor": names.get(e.supplier_id) if e.supplier_id else None,
                "nota_fiscal": e.invoice_number,
            }
            if e.id in paid:
                item["pagamento_ref"] = self._cite("movimento", paid[e.id], f"Pagamento: {label}")
            out.append(item)
        return {
            "total_encontrado": int(totals[0]),
            "soma": _money(Decimal(totals[1])),
            "mostrando": len(out),
            "despesas": out,
        }

    async def get_contract(self, args: dict[str, Any]) -> dict[str, Any]:
        stmt = select(Contract).where(Contract.condominium_id == self.condo)
        if raw_id := args.get("id"):
            try:
                stmt = stmt.where(Contract.id == uuid.UUID(str(raw_id)))
            except ValueError:
                return {"encontrado": False, "motivo": "id de contrato inválido"}
        elif supplier := args.get("supplier"):
            ids = await self._supplier_ids_matching(str(supplier))
            stmt = stmt.where(
                or_(Contract.supplier_id.in_(ids), Contract.object.ilike(f"%{supplier}%"))
            )
        contracts = list(await self.session.scalars(stmt.order_by(Contract.start_date)))
        if not contracts:
            return {"encontrado": False, "motivo": "nenhum contrato encontrado neste condomínio"}
        names = await self._supplier_names({c.supplier_id for c in contracts})
        table = await load_index_table(self.session)
        amendments = await amendments_by_contract(self.session, [c.id for c in contracts])
        today = await self._default_month() or date.today().replace(day=1)
        out = []
        for c in contracts:
            supplier_name = names.get(c.supplier_id, "")
            adjustments = []
            for anniversary in anniversaries(c.start_date, c.adjustment_base_month, today):
                adjustments.append(
                    {
                        "mes": f"{anniversary:%Y-%m}",
                        "valor_apos_reajuste": _money(
                            value_at(
                                c.monthly_value,
                                c.adjustment_index,
                                c.adjustment_base_month,
                                c.start_date,
                                anniversary,
                                table,
                            )
                        ),
                    }
                )
            mine = amendments.get(c.id, [])
            current = contract_value_at(c, mine, today, table)
            item: dict[str, Any] = {
                "ref": self._cite("contrato", c.id, f"Contrato {c.object} — {supplier_name}"),
                "id": str(c.id),
                "objeto": c.object,
                "fornecedor": supplier_name,
                "escopo": c.scope_items,
                "valor_mensal_original": _money(c.monthly_value),
                "valor_mensal_vigente": _money(current),
                "indice_reajuste": c.adjustment_index,
                "indice_reajuste_descricao": c.adjustment_index_other,
                "mes_base_reajuste": c.adjustment_base_month,
                "inicio": c.start_date.isoformat(),
                "fim": c.end_date.isoformat() if c.end_date else None,
                "reajustes": adjustments,
                "aditivos": [
                    {
                        "vigente_desde": a.effective_date.isoformat(),
                        "novo_valor_mensal": _money(a.monthly_value),
                        "novo_fim": a.end_date.isoformat() if a.end_date else None,
                        "descricao": a.description,
                    }
                    for a in mine
                ],
            }
            if c.source_document_id:
                doc = await self.session.get(Document, c.source_document_id)
                if doc is not None and doc.condominium_id == self.condo and doc.text_content:
                    item["documento_ref"] = self._cite(
                        "documento", doc.id, doc.original_filename, "#0"
                    )
                    item["clausulas"] = doc.text_content[:3000]
            out.append(item)
        return {"encontrado": True, "contratos": out}

    async def get_supplier(self, args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("cnpj") or args.get("name") or "")
        ids = await self._supplier_ids_matching(key) if key.strip() else []
        if not ids:
            return {"encontrado": False, "motivo": "fornecedor não encontrado neste condomínio"}
        out = []
        for s in await self.session.scalars(select(Supplier).where(Supplier.id.in_(ids))):
            stats = (
                await self.session.execute(
                    select(
                        func.count(),
                        func.coalesce(func.sum(Expense.amount), 0),
                        func.min(Expense.competence),
                        func.max(Expense.competence),
                    ).where(Expense.condominium_id == self.condo, Expense.supplier_id == s.id)
                )
            ).one()
            out.append(
                {
                    "ref": self._cite("fornecedor", s.id, s.legal_name),
                    "razao_social": s.legal_name,
                    "nome_fantasia": s.trade_name,
                    "cnpj": format_cnpj(s.cnpj),
                    "situacao_cadastral": s.registration_status,
                    "data_situacao": (
                        s.registration_status_date.isoformat()
                        if s.registration_status_date
                        else None
                    ),
                    "cnae_principal": s.cnae_main,
                    # partners carry masked CPFs only (seed and enrichment store them masked)
                    "socios": [
                        {"nome": p.get("name"), "cpf": p.get("cpf_masked")} for p in s.partners
                    ],
                    "despesas_neste_condominio": int(stats[0]),
                    "total_pago_neste_condominio": _money(Decimal(stats[1])),
                    "primeira_competencia": f"{stats[2]:%Y-%m}" if stats[2] else None,
                    "ultima_competencia": f"{stats[3]:%Y-%m}" if stats[3] else None,
                }
            )
        return {"encontrado": True, "fornecedores": out}

    async def compare_periods(self, args: dict[str, Any]) -> dict[str, Any]:
        a, b = _month(args.get("period_a")), _month(args.get("period_b"))
        if a is None or b is None:
            return {"erro": "informe period_a e period_b no formato AAAA-MM"}
        months = int(args.get("months") or 1)
        months = max(1, min(months, 12))
        cond = [Expense.condominium_id == self.condo]
        if category := args.get("category"):
            cond.append(Expense.category == str(category).lower())
        if supplier := args.get("supplier"):
            cond.append(Expense.supplier_id.in_(await self._supplier_ids_matching(str(supplier))))

        async def total(start: date) -> Decimal:
            end = add_months(start, months - 1)
            value = await self.session.scalar(
                select(func.coalesce(func.sum(Expense.amount), 0)).where(
                    and_(*cond, Expense.competence >= start, Expense.competence <= end)
                )
            )
            return Decimal(value or 0)

        ta, tb = await total(a), await total(b)
        diff = tb - ta
        pct = (diff / ta * 100).quantize(Decimal("0.01")) if ta else None
        label = f"Comparação {a:%m/%Y} × {b:%m/%Y}"
        return {
            "ref": self._cite("resumo", f"{a:%Y-%m}..{b:%Y-%m}", label),
            "categoria": category,
            "fornecedor": supplier,
            "meses_por_periodo": months,
            "periodo_a": f"{a:%Y-%m}",
            "total_a": _money(ta),
            "periodo_b": f"{b:%Y-%m}",
            "total_b": _money(tb),
            "diferenca": _money(diff),
            "variacao_percentual": None if pct is None else f"{pct}",
        }

    async def search_documents(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            return {"erro": "informe o texto da busca"}
        passages = await search(self.session, self.condo, query, limit=5)
        return {
            "trechos": [
                {
                    "ref": self._cite(
                        "documento",
                        p.document_id,
                        f"{p.document_name} (trecho {p.chunk_index + 1})",
                        f"#{p.chunk_index}",
                    ),
                    "documento": p.document_name,
                    "tipo": p.doc_type,
                    "texto": p.text,
                }
                for p in passages
            ]
        }

    async def get_screen_context(self, _: dict[str, Any]) -> dict[str, Any]:
        condo = await self.session.get(Condominium, self.condo)
        out: dict[str, Any] = {
            "condominio": condo.name if condo else None,
            "tela": self.screen.screen,
            "papel": sorted(r.value for r in self.access.roles),
            "hoje": date.today().isoformat(),
        }
        if self.screen.competence:
            out["competencia_na_tela"] = f"{self.screen.competence:%Y-%m}"
        if self.screen.finding_id:
            detail = await self.get_finding({"id": str(self.screen.finding_id)})
            if detail.get("encontrado"):
                out["achado_aberto"] = detail
        return out

    # ------------------------------------------------------------------ schema

    def specs(self) -> list[ToolSpec]:
        month = {"type": "string", "description": "Competência no formato AAAA-MM"}
        text = {"type": "string"}

        def obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": props,
                "required": required or [],
                "additionalProperties": False,
            }

        return [
            ToolSpec(
                "get_month_summary",
                "Resumo de uma competência: valor em risco, achados por gravidade, total de "
                "despesas e principais achados. Sem mês, usa o último mês fechado.",
                obj({"month": month}),
                self.get_month_summary,
            ),
            ToolSpec(
                "list_findings",
                "Lista achados do condomínio com filtros opcionais.",
                obj(
                    {
                        "month": month,
                        "severity": {"type": "string", "enum": ["alta", "media", "baixa"]},
                        "status": text,
                        "rule_code": {"type": "string", "description": "R01..R12"},
                        "supplier": {"type": "string", "description": "Nome ou CNPJ"},
                    }
                ),
                self.list_findings,
            ),
            ToolSpec(
                "get_finding",
                "Detalhe de um achado: explicação, dados da regra e evidências. Sem id, usa o "
                "achado aberto na tela.",
                obj({"id": text}),
                self.get_finding,
            ),
            ToolSpec(
                "search_expenses",
                "Busca despesas por fornecedor, categoria (ex.: portaria, limpeza, energia, "
                "agua, obras), período, faixa de valor ou texto da descrição. Devolve a soma.",
                obj(
                    {
                        "supplier": text,
                        "category": text,
                        "month_from": month,
                        "month_to": month,
                        "min_amount": {"type": "number"},
                        "max_amount": {"type": "number"},
                        "text": text,
                    }
                ),
                self.search_expenses,
            ),
            ToolSpec(
                "get_contract",
                "Contrato por id ou por fornecedor/objeto: valores (vigente, com aditivos), "
                "reajustes, aditivos, vigência e texto das cláusulas.",
                obj({"id": text, "supplier": text}),
                self.get_contract,
            ),
            ToolSpec(
                "get_supplier",
                "Dados cadastrais de um fornecedor deste condomínio (CNPJ ou nome) e quanto "
                "ele recebeu aqui.",
                obj({"cnpj": text, "name": text}),
                self.get_supplier,
            ),
            ToolSpec(
                "compare_periods",
                "Compara o total de despesas entre dois períodos (mesmo número de meses), "
                "opcionalmente por categoria ou fornecedor.",
                obj(
                    {
                        "period_a": month,
                        "period_b": month,
                        "months": {"type": "integer", "minimum": 1, "maximum": 12},
                        "category": text,
                        "supplier": text,
                    },
                    ["period_a", "period_b"],
                ),
                self.compare_periods,
            ),
            ToolSpec(
                "search_documents",
                "Busca trechos na convenção, regimento, atas, contratos, apólices, "
                "balancetes, laudos e planos de manutenção do condomínio.",
                obj({"query": text}, ["query"]),
                self.search_documents,
            ),
            ToolSpec(
                "get_screen_context",
                "O que o usuário está vendo agora (tela, achado aberto, competência) e o "
                "papel dele.",
                obj({}),
                self.get_screen_context,
            ),
        ]
