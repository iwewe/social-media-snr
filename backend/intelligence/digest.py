"""Ringkasan hash kanonik untuk dataset, parameter, dan keluaran analisis (bukan bukti keaslian)."""

import hashlib
import json
from collections.abc import Iterable
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_ids(ids: Iterable[int]) -> str:
    return hashlib.sha256("\n".join(str(i) for i in sorted(ids)).encode("ascii")).hexdigest()
