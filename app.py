"""사주 앱 Streamlit 진입점."""

from datetime import date, time
from pathlib import Path

import streamlit as st

from saju import analysis, calculate, content, visuals
from saju.calendar import LUNAR_MAX_YEAR, SOLAR_MAX, SOLAR_MIN
from saju.compatibility import compatibility
from saju.daewoon import calculate_daewoon

st.set_page_config(page_title="사주냥", page_icon="🔮")


@st.cache_data
def load_content() -> dict:
    return {
        "stems": content.stems(),
        "branches": content.branches(),
        "elements": content.elements(),
        "fortune": content.fortune(),
        "glossary": content.glossary(),
        "compat": content.compatibility(),
    }


@st.cache_data
def load_css() -> str:
    return (Path(__file__).parent / "assets" / "style.css").read_text(encoding="utf-8")


def card_png(saju, params: dict) -> bytes:
    """결과 카드 PNG. rerun마다 다시 그리지 않도록 이 사용자의 세션에만 보관한다.

    st.cache_data는 모든 접속자가 공유하는 서버 메모리라 개인정보(생년월일)가 남으므로 쓰지 않는다.
    """
    cached = st.session_state.get("_card")
    if cached is None or cached[0] != params:
        cached = (params, visuals.result_card_png(saju, params["name"]))
        st.session_state["_card"] = cached
    return cached[1]


C = load_content()
E = C["elements"]


def form_key(field: str) -> str:
    """폼 위젯 키. '다시 보기' 때 버전을 올려 위젯을 새로 만든다.

    폼 안 위젯은 session_state 키를 지워도 브라우저에 남은 값이 다시 전송되므로(REVIEW 🟠-2),
    키 자체를 바꿔 새 위젯으로 만드는 방식으로 초기화한다. 첫 화면(버전 0)은 원래 키를 그대로 쓴다.
    """
    ver = st.session_state.get("form_ver", 0)
    return field if ver == 0 else f"{field}#{ver}"


def reset() -> None:
    st.session_state["form_ver"] = st.session_state.get("form_ver", 0) + 1
    for k in ("params", "partner", "_card"):
        st.session_state.pop(k, None)


def has_batchim(word: str) -> bool:
    last = word[-1]
    return "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0


def eun_neun(word: str) -> str:
    """받침 유무에 따라 '은/는'을 붙인다."""
    return word + ("은" if has_batchim(word) else "는")


def i_ga(word: str) -> str:
    """받침 유무에 따라 '이/가'를 붙인다. (궁합이 / 절기가)"""
    return word + ("이" if has_batchim(word) else "가")


def stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def html(fragment: str) -> None:
    """커스텀 HTML 조각 출력 (스타일은 assets/style.css 한 곳에서 관리)."""
    st.html(fragment)


def term_help(*names: str) -> None:
    with st.expander(f"❓ {i_ga(', '.join(names))} 뭐예요?"):
        for n in names:
            st.markdown(f"**{n}** — {C['glossary']['terms'][n]}")


