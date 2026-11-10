"""과거 한국 벽시계 시각 → 현재 한국 표준시(UTC+9) 기준 시각 변환.

출생 기록은 그 당시 벽시계 시각이다. 서머타임(UTC+10, UTC+9:30), UTC+8:30 표준시,
1908년 이전 지방평균시(UTC+8:28) 기간에 태어난 시각을 UTC+9 기준으로 바꿔야
KST로 만든 절기표·시진과 맞게 비교할 수 있다. 표는 scripts/gen_korea_clock.py로 만든다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "korea_clock.json"
KST_OFFSET = 540  # 분


@dataclass(frozen=True)
class ClockPeriod:
    start: datetime
    end: datetime | None
    offset: int  # UTC 대비 분
    kind: str


@lru_cache(maxsize=1)
def _periods() -> tuple[ClockPeriod, ...]:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    return tuple(
        ClockPeriod(datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]) if p["end"] else None,
                    p["offset"], p["kind"])
        for p in raw
    )


def period_at(local: datetime) -> ClockPeriod | None:
    """벽시계 시각이 속한 특수 구간 (UTC+9이면 None).

    시계를 되돌려 같은 시각이 두 번 있는 경우에는 표에서 앞에 나오는 구간(먼저 지난 시각)을 쓴다.
    예: 1987-10-11 02:30은 서머타임, 1954-03-20 23:45는 (UTC+8:30으로 바뀌기 전) UTC+9.
    """
    for p in _periods():
        if p.start <= local and (p.end is None or local < p.end):
            return None if p.offset == KST_OFFSET else p
    return None


def to_kst(local: datetime) -> tuple[datetime, ClockPeriod | None]:
    """당시 벽시계 시각을 UTC+9 기준 시각으로 바꾼다. (변환 시각, 적용한 구간)"""
    p = period_at(local)
    if p is None:
        return local, None
    return local + timedelta(minutes=KST_OFFSET - p.offset), p


def describe(p: ClockPeriod) -> str:
    diff = KST_OFFSET - p.offset
    sign = "+" if diff > 0 else "-"
    return f"{p.kind} 기간이라 표준시(UTC+9) 기준으로 {sign}{abs(diff)}분 보정했어요"
