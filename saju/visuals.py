"""차트·SVG·HTML 카드·결과 카드 PNG 생성. Streamlit에 의존하지 않는다."""

from __future__ import annotations

import base64
import io
import math
from html import escape
from pathlib import Path

import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFont

from . import content
from .analysis import ELEMENTS, count_elements, count_yin_yang, lucky_items, strongest_elements, ten_gods, weakest_elements
from .pillars import Saju

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
PILLAR_LABELS = ["시주", "일주", "월주", "년주"]
PILLAR_HINTS = ["태어난 시간", "태어난 날 (나)", "태어난 달", "태어난 해"]


def _el(e: str) -> dict:
    return content.elements()[e]


# ── 오행 차트 ──────────────────────────────────────────────────

def element_radar(counts: dict[str, int]) -> go.Figure:
    labels = [f"{_el(e)['emoji']} {e}({_el(e)['hanja']})" for e in ELEMENTS]
    r = [counts[e] for e in ELEMENTS]
    fig = go.Figure(
        go.Scatterpolar(
            r=r + r[:1],
            theta=labels + labels[:1],
            fill="toself",
            fillcolor="rgba(124, 92, 255, 0.25)",
            line=dict(color="#7C5CFF", width=2),
            marker=dict(size=12, color=[_el(e)["color"] for e in ELEMENTS] + [_el(ELEMENTS[0])["color"]],
                        line=dict(color=[_el(e)["border"] for e in ELEMENTS] + [_el(ELEMENTS[0])["border"]], width=2)),
            hovertemplate="%{theta}: %{r}개<extra></extra>",
        )
    )
    top = max(4, max(r))
    fig.update_layout(
        polar=dict(bgcolor="rgba(124, 92, 255, 0.06)", radialaxis=dict(range=[0, top], dtick=1, showticklabels=True),
                   angularaxis=dict(direction="clockwise")),
        showlegend=False,
        margin=dict(l=70, r=70, t=30, b=30),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ── 상생·상극 오각형 SVG ────────────────────────────────────────

def cycle_svg(counts: dict[str, int], size: int = 320) -> str:
    """오행 오각형. 상생=바깥 실선 화살표, 상극=안쪽 점선 별 모양. 원 크기 = 글자 수."""
    cx = cy = size / 2
    R = size * 0.34
    pts = []
    for i in range(5):
        a = math.radians(-90 + 72 * i)
        pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    radius = [18 + 5 * counts[e] for e in ELEMENTS]

    def edge(i: int, j: int) -> tuple[float, float, float, float]:
        (x1, y1), (x2, y2) = pts[i], pts[j]
        d = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / d, (y2 - y1) / d
        return x1 + ux * (radius[i] + 3), y1 + uy * (radius[i] + 3), x2 - ux * (radius[j] + 6), y2 - uy * (radius[j] + 6)

    parts = [
        f'<svg viewBox="0 0 {size} {size}" width="100%" style="max-width:{size}px" role="img" '
        'aria-label="오행 상생 상극 관계도" xmlns="http://www.w3.org/2000/svg">',
        "<defs>"
        '<marker id="arrG" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#7C5CFF"/></marker>'
        '<marker id="arrK" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#9E9E9E"/></marker>'
        "</defs>",
    ]
    for i in range(5):  # 상극: i → i+2
        x1, y1, x2, y2 = edge(i, (i + 2) % 5)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#9E9E9E" '
                     'stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#arrK)"/>')
    for i in range(5):  # 상생: i → i+1
        x1, y1, x2, y2 = edge(i, (i + 1) % 5)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#7C5CFF" '
                     'stroke-width="2.5" marker-end="url(#arrG)"/>')
    for i, e in enumerate(ELEMENTS):
        x, y = pts[i]
        el = _el(e)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius[i]}" fill="{el["color"]}" '
                     f'stroke="{el["border"]}" stroke-width="2"/>')
        parts.append(f'<text x="{x:.1f}" y="{y + 6:.1f}" text-anchor="middle" font-size="18">{el["emoji"]}</text>')
        ly = y - radius[i] - 8 if y < cy else y + radius[i] + 18
        parts.append(f'<text x="{x:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="13" font-weight="bold" '
                     f'fill="#444">{e}({el["hanja"]}) {counts[e]}개</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_img_tag(svg: str, alt: str) -> str:
    """SVG를 data URI <img>로 감싼다 (st.html/markdown의 SVG 필터링을 피하려고).

    글자색이 고정이라 다크 테마에서도 읽히도록 흰 카드(.sj-diagram) 위에 올린다.
    """
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<div class="sj-diagram"><img src="data:image/svg+xml;base64,{b64}" alt="{escape(alt)}" '
            'style="width:100%;max-width:320px;display:block;margin:auto"></div>')


