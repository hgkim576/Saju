"""대운(10년 운) 계산.

규칙
- 방향: 양년간 남자·음년간 여자 → 순행, 음년간 남자·양년간 여자 → 역행
- 대운수(시작 나이): 순행은 생시~다음 절, 역행은 이전 절~생시까지의 날수 ÷ 3 을 반올림 (최소 1, 최대 10)
  (3일 = 1년이므로 나머지 1일은 버리고 2일은 올리는 전통 방식과 같다)
- 대운 간지: 월주에서 순행이면 다음 간지, 역행이면 이전 간지로 한 칸씩
- 흐름 점수(1~5): 기본 3, 대운의 천간·지지 오행이 내 사주의 부족한 오행이면 +1, 가장 많은 오행이면 -1
"""

from __future__ import annotations

from dataclasses import dataclass

from . import calendar as cal
from . import content
from .analysis import TEN_GOD_GROUPS, strongest_elements, ten_god, weakest_elements
from .pillars import Pillar, Saju, pillar_from_index

PERIODS = 9


@dataclass(frozen=True)
class Daewoon:
    order: int  # 1부터
    start_age: int  # 만 나이
    start_year: int
    pillar: Pillar
    ten_god: str
    group: str
    score: int
    title: str
    summary: str

    @property
    def end_age(self) -> int:
        return self.start_age + 9


@dataclass(frozen=True)
class DaewoonResult:
    forward: bool
    start_age: int
    days_to_term: float
    periods: list[Daewoon]

    def current(self, age: int) -> Daewoon | None:
        for p in self.periods:
            if p.start_age <= age <= p.end_age:
                return p
        return None


def is_forward(saju: Saju, gender: str) -> bool:
    yang_year = saju.year.stem.yin_yang == "양"
    return yang_year == (gender == "남")


def start_age(saju: Saju, forward: bool) -> tuple[int, float]:
    if forward:
        _, t = cal.next_term(saju.kst)
        days = (t - saju.kst).total_seconds() / 86400
    else:
        _, t = cal.latest_term(saju.kst)
        days = (saju.kst - t).total_seconds() / 86400
    return min(10, max(1, round(days / 3))), days


def flow_score(saju: Saju, p: Pillar) -> int:
    weak, strong = set(weakest_elements(saju)), set(strongest_elements(saju))
    score = 3
    for e in (p.stem.element, p.branch.element):
        score += (e in weak) - (e in strong)
    return max(1, min(5, score))


def calculate_daewoon(saju: Saju, gender: str, periods: int = PERIODS, cover_age: int | None = None) -> DaewoonResult:
    """cover_age를 주면 그 나이가 들어가는 대운까지 늘려서 계산한다(기본 9개보다 오래 산 경우)."""
    forward = is_forward(saju, gender)
    age, days = start_age(saju, forward)
    if cover_age is not None and cover_age >= age:
        periods = max(periods, (cover_age - age) // 10 + 1)
    step = 1 if forward else -1
    texts = content.fortune()["daewoon"]
    out = []
    for i in range(periods):
        p = pillar_from_index(saju.month.sexagenary_index + step * (i + 1))
        god = ten_god(saju.day_master, p.stem)
        group = TEN_GOD_GROUPS[god]
        a = age + 10 * i
        out.append(Daewoon(i + 1, a, saju.birth.year + a, p, god, group, flow_score(saju, p),
                           texts[group]["title"], texts[group]["summary"]))
    return DaewoonResult(forward, age, days, out)
