"""Per-field extraction accuracy over the fictitious corpus (milestone 2 acceptance).

    uv run python -m corpus.accuracy                 # mode from LLM_MODE / API key
    uv run python -m corpus.accuracy --out ../docs/extraction_accuracy.md

Metrics:
- automatic rate: documents that need no human review (target ≥ 90%).
- automatic but wrong: automatic documents with any field different from the ground truth
  (the dangerous case; target 0).
- per field: share of documents where the field came out exactly right.

Live mode calls the API and logs every call in ``llm_calls`` (needs the database).
Replay/off modes need neither the key nor the database.
"""

import argparse
import asyncio
import json
import time
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.db.enums import DocumentType
from app.extraction.convert import docling_available
from app.extraction.fields import InvalidValue, normalize, specs_for
from app.extraction.pipeline import analyze
from app.ingestion.filetypes import sniff
from app.llm.client import resolve_mode

CORPUS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "corpus"
REFERENCE_DATE = date(2026, 11, 5)


def _fold(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(_fold(v) for v in value)
    if isinstance(value, str):
        text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return " ".join(text.lower().split())
    return value


def same(kind: str, expected: Any, got: Any) -> bool:
    try:
        exp = normalize(kind, expected)  # type: ignore[arg-type]
    except InvalidValue:
        exp = expected
    return bool(_fold(exp) == _fold(got))


@dataclass
class DocResult:
    name: str
    expected_type: str
    got_type: str
    automatic: bool
    field_ok: dict[str, bool] = field(default_factory=dict)
    # A filled value that differs from the truth, or a required field that differs.
    field_wrong: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    source: str = ""
    seconds: float = 0.0

    @property
    def has_wrong_data(self) -> bool:
        return self.expected_type != self.got_type or any(self.field_wrong.values())


async def evaluate() -> list[DocResult]:
    truth = json.loads((CORPUS / "ground_truth.json").read_text(encoding="utf-8"))
    condo_cnpj = truth["condominium_cnpj"]
    condo_id = uuid.uuid5(uuid.NAMESPACE_URL, "condoos-corpus")
    session_cm: Any = None
    session = None
    if resolve_mode() in ("live", "record"):
        from app.db.session import get_worker_engine, sessionmaker_for

        session_cm = sessionmaker_for(get_worker_engine())()
        session = await session_cm.__aenter__()

    results = []
    try:
        for name, item in sorted(truth["documents"].items()):
            data = (CORPUS / name).read_bytes()
            started = time.monotonic()
            analysis = await analyze(
                session,
                data=data,
                mime=sniff(name, data),
                filename=name,
                condominium_id=condo_id,
                condominium_cnpj=condo_cnpj,
                today=REFERENCE_DATE,
            )
            if session is not None:
                await session.commit()
            specs = specs_for(DocumentType(item["doc_type"]))
            kinds = {s.name: s.kind for s in specs}
            required = {s.name for s in specs if s.required}
            res = DocResult(
                name=name,
                expected_type=item["doc_type"],
                got_type=analysis.doc_type.value,
                automatic=analysis.complete,
                reasons=analysis.reasons,
                source=analysis.extraction_source,
                seconds=time.monotonic() - started,
            )
            for fname, expected in item["fields"].items():
                got = analysis.values.get(fname)
                ok = same(kinds[fname], expected, got)
                res.field_ok[fname] = ok
                res.field_wrong[fname] = not ok and (got is not None or fname in required)
            results.append(res)
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)
    return results


def report(results: list[DocResult]) -> str:
    total = len(results)
    auto = [r for r in results if r.automatic]
    auto_wrong = [r for r in auto if r.has_wrong_data]
    type_ok = sum(r.expected_type == r.got_type for r in results)
    per_field: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for fname, ok in r.field_ok.items():
            per_field[fname].append(ok)

    engine = "Docling" if docling_available() else "pypdfium2 (sem OCR)"
    lines = [
        "# Acurácia da extração — corpus fictício (Marco 2)",
        "",
        f"- Data de referência: {REFERENCE_DATE:%d/%m/%Y}",
        f"- Modo do LLM: `{resolve_mode()}` · Conversor: {engine}",
        f"- Documentos: {total}",
        "",
        "| Métrica | Resultado | Meta |",
        "| --- | --- | --- |",
        f"| Documentos sem revisão manual | {len(auto)}/{total} ({100 * len(auto) / total:.0f}%) | ≥ 90% |",
        f"| Automáticos com dado divergente | {len(auto_wrong)} | 0 |",
        f"| Tipo de documento correto | {type_ok}/{total} ({100 * type_ok / total:.0f}%) | — |",
        "",
        "## Acurácia por campo",
        "",
        "| Campo | Corretos | % |",
        "| --- | --- | --- |",
    ]
    for fname in sorted(per_field):
        oks = per_field[fname]
        lines.append(f"| {fname} | {sum(oks)}/{len(oks)} | {100 * sum(oks) / len(oks):.0f}% |")
    lines += [
        "",
        "## Por documento",
        "",
        "| Arquivo | Tipo esperado | Tipo obtido | Automático | Campos certos | Fonte | Motivo da revisão |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        n_ok = sum(r.field_ok.values())
        reason = "; ".join(r.reasons)[:140].replace("|", "/")
        lines.append(
            f"| {r.name} | {r.expected_type} | {r.got_type} | {'sim' if r.automatic else 'não'} "
            f"| {n_ok}/{len(r.field_ok)} | {r.source} | {reason} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    text = report(asyncio.run(evaluate()))
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