def birth_form(prefix: str, form_id: str, submit_label: str, state_key: str, *, who: str = "",
               gender_help: str = "대운의 진행 방향을 정하는 데 쓰여요.", default_gender: str | None = None) -> None:
    """생년월일 입력 폼. 제출하면 st.session_state[state_key]에 calculate() 인자를 저장한다.

    태어난 시·성별은 기본값 없이 시작한다. 기본값이 있으면 고르는 것을 잊어도 그 값(12시·남)으로
    조용히 계산되기 때문이다. 시를 고르지도 '몰라요'를 체크하지도 않으면 안내만 하고 저장하지 않는다.
    default_gender: 상대방 폼처럼 결과에 영향이 없는 경우에만 기본값을 준다.

    who: 라벨 앞에 붙일 말(예: "상대방 ") — 두 폼의 라벨이 같아 스크린리더가 헷갈리지 않도록.
    결과가 rerun(다운로드 버튼 등)에도 유지되도록 세션에만 저장한다 (서버·파일에는 저장하지 않음).
    """

    def k(field: str) -> str:
        return form_key(prefix + field)

    # 양력/음력에 따라 입력 위젯이 달라지므로 폼 밖에 둔다 (폼 안 위젯은 제출 전까지 rerun되지 않음)
    is_lunar = st.radio(f"{who}달력", ["양력", "음력"], horizontal=True, key=k("cal_type")) == "음력"

    with st.form(form_id):
        name = st.text_input(f"{who}이름 (선택)", max_chars=20, key=k("name"))
        gender = st.radio(f"{who}성별", ["남", "여"], horizontal=True, key=k("gender"), help=gender_help,
                          index=None if default_gender is None else ["남", "여"].index(default_gender))

        if is_lunar:
            c1, c2, c3 = st.columns(3)
            ly = c1.number_input(f"{who}음력 연도 ({SOLAR_MIN.year}~{LUNAR_MAX_YEAR})", SOLAR_MIN.year, LUNAR_MAX_YEAR,
                                 1990, key=k("ly"), help="음력 변환 데이터(한국천문연구원 기준)가 2050년까지 있어요.")
            lm = c2.selectbox("월", range(1, 13), key=k("lm"))
            ld = c3.selectbox("일", range(1, 31), key=k("ld"))
            is_leap = st.checkbox("윤달", key=k("leap"))
        else:
            birth_date = st.date_input(f"{who}생년월일 ({SOLAR_MIN.year}~{SOLAR_MAX.year}년)", date(1990, 1, 1),
                                       min_value=SOLAR_MIN, max_value=SOLAR_MAX, key=k("birth_date"),
                                       help="범위 밖 날짜는 입력되지 않아요. 결과 위의 '계산 기준'을 꼭 확인해 주세요.")
            is_leap = False

        c1, c2 = st.columns(2)
        hour = c1.selectbox(f"{who}태어난 시", range(24), index=None, placeholder="선택하세요",
                            format_func=lambda h: f"{h:02d}시", key=k("hour"))
        minute = c2.selectbox("분", range(60), format_func=lambda m: f"{m:02d}분", key=k("minute"))
        time_unknown = st.checkbox("태어난 시간을 몰라요", key=k("time_unknown"))
        solar_correction = st.checkbox("진태양시 보정 (-30분)", key=k("solar_corr"),
                                       help="서울 기준 실제 태양 시각에 맞춰 일주·시주를 계산해요.")
        night_rat = st.checkbox("야자시 적용", key=k("night_rat"),
                                help="23시~24시 출생의 일주를 다음 날이 아닌 태어난 날로 봐요. 시주는 같아요.")

        if st.form_submit_button(submit_label, type="primary", width="stretch"):
            missing = []
            if gender is None:
                missing.append("성별을 골라 주세요.")
            if hour is None and not time_unknown:
                missing.append("태어난 시를 고르거나 '태어난 시간을 몰라요'를 체크해 주세요.")
            if missing:
                st.session_state.pop(state_key, None)  # 이전 결과가 새 입력의 결과처럼 보이지 않게
                st.warning(" ".join(missing), icon="✋")
                return
            st.session_state[state_key] = dict(
                name=name.strip(),
                gender=gender,
                # 음력은 (연, 월, 일) 정수로 넘긴다 — 음력 2월 30일은 양력 date로 만들 수 없음(REVIEW 🔴-1)
                birth_date=(int(ly), int(lm), int(ld)) if is_lunar else birth_date,
                birth_time=None if time_unknown else time(hour, minute),
                is_lunar=is_lunar,
                is_leap_month=is_leap,
                solar_time_offset_minutes=-30 if solar_correction else 0,
                night_rat=night_rat,
            )


def saju_from(params: dict):
    return calculate(
        params["birth_date"],
        params["birth_time"],
        is_lunar=params["is_lunar"],
        is_leap_month=params["is_leap_month"],
        solar_time_offset_minutes=params["solar_time_offset_minutes"],
        night_rat=params.get("night_rat", False),
    )


