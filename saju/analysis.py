"""오행·음양 집계, 십신, 행운 아이템, 운세."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from . import content
from .pillars import Char, Pillar, Saju, day_pillar, stem, year_pillar

ELEMENTS = ["목", "화", "토", "금", "수"]  # 상생 순서

# 지지의 십신은 정기(본기) 지장간으로 판단한다 (자=계, 오=정, 사=병, 해=임 …)
BRANCH_MAIN_STEM = [9, 5, 0, 1, 4, 2, 3, 5, 6, 7, 4, 8]

TEN_GOD_GROUPS = {
    "비견": "비겁", "겁재": "비겁",
    "식신": "식상", "상관": "식상",
    "편재": "재성", "정재": "재성",
    "편관": "관성", "정관": "관성",
    "편인": "인성", "정인": "인성",
}


# ── 집계 ──────────────────────────────────────────────────────

def count_elements(saju: Saju) -> dict[str, int]:
    """오행별 글자 수 (시간 모름이면 6글자 기준)."""
    counts = dict.fromkeys(ELEMENTS, 0)
    for c in saju.chars:
        counts[c.element] += 1
    return counts


def count_yin_yang(saju: Saju) -> dict[str, int]:
    counts = {"양": 0, "음": 0}
    for c in saju.chars:
        counts[c.yin_yang] += 1
    return counts


def _cycle_from(start: str) -> list[str]:
    i = ELEMENTS.index(start)
    return ELEMENTS[i:] + ELEMENTS[:i]


def strongest_elements(saju: Saju) -> list[str]:
    """가장 많은 오행 (동률이면 모두, 일간 오행부터 상생 순서)."""
    counts = count_elements(saju)
    top = max(counts.values())
    return [e for e in _cycle_from(saju.day_master.element) if counts[e] == top]


def weakest_elements(saju: Saju) -> list[str]:
    """가장 부족한 오행 (동률이면 모두, 일간 오행부터 상생 순서)."""
    counts = count_elements(saju)
    low = min(counts.values())
    return [e for e in _cycle_from(saju.day_master.element) if counts[e] == low]


def lucky_element(saju: Saju) -> str:
    """보완할 오행 하나: 가장 부족한 오행 중 일간 오행에서 상생 순서(목→화→토→금→수)로 가장 가까운 것."""
    return weakest_elements(saju)[0]


def lucky_items(saju: Saju) -> dict:
    e = lucky_element(saju)
    return {"element": e, **content.elements()[e]["lucky"]}


# ── 십신 ──────────────────────────────────────────────────────

def ten_god(day_master: Char, other: Char) -> str:
    """일간 기준 다른 글자의 십신."""
    target = stem(BRANCH_MAIN_STEM[other.index]) if not other.is_stem else other
    me = ELEMENTS.index(day_master.element)
    it = ELEMENTS.index(target.element)
    same_polarity = day_master.yin_yang == target.yin_yang
    rel = (it - me) % 5  # 0 같음, 1 내가 생함, 2 내가 극함, 3 나를 극함, 4 나를 생함
    names = [("비견", "겁재"), ("식신", "상관"), ("편재", "정재"), ("편관", "정관"), ("편인", "정인")][rel]
    return names[0] if same_polarity else names[1]


def ten_gods(saju: Saju) -> list[tuple[str | None, str | None]]:
    """saju.pillars 순서(시·일·월·년)로 (천간 십신, 지지 십신). 일간 자리는 '일간'."""
    dm = saju.day_master
    out: list[tuple[str | None, str | None]] = []
    for i, p in enumerate(saju.pillars):
        if p is None:
            out.append((None, None))
        elif i == 1:  # 일주
            out.append(("일간", ten_god(dm, p.branch)))
        else:
            out.append((ten_god(dm, p.stem), ten_god(dm, p.branch)))
    return out


# ── 운세 ──────────────────────────────────────────────────────

KST = timezone(timedelta(hours=9))


def today_kst() -> date:
    return datetime.now(KST).date()


@dataclass(frozen=True)
class DailyFortune:
    day: date
    pillar: Pillar
    group: str  # 비겁/식상/재성/관성/인성
    ten_god: str
    label: str
    stars: dict[str, int]
    message: str


def _seed(saju: Saju, *parts: object) -> bytes:
    key = "|".join([saju.birth.isoformat(), saju.day.hangul, *map(str, parts)])
    return hashlib.sha256(key.encode()).digest()


def daily_fortune(saju: Saju, day: date | None = None) -> DailyFortune:
    """오늘 일진과 내 일간의 관계로 보는 운세. 같은 사람·같은 날이면 항상 같은 결과."""
    day = day or today_kst()
    p = day_pillar(day)
    god = ten_god(saju.day_master, p.stem)
    group = TEN_GOD_GROUPS[god]
    data = content.fortune()["daily"][group]

    stars = dict(data["base"])
    # 일진 지지가 주는 보너스
    branch_group = TEN_GOD_GROUPS[ten_god(saju.day_master, p.branch)]
    bonus = {"비겁": "건강", "인성": "건강", "식상": "연애", "재성": "재물", "관성": "총운"}[branch_group]
    stars[bonus] += 1
    # 사람마다 조금씩 다른 결정적 변화 (-1, 0, +1)
    seed = _seed(saju, day.isoformat())
    for i, k in enumerate(stars):
        stars[k] = max(1, min(5, stars[k] + seed[i] % 3 - 1))

    message = data["messages"][seed[8] % len(data["messages"])]
    return DailyFortune(day, p, group, god, data["label"], stars, message)


@dataclass(frozen=True)
class YearlyFortune:
    year: int
    pillar: Pillar
    group: str
    ten_god: str
    title: str
    summary: str


def yearly_fortune(saju: Saju, day: date | None = None) -> YearlyFortune:
    """올해(입춘 기준) 세운 간지와 일간의 관계."""
    day = day or today_kst()
    p = year_pillar(datetime.combine(day, time(12, 0)))
    god = ten_god(saju.day_master, p.stem)
    group = TEN_GOD_GROUPS[god]
    data = content.fortune()["yearly"][group]
    saju_year = day.year if p.sexagenary_index == (day.year - 4) % 60 else day.year - 1
    return YearlyFortune(saju_year, p, group, god, data["title"], data["summary"])
