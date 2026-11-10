"""사주팔자(년·월·일·시주) 계산.

규칙
- 년주: 입춘 시각 기준으로 해가 바뀜
- 월주: 12절(節) 시각 기준으로 월이 바뀜, 월간은 오호둔법(년간 기준)
- 일주: 율리우스일 기준 60갑자 (1900-01-01 = 갑술일)
- 시주: 12시진, 시간은 오서둔법(일간 기준). 23시 이후는 다음 날 자시로 처리
  (야자시 옵션: 23시대는 일주를 당일로 두고, 시주는 다음 날 일간 기준 자시)
- 시간 모름이면 시주는 None
- 입력은 당시 벽시계 시각이다. 서머타임·UTC+8:30·지방평균시 기간이면 현재 KST(UTC+9) 기준으로
  바꾼 뒤(saju.clock) 모든 판정을 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from . import calendar as cal
from . import clock

STEMS_KO = "갑을병정무기경신임계"
STEMS_HANJA = "甲乙丙丁戊己庚辛壬癸"
STEM_ELEMENTS = ["목", "목", "화", "화", "토", "토", "금", "금", "수", "수"]

BRANCHES_KO = "자축인묘진사오미신유술해"
BRANCHES_HANJA = "子丑寅卯辰巳午未申酉戌亥"
BRANCH_ELEMENTS = ["수", "토", "목", "목", "토", "화", "화", "토", "금", "금", "토", "수"]
BRANCH_ANIMALS = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]

ELEMENT_HANJA = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}


@dataclass(frozen=True)
class Char:
    """천간 또는 지지 한 글자."""

    index: int
    hanja: str
    hangul: str
    element: str  # 목화토금수
    yin_yang: str  # 양 / 음
    is_stem: bool

    @property
    def element_hanja(self) -> str:
        return ELEMENT_HANJA[self.element]


def stem(i: int) -> Char:
    i %= 10
    return Char(i, STEMS_HANJA[i], STEMS_KO[i], STEM_ELEMENTS[i], "양" if i % 2 == 0 else "음", True)


def branch(i: int) -> Char:
    i %= 12
    return Char(i, BRANCHES_HANJA[i], BRANCHES_KO[i], BRANCH_ELEMENTS[i], "양" if i % 2 == 0 else "음", False)


@dataclass(frozen=True)
class Pillar:
    stem: Char
    branch: Char

    @property
    def hangul(self) -> str:
        return self.stem.hangul + self.branch.hangul

    @property
    def hanja(self) -> str:
        return self.stem.hanja + self.branch.hanja

    @property
    def sexagenary_index(self) -> int:
        """60갑자 순번 (갑자=0 … 계해=59)."""
        return (6 * self.stem.index - 5 * self.branch.index) % 60

    def __str__(self) -> str:
        return f"{self.hangul}({self.hanja})"


def pillar_from_index(i: int) -> Pillar:
    return Pillar(stem(i % 10), branch(i % 12))


@dataclass(frozen=True)
class Saju:
    birth: datetime  # 입력한 양력 벽시계 시각 (시간 모름이면 12:00) — 화면 표시용
    time_known: bool
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | None
    # 시간 모름 + 그날 중에 입춘/절기가 바뀌어 년·월주가 시간에 따라 달라질 수 있음
    boundary_ambiguous: bool = False
    # 계산에 실제로 쓴 KST(UTC+9) 기준 시각. 과거 시계 보정이 없으면 birth와 같다
    moment: datetime | None = None
    clock_note: str | None = None  # 과거 시계 보정 안내 문구
    night_rat: bool = False  # 야자시 적용 여부

    @property
    def kst(self) -> datetime:
        return self.moment or self.birth

    @property
    def pillars(self) -> list[Pillar | None]:
        """시주, 일주, 월주, 년주 순서 (전통 표기 순서: 오른쪽→왼쪽이 년→시)."""
        return [self.hour, self.day, self.month, self.year]

    @property
    def chars(self) -> list[Char]:
        out: list[Char] = []
        for p in (self.year, self.month, self.day, self.hour):
            if p is not None:
                out += [p.stem, p.branch]
        return out

    @property
    def day_master(self) -> Char:
        """일간 — 나를 나타내는 글자."""
        return self.day.stem

    @property
    def animal(self) -> str:
        return BRANCH_ANIMALS[self.year.branch.index]


def year_pillar(moment: datetime) -> Pillar:
    y = moment.year if moment >= cal.ipchun(moment.year) else moment.year - 1
    return pillar_from_index(y - 4)  # 1984 = 갑자


def month_pillar(moment: datetime, year_stem: Char) -> Pillar:
    term, _ = cal.latest_term(moment)
    b = cal.TERM_TO_MONTH_BRANCH[term]
    months_since_in = (b - 2) % 12  # 인월=0
    first_stem = (year_stem.index * 2 + 2) % 10  # 오호둔법: 갑·기년 → 병인월
    return Pillar(stem(first_stem + months_since_in), branch(b))


def day_pillar(d: date) -> Pillar:
    jdn = d.toordinal() + 1721425  # 율리우스일 수
    return pillar_from_index((jdn + 49) % 60)


def hour_branch_index(t: time) -> int:
    return ((t.hour + 1) // 2) % 12


def hour_pillar(t: time, day_stem: Char) -> Pillar:
    b = hour_branch_index(t)
    first_stem = (day_stem.index * 2) % 10  # 오서둔법: 갑·기일 → 갑자시
    return Pillar(stem(first_stem + b), branch(b))


def calculate(
    birth_date: date | tuple[int, int, int],
    birth_time: time | None = None,
    *,
    is_lunar: bool = False,
    is_leap_month: bool = False,
    solar_time_offset_minutes: int = 0,
    night_rat: bool = False,
    historical_clock: bool = True,
) -> Saju:
    """사주팔자 계산.

    birth_date: 양력 date, 또는 음력이면 (연, 월, 일) 정수 튜플(음력 2월 30일처럼 양력 date로 만들 수 없는 날 때문).
        음력에 date를 넘겨도 연·월·일만 쓴다.
    birth_time이 None이면 시간 모름 → 시주 없음, 년·월주는 그날 정오 기준.
    solar_time_offset_minutes: 진태양시 보정(예: -30). 일주·시주 판정에만 적용.
    night_rat: 야자시 — 23시대 출생의 일주를 당일로 둔다(시주는 다음 날 일간 기준 자시).
    historical_clock: 서머타임 등 과거 벽시계 시각을 UTC+9 기준으로 보정.
    """
    if is_lunar:
        ly, lm, ld = (birth_date.year, birth_date.month, birth_date.day) if isinstance(birth_date, date) else birth_date
        solar = cal.lunar_to_solar(int(ly), int(lm), int(ld), is_leap_month)
    elif isinstance(birth_date, date):
        solar = birth_date
    else:
        raise TypeError("양력은 date로 넘겨 주세요.")
    if not (cal.SOLAR_MIN <= solar <= cal.SOLAR_MAX):
        raise ValueError("1900년 1월 1일 ~ 2100년 12월 31일 사이 날짜만 지원해요.")

    time_known = birth_time is not None
    wall = datetime.combine(solar, birth_time or time(12, 0))
    moment, period = clock.to_kst(wall) if (time_known and historical_clock) else (wall, None)

    y = year_pillar(moment)
    m = month_pillar(moment, y.stem)

    local = moment + timedelta(minutes=solar_time_offset_minutes)
    late = time_known and local.hour >= 23
    next_day = day_pillar(local.date() + timedelta(days=1))
    d = day_pillar(local.date()) if (not late or night_rat) else next_day
    # 23시대 자시의 시간은 (야자시든 아니든) 다음 날 일간 기준으로 정한다
    h = hour_pillar(local.time(), next_day.stem if late else d.stem) if time_known else None

    ambiguous = False
    if not time_known:
        start, end = datetime.combine(solar, time(0, 0)), datetime.combine(solar, time(23, 59))
        ys, ye = year_pillar(start), year_pillar(end)
        ambiguous = (ys, month_pillar(start, ys.stem)) != (ye, month_pillar(end, ye.stem))

    return Saju(birth=wall, time_known=time_known, year=y, month=m, day=d, hour=h, boundary_ambiguous=ambiguous,
                moment=moment, clock_note=clock.describe(period) if period else None, night_rat=night_rat and late)