# ── 음양 게이지 ────────────────────────────────────────────────

def yin_yang_bar(counts: dict[str, int]) -> str:
    total = counts["양"] + counts["음"]
    yang = round(counts["양"] / total * 100)
    return (
        '<div style="display:flex;align-items:center;gap:8px;font-size:15px;font-weight:600">'
        f'<span>☀️ 양 {counts["양"]}</span>'
        '<div style="flex:1;height:18px;border-radius:9px;overflow:hidden;display:flex;'
        'border:1px solid rgba(128,128,128,.4)" role="img" '
        f'aria-label="양 {counts["양"]}개, 음 {counts["음"]}개">'
        f'<div style="width:{yang}%;background:linear-gradient(90deg,#FFD180,#FFB74D)"></div>'
        f'<div style="width:{100 - yang}%;background:linear-gradient(90deg,#7986CB,#3F51B5)"></div>'
        "</div>"
        f'<span>{counts["음"]} 음 🌙</span></div>'
    )


# ── 화면용 HTML 조각 (스타일은 assets/style.css) ────────────────

def hero_html() -> str:
    return ('<div class="sj-hero"><div class="sj-moon">🔮</div><h1>사주냥</h1>'
            '<p>생년월일과 태어난 시간으로 보는, 그림으로 쉽게 푸는 내 사주 ✨</p></div>')


def zodiac_html(emoji: str, title: str, trait: str, meta: str) -> str:
    return (f'<div class="sj-zodiac sj-fade"><div class="sj-big" aria-hidden="true">{emoji}</div>'
            f'<div class="sj-bubble"><div class="sj-title">{escape(title)}</div><div>{escape(trait)}</div>'
            f'<div class="sj-meta">{escape(meta)}</div></div></div>')


def _cell(ch, god: str | None, is_me: bool = False) -> str:
    el = _el(ch.element)
    return (
        f'<div class="sj-cell{" sj-me" if is_me else ""}" '
        f'style="background:{el["color"]};color:{el["text_color"]};border-color:{el["border"]}" '
        f'aria-label="{ch.hangul}, {ch.element}({el["name"]}) 기운{", " + god if god else ""}">'
        f'<div class="sj-god">{escape(god or "")}</div>'
        f'<div class="sj-hanja">{ch.hanja}</div>'
        f'<div class="sj-sub">{ch.hangul} · {el["emoji"]} {ch.element}</div></div>'
    )


def pillar_cards_html(saju: Saju) -> str:
    """사주팔자 4기둥 × 2줄 카드. 오행 색 + 오행 이름을 함께 표시(색만으로 구분하지 않음)."""
    gods = ten_gods(saju)
    cols = []
    for i, (label, hint, p, (g_stem, g_branch)) in enumerate(
            zip(PILLAR_LABELS, PILLAR_HINTS, saju.pillars, gods, strict=True)):
        if p is None:
            cells = ['<div class="sj-cell sj-empty">❔<br>시간 모름</div>'] * 2
        else:
            cells = [_cell(p.stem, g_stem, is_me=(i == 1)), _cell(p.branch, g_branch)]
        cols.append(f'<div class="sj-col"><div class="sj-col-head">{label}</div><div class="sj-col-hint">{hint}</div>'
                    + "".join(cells) + "</div>")
    return '<div class="sj-pillars sj-fade">' + "".join(cols) + "</div>"


def element_badges_html(counts: dict[str, int]) -> str:
    badges = []
    for e in ELEMENTS:
        el = _el(e)
        badges.append(f'<span class="sj-badge" style="background:{el["color"]};color:{el["text_color"]};'
                      f'border-color:{el["border"]}">{el["emoji"]} {e}({el["name"]}) {counts[e]}</span>')
    return '<div class="sj-badges">' + "".join(badges) + "</div>"


