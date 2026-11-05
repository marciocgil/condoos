"""Estimated cost per call (USD). Anthropic first-party list prices per 1M tokens.

Used only for the internal cost metric and the monthly ceiling; the invoice is the source
of truth. Cache writes (5-minute TTL) cost 1.25x input; cache reads are listed per model.
"""

from decimal import Decimal

# model -> (input, output, cache_read) per 1M tokens
PRICES_PER_MTOK: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "claude-opus-5-5": (Decimal("4.00"), Decimal("20.00"), Decimal("0.20")),
    "claude-sonnet-5-5": (Decimal("2.00"), Decimal("10.00"), Decimal("0.20")),
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50"), Decimal("0.01")),
}
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
# Unknown model (e.g. a server-side fallback): assume the most expensive known price.
_FALLBACK = max(PRICES_PER_MTOK.values())
MTOK = Decimal(1_000_000)


def estimate_cost_usd(
    model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0
) -> Decimal:
    price_in, price_out, price_cache_read = PRICES_PER_MTOK.get(model, _FALLBACK)
    cost = (
        Decimal(input_tokens) * price_in
        + Decimal(output_tokens) * price_out
        + Decimal(cache_read) * price_cache_read
        + Decimal(cache_write) * price_in * CACHE_WRITE_MULTIPLIER
    ) / MTOK
    return cost.quantize(Decimal("0.000001"))
