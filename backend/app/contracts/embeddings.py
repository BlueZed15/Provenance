from __future__ import annotations

import math
from collections.abc import Sequence


EMBEDDING_DIMENSIONS = 1024


def validate_embedding(values: Sequence[float]) -> list[float]:
    if isinstance(values, (str, bytes)):
        raise TypeError("embedding must be a numeric sequence")
    if len(values) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"embedding must contain exactly {EMBEDDING_DIMENSIONS} values; "
            f"received {len(values)}"
        )

    normalized: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool):
            raise TypeError(f"embedding value {index} must be numeric, not boolean")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"embedding value {index} is not numeric") from exc
        if not math.isfinite(number):
            raise ValueError(f"embedding value {index} must be finite")
        normalized.append(number)
    return normalized


def validate_embeddings(
    values: Sequence[Sequence[float]], *, expected_count: int
) -> list[list[float]]:
    if len(values) != expected_count:
        raise RuntimeError(
            f"Mistral returned {len(values)} embeddings for {expected_count} texts"
        )
    return [validate_embedding(value) for value in values]