def me_card_html(info: dict, element: str) -> str:
    el = _el(element)
    return (
        '<div class="sj-card sj-fade"><div class="sj-me-card">'
        f'<div class="sj-big" aria-hidden="true">{info["emoji"]}</div><div>'
        f'<div class="sj-nature">{escape(info["nature"])}</div>'
        f'<div style="opacity:.75;font-size:.9rem">일간 {info["hangul"]}{element}({info["hanja"]}{el["hanja"]}) · '
        f'{el["emoji"]} {el["keyword"]}</div>'
        f'<div style="margin-top:6px">{escape(info["summary"])}</div></div></div>'
        f'<p style="margin:12px 0 10px">{escape(info["personality"])}</p>'
        '<div class="sj-pros-cons">'
        f'<div class="sj-pros"><b>👍 장점</b>{escape(info["strengths"])}</div>'
        f'<div class="sj-cons"><b>💡 이렇게 해 보세요</b>{escape(info["cautions"])}</div>'
        "</div></div>"
    )


def lucky_html(lucky: dict) -> str:
    items = [("🎨", "행운의 색", lucky["color"]), ("🔢", "행운의 숫자", ", ".join(map(str, lucky["numbers"]))),
             ("🧭", "행운의 방향", lucky["direction"])]
    return '<div class="sj-lucky sj-fade">' + "".join(
        f'<div><div class="sj-ico">{ico}</div><div class="sj-label">{label}</div><div class="sj-value">{escape(v)}</div></div>'
        for ico, label, v in items) + "</div>"


def stars_html(n: int) -> str:
    return (f'<span class="sj-stars" role="img" aria-label="별 5개 중 {n}개">{"★" * n}'
            f'<span class="sj-off">{"★" * (5 - n)}</span></span>')


def fortune_html(stars: dict[str, int], emojis: dict[str, str]) -> str:
    return '<div class="sj-fortune sj-fade">' + "".join(
        f'<div><div class="sj-ico">{emojis[k]}</div><div class="sj-label">{k}</div>{stars_html(v)}</div>'
        for k, v in stars.items()) + "</div>"


def couple_html(left: tuple[str, str, str], right: tuple[str, str, str], grade_emoji: str, grade_title: str) -> str:
    """left/right = (캐릭터 이모지, 이름 줄, 설명 줄)."""
    def side(p: tuple[str, str, str]) -> str:
        return (f'<div><div class="sj-big" aria-hidden="true">{p[0]}</div><b>{escape(p[1])}</b>'
                f'<div style="font-size:.85rem;opacity:.75">{escape(p[2])}</div></div>')

    return (f'<div class="sj-card sj-fade"><div class="sj-couple">{side(left)}'
            f'<div class="sj-heart" aria-hidden="true">💗</div>{side(right)}</div>'
            f'<div class="sj-grade">{grade_emoji} {escape(grade_title)}</div></div>')


# ── 결과 카드 PNG ──────────────────────────────────────────────

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf")), size)


def _hanja_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / "NotoSansKR-Hanja-Bold.ttf"), size)


def png_safe_name(name: str) -> str:
    """PNG용 이름: 나눔고딕에 있는 글자(영문·숫자·기본 기호·한글)만 남긴다.

    이모지·한자·악센트 문자는 글꼴에 없어 네모(□)로 그려지므로 뺀다. 화면 표시에는 영향 없음.
    """
    kept = [ch for ch in name if (" " <= ch <= "~") or ("가" <= ch <= "힣") or ("\u3131" <= ch <= "\u318e")]
    return " ".join("".join(kept).split())


def _fit_font(draw: ImageDraw.ImageDraw, text: str, width: int, size: int, min_size: int) -> ImageFont.FreeTypeFont:
    """text가 width 안에 들어가도록 굵은 글꼴 크기를 줄인다 (긴 이름 대응, 최대 20자)."""
    while size > min_size and draw.textlength(text, font=_font(size, True)) > width:
        size -= 2
    return _font(size, True)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split(" "):
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _night_header(img: Image.Image, height: int) -> None:
    """화면 헤더와 같은 밤하늘 그라데이션 + 별."""
    w = img.width
    top, mid, bot = (0x1B, 0x16, 0x40), (0x3B, 0x2C, 0x85), (0x8E, 0x6B, 0xFF)
    # 작은 그라데이션을 계산한 뒤 확대한다 (픽셀 단위 루프는 너무 느림)
    gw, gh = 40, 8
    small = Image.new("RGB", (gw, gh))
    px = small.load()
    for x in range(gw):
        for y in range(gh):
            t = x / (gw - 1) * 0.65 + y / (gh - 1) * 0.35
            a, b, tt = (top, mid, t / 0.55) if t < 0.55 else (mid, bot, (t - 0.55) / 0.45)
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * tt) for i in range(3))
    img.paste(small.resize((w, height), Image.BILINEAR), (0, 0))
    d = ImageDraw.Draw(img)
    for sx, sy, r, c in [(0.12, 0.1, 2, "#FFFFFF"), (0.3, 0.08, 1.5, "#FFFFFF"), (0.46, 0.13, 2, "#FFE9A8"),
                         (0.63, 0.55, 1.5, "#FFFFFF"), (0.78, 0.28, 2, "#FFFFFF"), (0.9, 0.75, 1.5, "#FFE9A8"),
                         (0.7, 0.85, 1.5, "#FFFFFF"), (0.95, 0.18, 2, "#FFFFFF")]:
        d.ellipse((sx * w - r, sy * height - r, sx * w + r, sy * height + r), fill=c)


