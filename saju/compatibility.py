"""두 사람 궁합.

점수 구성 (합계 100, 최저 40 — 재미 콘텐츠라 지나치게 낮은 점수는 주지 않는다)
- 일간 관계 30: 천간합 30 / 상생 26 / 같은 오행 22 / 상극 16
- 띠(년지) 관계 25: 육합 25 / 삼합 22 / 같은 띠 18 / 보통 15 / 충 10
- 일지 관계 20: 육합 20 / 삼합 18 / 같음 14 / 보통 13 / 충 8
- 오행 보완 25: 내 부족한 오행을 상대가 가진 개수 + 그 반대, 합계 n → min(25, 7 + 3n)
"""

from __future__ import annotations

from dataclasses import dataclass

from . import content
from .analysis import ELEMENTS, count_elements, weakest_elements
from .pillars import Char, Saju

STEM_HAP = {frozenset(p) for p in [(0, 5), (1, 6), (2, 7), (3, 8), (4, 9)]}  # 갑기 을경 병신 정임 무계
BRANCH_YUKHAP = {frozenset(p) for p in [(0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)]}  # 자축 인해 묘술 진유 사신 오미
SAMHAP_GROUPS = [{8, 0, 4}, {11, 3, 7}, {2, 6, 10}, {5, 9, 1}]  # 신자진 해묘미 인오술 사유축

DAY_MASTER_SCORE = {"합": 30, "상생": 26, "같음": 22, "상극": 16}
BRANCH_SCORE = {"육합": 25, "삼합": 22, "같음": 18, "보통": 15, "충": 10}
DAY_BRANCH_SCORE = {"육합": 20, "삼합": 18, "같음": 14, "보통": 13, "충": 8}


def day_master_relation(a: Char, b: Char) -> str:
    if frozenset((a.index, b.index)) in STEM_HAP:
        return "합"
    d = (ELEMENTS.index(b.element) - ELEMENTS.index(a.element)) % 5
    return {0: "같음", 1: "상생", 4: "상생", 2: "상극", 3: "상극"}[d]


def branch_relation(a: Char, b: Char) -> str:
    if a.index == b.index:
        return "같음"
    if frozenset((a.index, b.index)) in BRANCH_YUKHAP:
        return "육합"
    if (a.index - b.index) % 12 == 6:
        return "충"
    if any({a.index, b.index} <= g for g in SAMHAP_GROUPS):
        return "삼합"
    return "보통"


@dataclass(frozen=True)
class Part:
    name: str
    relation: str
    score: int
    max_score: int
    message: str


@dataclass(frozen=True)
class Compatibility:
    total: int
    grade: dict
    parts: list[Part]


def element_fill(a: Saju, b: Saju) -> int:
    """a의 부족한 오행을 b가 가진 개수 + b의 부족한 오행을 a가 가진 개수."""
    ca, cb = count_elements(a), count_elements(b)
    return sum(cb[e] for e in weakest_elements(a)) + sum(ca[e] for e in weakest_elements(b))


def compatibility(a: Saju, b: Saju) -> Compatibility:
    text = content.compatibility()

    dm = day_master_relation(a.day_master, b.day_master)
    yb = branch_relation(a.year.branch, b.year.branch)
    db = branch_relation(a.day.branch, b.day.branch)
    fill = element_fill(a, b)
    el_score = min(25, 7 + 3 * fill)
    el_key = "high" if el_score >= 22 else "mid" if el_score >= 13 else "low"

    parts = [
        Part("일간 (나와 너)", dm, DAY_MASTER_SCORE[dm], 30, text["day_master"][dm]),
        Part("띠", yb, BRANCH_SCORE[yb], 25, text["branch"][yb]),
        Part("일지 (배우자 자리)", db, DAY_BRANCH_SCORE[db], 20, text["day_branch"][db]),
        Part("오행 보완", f"{fill}개 채움", el_score, 25, text["elements"][el_key]),
    ]
    total = max(40, sum(p.score for p in parts))
    grade = next(g for g in text["grades"] if total >= g["min"])
    return Compatibility(total, grade, parts)
