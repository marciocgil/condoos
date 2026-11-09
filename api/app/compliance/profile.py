"""Building profile (D109): what the building has. It only SUGGESTS which catalogue
obligations probably apply or not; a person still validates each one (Plano D-10)."""

from dataclasses import dataclass
from typing import Any, Literal

from app.compliance.catalog import BY_KEY
from app.db.enums import ComplianceApplicability
from app.db.models import ComplianceObligation


@dataclass(frozen=True)
class ProfileField:
    key: str
    label: str
    kind: Literal["bool", "int"]


FIELDS: tuple[ProfileField, ...] = (
    ProfileField("andares", "Número de andares", "int"),
    ProfileField("elevadores", "Elevadores (quantidade)", "int"),
    ProfileField("gas_encanado", "Gás encanado", "bool"),
    ProfileField("gerador", "Gerador", "bool"),
    ProfileField("bombas", "Bombas de recalque ou de incêndio", "bool"),
    ProfileField("reservatorios", "Caixa d'água ou cisterna", "bool"),
    ProfileField("hidrantes", "Hidrantes e mangueiras", "bool"),
    ProfileField("spda", "Para-raios (SPDA)", "bool"),
    ProfileField("piscina", "Piscina", "bool"),
)
BY_FIELD = {f.key: f for f in FIELDS}
MAX_INT = 500


class ProfileError(ValueError):
    """Message shown to the user (pt-BR)."""


def clean(raw: dict[str, Any]) -> dict[str, bool | int]:
    """Known fields only; ``None`` removes a field (back to "não informado")."""
    out: dict[str, bool | int] = {}
    for key, value in raw.items():
        field = BY_FIELD.get(key)
        if field is None:
            raise ProfileError(f"Campo desconhecido no perfil: {key}.")
        if value is None:
            continue
        if field.kind == "bool":
            if not isinstance(value, bool):
                raise ProfileError(f"{field.label}: responda sim ou não.")
            out[key] = value
        else:
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_INT:
                raise ProfileError(f"{field.label}: informe um número de 0 a {MAX_INT}.")
            out[key] = value
    return out


def hint(ob: ComplianceObligation, profile: dict[str, Any]) -> dict[str, str] | None:
    """A suggestion for an obligation still "a validar", from the profile. Never a decision."""
    if ob.applicability != ComplianceApplicability.A_VALIDAR.value or not ob.catalog_key:
        return None
    item = BY_KEY.get(ob.catalog_key)
    if item is None or not item.needs:
        return None
    known = [k for k in item.needs if k in profile]
    if any(profile.get(k) for k in known):
        return {
            "code": "provavel",
            "text": f"O perfil do prédio indica {item.needs_label}: provavelmente se aplica.",
        }
    if known and len(known) == len(item.needs):
        return {
            "code": "provavel_nao",
            "text": (
                f"O perfil do prédio indica que não há {item.needs_label}: "
                "provavelmente não se aplica."
            ),
        }
    return None