def basis_text(params: dict, s) -> str:
    """결과 위에 보여 줄 '계산 기준' — 입력이 무시되거나 바뀐 경우를 사용자가 알아챌 수 있게(REVIEW 🟠-1)."""
    when = f"{s.birth:%Y년 %m월 %d일}" + (f" {s.birth:%H:%M}" if s.time_known else " (시간 모름)")
    parts = [f"📅 **계산 기준: 양력 {when}**"]
    if params["is_lunar"]:
        y, m, d = params["birth_date"]
        parts.append(f"(입력: 음력 {y}년 {'윤' if params['is_leap_month'] else ''}{m}월 {d}일)")
    notes = []
    if s.clock_note:
        notes.append(f"🕰️ {s.clock_note} → {s.kst:%H:%M}")
    if params["solar_time_offset_minutes"]:
        notes.append("☀️ 진태양시 보정 -30분")
    if s.night_rat:
        notes.append("🌙 야자시 적용: 일주를 태어난 날로 계산")
    return " ".join(parts) + ("  \n" + " · ".join(notes) if notes else "")


# ── 입력 ──────────────────────────────────────────────────────

# 커스텀 CSS는 여기서 한 번만 주입한다
st.markdown(f"<style>{load_css()}</style>", unsafe_allow_html=True)
html(visuals.hero_html())
birth_form("", "birth_form", "내 사주 보기 🔮", "params")

DISCLAIMER = '<div class="sj-disclaimer">※ 재미로 보는 콘텐츠입니다. 중요한 결정은 스스로의 판단으로 내려 주세요.</div>'

params = st.session_state.get("params")
if not params:
    html(DISCLAIMER)
    st.stop()

try:
    saju = saju_from(params)
except ValueError as e:
    st.error(f"앗, 날짜를 다시 확인해 주세요. {e}")
    st.stop()

name = params["name"]
who = f"{name}님" if name else "당신"
counts = analysis.count_elements(saju)

st.write("")
st.info(basis_text(params, saju))
tab_me, tab_daewoon, tab_compat = st.tabs(["🔮 내 사주", "📈 대운 (10년 운)", "💞 궁합 보기"])