def result_card_png(saju: Saju, name: str = "") -> bytes:
    """공유용 결과 카드 (PNG bytes). 화면과 같은 밤하늘 헤더 + 파스텔 오행 색.

    Pillow는 컬러 이모지를 그리지 못하므로 색과 글자로만 표현한다.
    """
    W, H, M = 800, 1040, 48
    BG, FG, SUB, ACCENT, SOFT = "#FCFAFF", "#2B2340", "#6B6480", "#7C5CFF", "#F1ECFF"
    img = Image.new("RGB", (W, H), BG)
    _night_header(img, 150)
    d = ImageDraw.Draw(img)

    safe = png_safe_name(name)
    title = f"{safe}님의 사주" if safe else "나의 사주"
    d.text((M, 40), title, font=_fit_font(d, title, W - 2 * M, 40, 22), fill="#FFFFFF")
    when = f"{saju.birth:%Y년 %m월 %d일}" + (f" {saju.birth:%H:%M}" if saju.time_known else " (시간 모름)")
    d.text((M, 96), f"양력 {when} · {content.branches()[saju.year.branch.index]['title']}", font=_font(20), fill="#E6DFFF")

    # 4기둥
    top, cw, ch, gap = 180, 160, 120, 16
    left = (W - (cw * 4 + gap * 3)) // 2
    for i, (label, p) in enumerate(zip(PILLAR_LABELS, saju.pillars, strict=True)):
        x = left + i * (cw + gap)
        d.text((x + cw / 2, top), label, font=_font(20, True), fill=FG, anchor="mt")
        for row in range(2):
            y = top + 34 + row * (ch + 10)
            if p is None:
                d.rounded_rectangle((x, y, x + cw, y + ch), 18, outline="#B9B0D6", width=2)
                d.text((x + cw / 2, y + ch / 2), "?", font=_font(40, True), fill=SUB, anchor="mm")
                continue
            c = p.stem if row == 0 else p.branch
            el = _el(c.element)
            if i == 1 and row == 0:  # 일간 강조
                d.rounded_rectangle((x - 5, y - 5, x + cw + 5, y + ch + 5), 22, outline=ACCENT, width=3)
            d.rounded_rectangle((x, y, x + cw, y + ch), 18, fill=el["color"], outline=el["border"], width=2)
            d.text((x + cw / 2, y + 50), c.hanja, font=_hanja_font(58), fill=el["text_color"], anchor="mm")
            d.text((x + cw / 2, y + ch - 20), f"{c.hangul} · {c.element}", font=_font(18, True),
                   fill=el["text_color"], anchor="mm")

    # 오행 막대
    counts = count_elements(saju)
    y = top + 34 + 2 * ch + 10 + 36
    d.text((M, y), "오행 분포", font=_font(24, True), fill=FG)
    y += 44
    bar_w = W - 2 * M - 150
    total = max(1, sum(counts.values()))
    for e in ELEMENTS:
        el = _el(e)
        d.text((M, y + 13), f"{e}({el['name']})", font=_font(18), fill=FG, anchor="lm")
        d.rounded_rectangle((M + 90, y, M + 90 + bar_w, y + 26), 13, fill=SOFT)
        if counts[e]:
            d.rounded_rectangle((M + 90, y, M + 90 + max(26, bar_w * counts[e] / total), y + 26), 13,
                                fill=el["color"], outline=el["border"], width=2)
        d.text((W - M, y + 13), f"{counts[e]}개", font=_font(18, True), fill=FG, anchor="rm")
        y += 38

    yy = count_yin_yang(saju)
    d.text((M, y + 6), f"음양: 양 {yy['양']} · 음 {yy['음']}    많은 기운: {', '.join(strongest_elements(saju))}"
           f"    부족한 기운: {', '.join(weakest_elements(saju))}", font=_font(18), fill=SUB)

    # 일간
    y += 50
    info = content.stems()[saju.day_master.index]
    d.text((M, y), f"나는 '{info['nature']}' 같은 사람 ({info['hangul']}{saju.day_master.element})",
           font=_font(26, True), fill=ACCENT)
    y += 42
    for line in _wrap(d, info["personality"], _font(19), W - 2 * M)[:3]:
        d.text((M, y), line, font=_font(19), fill=FG)
        y += 30

    # 행운
    lucky = lucky_items(saju)
    y += 14
    d.rounded_rectangle((M, y, W - M, y + 70), 18, fill=SOFT, outline="#E2DAFF", width=2)
    numbers = ", ".join(map(str, lucky["numbers"]))
    d.text((M + 20, y + 35), f"행운의 색 {lucky['color']}  ·  숫자 {numbers}  ·  방향 {lucky['direction']}",
           font=_font(20, True), fill=FG, anchor="lm")

    d.text((W / 2, H - 36), "사주냥 · 재미로 보는 콘텐츠입니다", font=_font(16), fill=SUB, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── 대운 타임라인 ──────────────────────────────────────────────

def daewoon_chart(periods: list, current_age: int | None = None) -> go.Figure:
    """대운 흐름 그래프. 막대 색 = 대운 천간의 오행, 높이 = 흐름 점수(1~5)."""
    x = [f"{p.start_age}~{p.end_age}세" for p in periods]
    now = [current_age is not None and p.start_age <= current_age <= p.end_age for p in periods]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x,
        y=[p.score for p in periods],
        marker=dict(
            color=[_el(p.pillar.stem.element)["color"] for p in periods],
            line=dict(color=["#7C5CFF" if n else _el(p.pillar.stem.element)["border"] for p, n in zip(periods, now, strict=True)],
                      width=[4 if n else 1.5 for n in now]),
        ),
        text=[f"{p.pillar.hanja}<br>{p.pillar.hangul}" for p in periods],
        textposition="outside",
        customdata=[[p.start_year, p.ten_god, p.title] for p in periods],
        hovertemplate=("%{x} (%{customdata[0]}년~)<br>%{text}<br>%{customdata[1]} · %{customdata[2]}"
                       "<br>흐름 %{y}/5<extra></extra>"),
    ))
    fig.add_trace(go.Scatter(x=x, y=[p.score for p in periods], mode="lines", line=dict(color="#7C5CFF", width=2, dash="dot"),
                             hoverinfo="skip"))
    fig.update_layout(
        showlegend=False, height=340, margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(range=[0, 6.3], dtick=1, showticklabels=False, showgrid=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ── 궁합 ──────────────────────────────────────────────────────

def compat_gauge(total: int) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=total,
        number=dict(suffix="점"),
        gauge=dict(
            axis=dict(range=[0, 100]),
            bar=dict(color="#FF6B9A"),
            steps=[dict(range=[0, 60], color="#F3EEFF"), dict(range=[60, 80], color="#E6DCFF"),
                   dict(range=[80, 100], color="#D4C4FF")],
        ),
    ))
    fig.update_layout(height=250, margin=dict(l=30, r=30, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def element_compare_chart(a_counts: dict[str, int], b_counts: dict[str, int], a_name: str, b_name: str) -> go.Figure:
    labels = [f"{_el(e)['emoji']} {e}" for e in ELEMENTS]
    fig = go.Figure([
        # 이름은 사용자가 입력한 값이라 Plotly 의사 HTML(<b>, <a href> …)로 해석되지 않게 이스케이프
        go.Bar(name=escape(a_name), x=labels, y=[a_counts[e] for e in ELEMENTS], marker_color="#7C5CFF"),
        go.Bar(name=escape(b_name), x=labels, y=[b_counts[e] for e in ELEMENTS], marker_color="#FF6B9A"),
    ])
    fig.update_layout(barmode="group", height=280, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis=dict(dtick=1), legend=dict(orientation="h", y=1.12),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig
