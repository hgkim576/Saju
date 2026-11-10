"""양력/음력 변환과 절기 조회."""

from __future__ import annotations

import bisect
import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from korean_lunar_calendar import KoreanLunarCalendar

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 앱이 지원하는 범위
SOLAR_MIN = date(1900, 1, 1)
SOLAR_MAX = date(2100, 12, 31)
# korean-lunar-calendar 라이브러리의 음력 지원 범위 상한 (음력 2050-11-18 = 양력 2050-12-31)
LUNAR_MAX_YEAR = 2050
LUNAR_MAX = (2050, 11, 18)

# 12절 → 사주 월 지지 index (자=0 … 해=11)
TERM_TO_MONTH_BRANCH = {
    "소한": 1, "입춘": 2, "경칩": 3, "청명": 4, "입하": 5, "망종": 6,
    "소서": 7, "입추": 8, "백로": 9, "한로": 10, "입동": 11, "대설": 0,
}


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool = False) -> date:
    """음력 날짜를 양력으로 변환. 존재하지 않는 날짜면 ValueError."""
    if not (SOLAR_MIN.year <= year <= LUNAR_MAX_YEAR):
        raise ValueError(f"음력은 {SOLAR_MIN.year}~{LUNAR_MAX_YEAR}년까지만 지원해요.")
    if (year, month, day) > LUNAR_MAX:
        y, m, d = LUNAR_MAX
        raise ValueError(f"음력은 {y}년 {m}월 {d}일까지만 지원해요. (음력 변환 데이터의 끝)")
    cal = KoreanLunarCalendar()
    if not cal.setLunarDate(year, month, day, is_leap):
        if is_leap:
            raise ValueError(f"음력 {year}년에는 윤{month}월이 없거나, 그 달에 {day}일이 없어요.")
        raise ValueError(f"음력 {year}년 {month}월에는 {day}일이 없어요.")
    result = date.fromisoformat(cal.SolarIsoFormat())
    if result < SOLAR_MIN:
        raise ValueError("1900년 1월 1일 이후 날짜만 지원해요.")
    return result


@lru_cache(maxsize=1)
def _load_terms() -> tuple[list[datetime], list[str]]:
    raw = json.loads((DATA_DIR / "solar_terms.json").read_text(encoding="utf-8"))
    pairs = sorted(
        (datetime.fromisoformat(ts), name)
        for year_terms in raw.values()
        for name, ts in year_terms
    )
    return [p[0] for p in pairs], [p[1] for p in pairs]


def latest_term(moment: datetime) -> tuple[str, datetime]:
    """moment(KST, naive) 이전(같은 분 포함)의 가장 최근 절(節)."""
    times, names = _load_terms()
    i = bisect.bisect_right(times, moment) - 1
    if i < 0:
        raise ValueError("절기 데이터 범위를 벗어났어요.")
    return names[i], times[i]


def next_term(moment: datetime) -> tuple[str, datetime]:
    """moment(KST, naive) 이후(같은 분 제외)의 가장 가까운 절(節)."""
    times, names = _load_terms()
    i = bisect.bisect_right(times, moment)
    if i >= len(times):
        raise ValueError("절기 데이터 범위를 벗어났어요.")
    return names[i], times[i]


def ipchun(year: int) -> datetime:
    """해당 양력 연도의 입춘 시각(KST)."""
    times, names = _load_terms()
    for t, n in zip(times, names, strict=True):
        if n == "입춘" and t.year == year:
            return t
    raise ValueError(f"{year}년 입춘 데이터가 없어요.")