with tab_me:
    # ── 1. 띠 ─────────────────────────────────────────────────
    br = C["branches"][saju.year.branch.index]
    when = f"{saju.birth:%Y년 %m월 %d일}" + (f" {saju.birth:%H:%M}" if saju.time_known else " (시간 모름)")
    html(visuals.zodiac_html(br["emoji"], f"{eun_neun(who)} {br['title']}예요!", br["trait"],
                             f"양력 {when} · {saju.year.hangul}년생"))

    # ── 2. 사주팔자 ───────────────────────────────────────────
    st.subheader("📜 나의 사주팔자")
    st.caption("네 기둥, 여덟 글자예요. 위는 천간, 아래는 지지예요. 작은 글씨는 일간 기준 십신, 보라 테두리는 '나'(일간)예요.")
    html(visuals.pillar_cards_html(saju))
    if saju.boundary_ambiguous:
        st.warning("태어난 날에 절기가 바뀌어서, 태어난 시간에 따라 년주·월주가 달라질 수 있어요.")
    term_help("사주팔자", "천간", "지지", "십신", "절기")
    with st.expander("📖 내 사주에 있는 십신 풀이"):
        gods = {g for pair in analysis.ten_gods(saju) for g in pair if g and g != "일간"}
        for g, desc in C["glossary"]["ten_gods"].items():
            if g in gods:
                st.markdown(f"**{g}** — {desc}")

    # ── 3. 오행 ───────────────────────────────────────────────
    st.subheader("🌈 오행 밸런스")
    html(visuals.element_badges_html(counts))
    c1, c2 = st.columns(2, vertical_alignment="center")
    c1.plotly_chart(visuals.element_radar(counts), width="stretch", config={"displayModeBar": False})
    c1.caption("오행 레이더: " + ", ".join(f"{e} {counts[e]}개" for e in analysis.ELEMENTS))
    with c2:
        st.markdown(visuals.svg_img_tag(visuals.cycle_svg(counts), "오행 상생 상극 관계도"), unsafe_allow_html=True)
        st.caption("보라 실선 = 상생(도와줌) · 회색 점선 = 상극(눌러 줌) · 원 크기 = 글자 수")

    strong, weak = analysis.strongest_elements(saju), analysis.weakest_elements(saju)
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown(f"**💪 많은 기운: {', '.join(E[e]['emoji'] + ' ' + e for e in strong)}**")
        for e in strong:
            st.write(E[e]["many"])
    with c2, st.container(border=True):
        st.markdown(f"**🌱 부족한 기운: {', '.join(E[e]['emoji'] + ' ' + e for e in weak)}**")
        for e in weak:
            st.write(E[e]["lack"])

    st.markdown("**☯️ 음양 밸런스**")
    html(visuals.yin_yang_bar(analysis.count_yin_yang(saju)))
    term_help("오행", "상생", "상극", "음양")

    # ── 4. 일간 캐릭터 ────────────────────────────────────────
    st.subheader("🪞 나는 어떤 사람일까?")
    info = C["stems"][saju.day_master.index]
    html(visuals.me_card_html(info, saju.day_master.element))
    term_help("일간")

    # ── 5. 행운 아이템 ────────────────────────────────────────
    lucky = analysis.lucky_items(saju)
    le = E[lucky["element"]]
    st.subheader("🍀 나를 채워 주는 행운 아이템")
    st.caption(f"부족한 {le['emoji']} {lucky['element']}({le['name']}) 기운을 채워 주는 것들이에요.")
    html(visuals.lucky_html(lucky))
    st.write(f"🍽️ **음식** {lucky['food']}  ·  🎁 **아이템** {lucky['item']}  ·  🗓️ **계절** {lucky['season']}")

    # ── 6. 운세 ───────────────────────────────────────────────
    F = C["fortune"]
    daily = analysis.daily_fortune(saju)
    st.subheader(f"📅 오늘의 운세 ({daily.day:%m월 %d일})")
    st.markdown(f"**{daily.label}** · 오늘의 일진 {daily.pillar} · {daily.ten_god}의 날")
    html(visuals.fortune_html({k: daily.stars[k] for k in F["categories"]}, F["category_emoji"]))
    st.info(daily.message, icon="💌")

    yearly = analysis.yearly_fortune(saju)
    st.subheader(f"🎆 {yearly.year}년 {yearly.pillar.hangul}년의 운세")
    with st.container(border=True):
        st.markdown(f"**{yearly.title}** ({yearly.ten_god}의 해)")
        st.write(yearly.summary)

# ── 7. 대운 ───────────────────────────────────────────────────

with tab_daewoon:
    st.subheader("📈 대운 — 10년마다 바뀌는 큰 흐름")
    today = analysis.today_kst()
    age = today.year - saju.birth.year - ((today.month, today.day) < (saju.birth.month, saju.birth.day))
    dw = calculate_daewoon(saju, params["gender"], cover_age=age)  # 오래 산 경우 지금 나이까지 대운을 늘림
    st.caption(f"{'순행' if dw.forward else '역행'} 대운 · 만 {dw.start_age}세부터 시작 "
               f"({saju.year.stem.yin_yang}년생 {params['gender']}자 → {'다음' if dw.forward else '이전'} 절기까지 "
               f"{dw.days_to_term:.1f}일 ÷ 3)")
    if not saju.time_known:
        st.warning("태어난 시간을 몰라서 정오 기준으로 계산했어요. 대운 시작 나이가 조금 다를 수 있어요.")

    now = dw.current(age)
    if now:
        el = E[now.pillar.stem.element]
        with st.container(border=True):
            st.markdown(f"#### 지금은 {el['emoji']} {now.pillar} 대운 ({now.start_age}~{now.end_age}세)")
            st.markdown(f"**{now.title}** ({now.ten_god}) · 흐름 {stars(now.score)}")
            st.write(now.summary)
    elif age < dw.start_age:
        st.info(f"첫 대운은 만 {dw.start_age}세({saju.birth.year + dw.start_age}년)에 시작해요. "
                "그 전에는 월주의 기운으로 자라요.")

    st.plotly_chart(visuals.daewoon_chart(dw.periods, age), width="stretch", config={"displayModeBar": False})
    st.caption("막대 색 = 그 대운 천간의 오행 · 높이 = 흐름 점수(내게 부족한 기운이 오면 ↑, 이미 많은 기운이 오면 ↓) · "
               "보라 테두리 = 지금 대운  \n"
               + " → ".join(f"{p.start_age}세 {p.pillar.hangul}({p.score})" for p in dw.periods))

    with st.expander("📋 대운 전체 보기"):
        for p in dw.periods:
            mark = " 👈 지금" if now and p.order == now.order else ""
            st.markdown(f"**{p.start_age}~{p.end_age}세** ({p.start_year}년~) · {E[p.pillar.stem.element]['emoji']} "
                        f"{p.pillar} · {p.ten_god} · {stars(p.score)}{mark}  \n{p.title} — {p.summary}")
    term_help("대운")

