"""data/*.json 풀이 콘텐츠 로더. 문구 수정은 JSON만 고치면 된다."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str):
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def stems() -> list[dict]:
    return _load("stems")


@lru_cache(maxsize=1)
def branches() -> list[dict]:
    return _load("branches")


@lru_cache(maxsize=1)
def elements() -> dict[str, dict]:
    return _load("elements")


@lru_cache(maxsize=1)
def fortune() -> dict:
    return _load("fortune")


@lru_cache(maxsize=1)
def glossary() -> dict:
    return _load("glossary")


@lru_cache(maxsize=1)
def compatibility() -> dict:
    return _load("compatibility")
