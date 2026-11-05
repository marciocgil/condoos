"""Pydantic model -> JSON Schema accepted by structured outputs (strict).

Structured outputs require every object to list all its properties as required and to set
``additionalProperties: false``. Optional fields stay optional by being nullable. Validation
keywords the API does not enforce are dropped here and re-checked by Pydantic on our side.
"""

from functools import lru_cache
from typing import Any

from pydantic import BaseModel

_DROP = {
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
}


def _strict(node: Any) -> Any:
    if isinstance(node, dict):
        out = {k: _strict(v) for k, v in node.items() if k not in _DROP}
        if out.get("type") == "object" and "properties" in out:
            out["required"] = sorted(out["properties"])
            out["additionalProperties"] = False
        return out
    if isinstance(node, list):
        return [_strict(v) for v in node]
    return node


@lru_cache
def _cached(model: type[BaseModel]) -> dict[str, Any]:
    result: dict[str, Any] = _strict(model.model_json_schema())
    return result


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _cached(model)