# ── 8. 궁합 ───────────────────────────────────────────────────

with tab_compat:
    st.subheader("💞 두 사람 궁합 보기")
    st.caption("상대방의 생년월일을 넣으면 내 사주와 비교해 볼게요.")
    birth_form("p_", "partner_form", "궁합 보기 💞", "partner", who="상대방 ",
               gender_help="두 사람을 표시하는 데 쓰여요. 궁합 점수에는 영향을 주지 않아요.",
               default_gender="여" if params["gender"] == "남" else "남")

    partner = st.session_state.get("partner")
    if partner:
        try:
            other = saju_from(partner)
        except ValueError as e:
            st.error(f"앗, 상대방 날짜를 다시 확인해 주세요. {e}")
        else:
            me_name = name or "나"
            other_name = partner["name"] or "상대방"
            icon = {"남": "👨", "여": "👩"}
            result = compatibility(saju, other)

            def side(person: str, g_: str | None, s_) -> tuple[str, str, str]:
                info_ = C["stems"][s_.day_master.index]
                br_ = C["branches"][s_.year.branch.index]
                return (info_["emoji"], f"{icon.get(g_, '')} {person} ({g_ or '?'})",
                        f"{info_['nature']}({s_.day_master.hangul}{s_.day_master.element}) · {br_['emoji']} {br_['animal']}띠")

            st.write("")
            html(visuals.couple_html(side(me_name, params["gender"], saju), side(other_name, partner["gender"], other),
                                     result.grade["emoji"], result.grade["title"]))
            st.plotly_chart(visuals.compat_gauge(result.total), width="stretch", config={"displayModeBar": False})
            st.info(result.grade["message"], icon=result.grade["emoji"])

            for part in result.parts:
                with st.container(border=True):
                    st.markdown(f"**{part.name}** · {part.relation} — {part.score}/{part.max_score}점")
                    st.progress(part.score / part.max_score)
                    st.caption(part.message)

            c1, c2 = st.columns(2)
            for col, person, s_ in ((c1, me_name, saju), (c2, other_name, other)):
                with col.expander(f"{person}의 사주팔자"):
                    html(visuals.pillar_cards_html(s_))

            st.markdown("**🌈 두 사람의 오행 비교**")
            other_counts = analysis.count_elements(other)
            st.plotly_chart(visuals.element_compare_chart(counts, other_counts, me_name, other_name),
                            width="stretch", config={"displayModeBar": False})
            st.caption(" · ".join(f"{E[e]['emoji']} {e} {counts[e]}:{other_counts[e]}" for e in analysis.ELEMENTS)
                       + f"  ({me_name}:{other_name})")
            term_help("궁합")

# ── 9. 공유 · 다시 보기 ───────────────────────────────────────

st.divider()
c1, c2 = st.columns(2)
c1.download_button("📥 결과 카드 저장", card_png(saju, params), file_name="saju_card.png",
                   mime="image/png", width="stretch")
c2.button("🔄 다시 보기", on_click=reset, width="stretch")
html(DISCLAIMER)
