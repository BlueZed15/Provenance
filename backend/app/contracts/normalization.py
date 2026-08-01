from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(value: str) -> str:
    """Return stable UTF-8/NFC text suitable for prompts, hashing, and Postgres."""
    if not isinstance(value, str):
        raise TypeError("text must be a string")

    # Standalone UTF-16 surrogates cannot be stored as UTF-8. Replace only
    # invalid surrogates while retaining normal Unicode, emoji, and ZWJ.
    value = value.encode("utf-8", errors="replace").decode("utf-8")
    value = unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
    )

    cleaned: list[str] = []
    for character in value:
        if character in {"\n", "\t"}:
            cleaned.append(character)
        elif unicodedata.category(character) == "Cc":
            # PostgreSQL text cannot contain NUL. Other C0/C1 controls add no
            # useful ticket content. A space avoids accidentally joining the
            # words on either side of a removed character.
            cleaned.append(" ")
        else:
            cleaned.append(character)

    normalized = _HORIZONTAL_WHITESPACE.sub(" ", "".join(cleaned))
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    return _EXCESS_BLANK_LINES.sub("\n\n", normalized).strip()


def normalize_identifier(value: str, *, field: str, max_length: int = 255) -> str:
    normalized = normalize_text(value).replace("\n", " ")
    normalized = _HORIZONTAL_WHITESPACE.sub(" ", normalized).strip()
    if not normalized:
        raise ValueError(f"{field} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field} must be at most {max_length} characters")
    return normalized


def parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, str):
        timestamp = value.strip()
        if timestamp.endswith(("Z", "z")):
            timestamp = f"{timestamp[:-1]}+00:00"
        try:
            value = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise ValueError("timestamp must be ISO 8601") from exc
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime or ISO 8601 string")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def json_safe(value: Any, *, _depth: int = 0) -> Any:
    """Convert connector metadata to strict JSONB-compatible primitives."""
    if _depth > 20:
        raise ValueError("metadata nesting exceeds 20 levels")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, Enum):
        return json_safe(value.value, _depth=_depth + 1)
    if isinstance(value, datetime):
        return parse_timestamp(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return normalize_text(value.decode("utf-8", errors="replace"))
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = normalize_text(str(key))
            if not normalized_key:
                raise ValueError("metadata keys must not be blank")
            if normalized_key in result:
                raise ValueError(
                    f"metadata contains duplicate normalized key: {normalized_key}"
                )
            result[normalized_key] = json_safe(item, _depth=_depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_safe(item, _depth=_depth + 1) for item in value]
    if isinstance(value, set):
        return [json_safe(item, _depth=_depth + 1) for item in sorted(value, key=str)]

    return normalize_text(str(value))


def assert_strict_json(value: Any) -> None:
    json.dumps(value, ensure_ascii=False, allow_nan=False)


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
