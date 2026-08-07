import os
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime

import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Colors — validated categorical palette (dataviz skill reference), fixed order.
CATEGORICAL = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
COLOR_INCOME = CATEGORICAL[0]
COLOR_EXPENSE = CATEGORICAL[7]
COLOR_TRANSFER = "#898781"
COLOR_BRAND = "#6366f1"  # indigo/periwinkle — single brand accent (nav, gauge, chrome)
COLOR_ACCENT = COLOR_BRAND
INK_PRIMARY = "#1e1b2e"
INK_MUTED = "#8b899e"
GRIDLINE = "#e3e1f5"
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_CRITICAL = "#d03b3b"
PAGE_BG = "#f4f3fb"
CARD_BG = "#ffffff"
SIDEBAR_BG = "#eeecfa"

ASSET_TYPE_LABEL = {"cash": "현금", "bank": "은행", "card": "카드"}
WEEKDAY_LABEL = ["월", "화", "수", "목", "금", "토", "일"]
NAV_PAGES = ["대시보드", "거래내역", "통계", "예산", "자산", "거래 추가"]

st.set_page_config(page_title="가계부 대시보드", layout="wide")

st.markdown(
    f"""
<style>
/* hide Streamlit chrome so it reads as an app, not a dev tool */
#MainMenu, header[data-testid="stHeader"], footer {{ visibility: hidden; height: 0; }}

.stApp {{ background: {PAGE_BG}; }}
.block-container {{
    max-width: 100%;
    padding-top: 1.5rem;
    padding-left: 2.5rem;
    padding-right: 2.5rem;
}}
@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    .stat-value {{ font-size: 20px; }}
}}

/* ── Sidebar nav ─────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: {SIDEBAR_BG};
    border-right: 1px solid {GRIDLINE};
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {{ gap: 2px; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
    padding: 10px 14px;
    border-radius: 8px;
    width: 100%;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{ background: #ffffff; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{ background: #ffffff; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {{
    color: {COLOR_BRAND}; font-weight: 700;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {{ display: none; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] p {{ font-size: 15px; font-weight: 600; color: {INK_PRIMARY}; }}
section[data-testid="stSidebar"] hr {{ border-color: {GRIDLINE}; }}

/* month nav row — keep it a single row even on mobile, where Streamlit
   normally stacks st.columns vertically below ~640px */
div[class*="st-key-month_nav"] [data-testid="stHorizontalBlock"] {{
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center;
}}
div[class*="st-key-month_nav"] [data-testid="stColumn"] {{
    width: unset !important;
    min-width: unset !important;
}}
div[class*="st-key-nav_"] button {{
    width: 32px; height: 32px; border-radius: 50%; padding: 0;
    font-size: 13px; line-height: 1; display:block; margin: 0 auto;
}}

/* panel headings inside grid cards */
.panel-title {{ font-size: 14px; font-weight: 700; color: {INK_PRIMARY}; margin-bottom: 10px; }}
.page-title {{ font-size: 22px; font-weight: 700; color: {INK_PRIMARY}; margin-bottom: 4px; }}

/* grid rows — make every card/panel in the same row match the tallest one.
   Streamlit nests columns several levels deep (stColumn > stVerticalBlock >
   [stLayoutWrapper > stVerticalBlock >] stElementContainer > ...), so every
   wrapper level in the chain needs to flex, not just the direct child. */
div[class*="st-key-kpi_row"] [data-testid="stHorizontalBlock"],
div[class*="st-key-panel_row"] [data-testid="stHorizontalBlock"] {{
    align-items: stretch;
}}
div[class*="st-key-kpi_row"] [data-testid="stColumn"],
div[class*="st-key-panel_row"] [data-testid="stColumn"] {{
    display: flex;
}}
div[class*="st-key-kpi_row"] [data-testid="stVerticalBlock"],
div[class*="st-key-kpi_row"] [data-testid="stLayoutWrapper"],
div[class*="st-key-kpi_row"] [data-testid="stElementContainer"],
div[class*="st-key-kpi_row"] [data-testid="stMarkdown"],
div[class*="st-key-kpi_row"] [data-testid="stMarkdownContainer"],
div[class*="st-key-panel_row"] [data-testid="stVerticalBlock"],
div[class*="st-key-panel_row"] [data-testid="stLayoutWrapper"],
div[class*="st-key-panel_row"] [data-testid="stElementContainer"],
div[class*="st-key-panel_row"] [data-testid="stMarkdown"],
div[class*="st-key-panel_row"] [data-testid="stMarkdownContainer"] {{
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
}}
div[class*="st-key-kpi_row"] .card,
div[class*="st-key-panel_row"] .card,
div[class*="st-key-kpi_row"] [class*="st-key-chart_panel"],
div[class*="st-key-panel_row"] [class*="st-key-chart_panel"] {{
    flex: 1 1 auto;
}}

/* chart panels — plain st.container(key=...) restyled to look like a card.
   (Not st.container(border=True): that renders as stVerticalBlockBorderWrapper
   in some Streamlit builds and stLayoutWrapper in others, and stLayoutWrapper
   is also used for plain non-bordered wrappers elsewhere — too ambiguous to
   target reliably. An explicit key is unambiguous.) */
div[class*="st-key-chart_panel"] {{
    background: {CARD_BG};
    border-radius: 14px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(11,11,11,0.06);
}}

.card {{
    background: {CARD_BG};
    border-radius: 14px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(11,11,11,0.06);
    margin-bottom: 12px;
    height: 100%;
}}
.stat-label {{ font-size: 13px; color: {INK_MUTED}; margin-bottom: 6px; }}
.stat-value {{ font-size: 24px; font-weight: 700; }}
.day-header {{
    display:flex; justify-content:space-between; align-items:baseline;
    padding: 12px 4px 6px 4px; font-weight:700; color:{INK_PRIMARY};
}}
.day-header .sub {{ font-size: 13px; font-weight:400; color:{INK_MUTED}; margin-left:4px; }}
.tx-row {{
    display:flex; justify-content:space-between; align-items:center;
    padding: 10px 4px; border-bottom: 1px solid {GRIDLINE};
}}
.tx-row:last-child {{ border-bottom: none; }}
.tx-title {{ font-size:14px; color:{INK_PRIMARY}; font-weight:500; }}
.tx-sub {{ font-size:12px; color:{INK_MUTED}; margin-top:2px; }}
.tx-amount {{ font-size:15px; font-weight:700; white-space:nowrap; }}
.cat-pill {{
    display:inline-block; padding:2px 9px; border-radius:999px;
    font-size:11px; font-weight:600; color:white; margin-right:6px;
}}
.legend-row {{
    display:flex; justify-content:space-between; align-items:center;
    padding:7px 0; font-size:13px;
}}
.legend-row.lg {{ padding: 9px 0; font-size: 14px; }}
.legend-dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:8px; }}
.legend-pct {{ color:{INK_MUTED}; font-size:12px; margin-left:6px; }}
.budget-name {{ font-size:13px; font-weight:600; color:{INK_PRIMARY}; }}
.budget-track {{ background:#eeece6; border-radius:8px; height:8px; overflow:hidden; margin-top:6px; }}
.budget-fill {{ height:8px; border-radius:8px; }}
.budget-numbers {{ display:flex; justify-content:space-between; font-size:11px; color:{INK_MUTED}; margin-top:4px; }}
.asset-row {{
    display:flex; justify-content:space-between; padding:8px 0;
    border-bottom:1px solid {GRIDLINE}; font-size:13px;
}}
.asset-total-row {{
    display:flex; justify-content:space-between; padding-top:10px; margin-top:4px;
    font-size:14px; font-weight:700; color:{INK_PRIMARY};
}}
.asset-group-title {{ font-size:12px; color:{INK_MUTED}; font-weight:700; margin: 12px 0 4px 0; }}
</style>
""",
    unsafe_allow_html=True,
)


def get_categories():
    return requests.get(f"{API_URL}/categories/").json()


def get_assets():
    return requests.get(f"{API_URL}/assets/").json()


def get_transactions():
    return requests.get(f"{API_URL}/transactions/").json()


def get_budgets():
    return requests.get(f"{API_URL}/budgets/").json()


def compute_current_balance(asset_id, opening_balance, transactions):
    balance = opening_balance or 0
    for t in transactions:
        if t["type"] == "income" and t["asset_id"] == asset_id:
            balance += t["amount"]
        elif t["type"] == "expense" and t["asset_id"] == asset_id:
            balance -= t["amount"]
        elif t["type"] == "transfer":
            if t["asset_id"] == asset_id:
                balance -= t["amount"]
            if t.get("to_asset_id") == asset_id:
                balance += t["amount"]
    return balance


def build_category_colors(categories):
    ordered = sorted(categories, key=lambda c: c["id"])
    return {c["id"]: CATEGORICAL[i % len(CATEGORICAL)] for i, c in enumerate(ordered)}


def month_bounds(year, month):
    start = datetime(year, month, 1)
    end = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
    return start, end


def filter_by_month(transactions, year, month):
    start, end = month_bounds(year, month)
    return [t for t in transactions if start <= datetime.fromisoformat(t["date"]) <= end]


def shift_month(year, month, delta):
    month += delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def stat_card_html(label, value_text, value_color=INK_PRIMARY):
    return (
        f'<div class="card"><div class="stat-label">{label}</div>'
        f'<div class="stat-value" style="color:{value_color}">{value_text}</div></div>'
    )


def build_trend_figure(transactions, sel_year, sel_month, height):
    months = [shift_month(sel_year, sel_month, -i) for i in range(5, -1, -1)]
    income_series, expense_series, labels = [], [], []
    for yy, mm in months:
        mtx = filter_by_month(transactions, yy, mm)
        income_series.append(sum(t["amount"] for t in mtx if t["type"] == "income"))
        expense_series.append(sum(t["amount"] for t in mtx if t["type"] == "expense"))
        labels.append(f"{mm}월")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels, y=income_series, name="수입", mode="lines+markers",
            line=dict(color=COLOR_INCOME, width=2), marker=dict(size=7),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels, y=expense_series, name="지출", mode="lines+markers",
            line=dict(color=COLOR_EXPENSE, width=2), marker=dict(size=7),
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(gridcolor=GRIDLINE, zeroline=False),
        xaxis=dict(showgrid=False),
    )
    return fig


def build_donut_figure(items, colors, total_amount, height):
    names = [n for n, _ in items]
    values = [v for _, v in items]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=names, values=values, hole=0.65,
                marker=dict(colors=colors, line=dict(color="#ffffff", width=2)),
                textinfo="none", sort=False,
            )
        ]
    )
    fig.update_layout(
        showlegend=False,
        height=height,
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        annotations=[
            dict(text=f"{total_amount:,}원", x=0.5, y=0.5, font=dict(size=15, color=INK_PRIMARY), showarrow=False)
        ],
    )
    return fig


categories = get_categories()
assets = get_assets()
transactions = get_transactions()
budgets = get_budgets()

category_colors = build_category_colors(categories)
category_by_id = {c["id"]: c for c in categories}
asset_by_id = {a["id"]: a for a in assets}
category_options = {c["name"]: c["id"] for c in categories}
asset_options = {a["name"]: a["id"] for a in assets}

if "sel_year" not in st.session_state:
    today = date.today()
    st.session_state.sel_year = today.year
    st.session_state.sel_month = today.month

# ── Sidebar: logo, nav, period control ─────────────────────────────
with st.sidebar:
    st.markdown("## 📒 가계부")
    page = st.radio("nav", NAV_PAGES, label_visibility="collapsed", key="nav_page")
    st.markdown("---")
    st.markdown('<div style="font-size:12px; color:#898781; font-weight:700;">기간</div>', unsafe_allow_html=True)
    with st.container(key="month_nav"):
        nav_left, nav_mid, nav_right = st.columns([1, 3, 1])
        with nav_left:
            with st.container(key="nav_prev"):
                if st.button("◀", key="prev_month"):
                    st.session_state.sel_year, st.session_state.sel_month = shift_month(
                        st.session_state.sel_year, st.session_state.sel_month, -1
                    )
                    st.rerun()
        with nav_mid:
            st.markdown(
                f'<div style="text-align:center; font-size:14px; font-weight:700; padding-top:7px;">'
                f"{st.session_state.sel_year}.{st.session_state.sel_month:02d}</div>",
                unsafe_allow_html=True,
            )
        with nav_right:
            with st.container(key="nav_next"):
                if st.button("▶", key="next_month"):
                    st.session_state.sel_year, st.session_state.sel_month = shift_month(
                        st.session_state.sel_year, st.session_state.sel_month, 1
                    )
                    st.rerun()

month_tx = filter_by_month(transactions, st.session_state.sel_year, st.session_state.sel_month)
income_sum = sum(t["amount"] for t in month_tx if t["type"] == "income")
expense_sum = sum(t["amount"] for t in month_tx if t["type"] == "expense")

month_budgets = [
    b for b in budgets
    if b["year"] == st.session_state.sel_year and b["month"] == st.session_state.sel_month
]
spent_by_cat = defaultdict(int)
for t in month_tx:
    if t["type"] == "expense":
        spent_by_cat[t["category_id"]] += t["amount"]
total_budget = sum(b["amount"] for b in month_budgets)
total_spent_budgeted = sum(spent_by_cat.get(b["category_id"], 0) for b in month_budgets)
budget_pct = (total_spent_budgeted / total_budget * 100) if total_budget else 0

month_label = f'{st.session_state.sel_year}년 {st.session_state.sel_month}월'
st.markdown(f'<div class="page-title">{page}</div>', unsafe_allow_html=True)
st.markdown(f'<div style="color:{INK_MUTED}; margin-bottom:16px;">{month_label}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
if page == "대시보드":
    gauge_color = STATUS_CRITICAL if budget_pct >= 100 else STATUS_WARNING if budget_pct >= 80 else COLOR_ACCENT

    kpi_row = st.container(key="kpi_row")
    k1, k2, k3, k4 = kpi_row.columns(4)
    with k1:
        st.markdown(stat_card_html("이번달 수입", f"{income_sum:,}원", COLOR_INCOME), unsafe_allow_html=True)
    with k2:
        st.markdown(stat_card_html("이번달 지출", f"{expense_sum:,}원", COLOR_EXPENSE), unsafe_allow_html=True)
    with k3:
        st.markdown(stat_card_html("합계", f"{income_sum - expense_sum:,}원"), unsafe_allow_html=True)
    with k4:
        with st.container(key="chart_panel_gauge"):
            gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=min(budget_pct, 100),
                    number={"suffix": "%", "font": {"size": 20, "color": INK_PRIMARY}},
                    gauge={
                        "axis": {"range": [0, 100], "visible": False},
                        "bar": {"color": gauge_color, "thickness": 0.35},
                        "bgcolor": "#eeece6",
                        "borderwidth": 0,
                    },
                )
            )
            gauge.update_layout(
                height=100,
                margin=dict(t=28, b=0, l=10, r=45),
                paper_bgcolor="white",
                title={"text": "예산 사용률", "font": {"size": 13, "color": INK_MUTED}},
            )
            st.plotly_chart(gauge, use_container_width=True, config={"displayModeBar": False})

    panel_row = st.container(key="panel_row")
    col_assets, col_donut, col_budget = panel_row.columns(3)

    with col_assets:
        display_assets = [
            {**a, "current": compute_current_balance(a["id"], a["balance"], transactions)} for a in assets
        ]
        rows_html = ""
        for a in sorted(display_assets, key=lambda a: a["id"]):
            rows_html += f'<div class="asset-row"><span>{a["name"]}</span><span>{a["current"]:,}원</span></div>'
        total_assets = sum(a["current"] for a in display_assets)
        rows_html += f'<div class="asset-total-row"><span>총자산</span><span>{total_assets:,}원</span></div>'
        st.markdown(
            f'<div class="card"><div class="panel-title">자산 현황</div>{rows_html}</div>'
            if display_assets
            else '<div class="card"><div class="panel-title">자산 현황</div>등록된 자산이 없습니다.</div>',
            unsafe_allow_html=True,
        )

    with col_donut:
        with st.container(key="chart_panel_donut1"):
            st.markdown('<div class="panel-title">카테고리별 지출</div>', unsafe_allow_html=True)
            totals = defaultdict(int)
            for t in month_tx:
                if t["type"] == "expense":
                    totals[t["category_id"]] += t["amount"]
            if totals:
                items_raw = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
                colors = [category_colors.get(cid, INK_MUTED) for cid, _ in items_raw]
                total_amount = sum(v for _, v in items_raw)
                items = [(category_by_id.get(cid, {}).get("name", "미분류"), v) for cid, v in items_raw]
                st.plotly_chart(
                    build_donut_figure(items, colors, total_amount, 180),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
                legend_html = ""
                for (name, amount), color in list(zip(items, colors))[:5]:
                    pct = amount / total_amount * 100
                    legend_html += (
                        '<div class="legend-row"><span>'
                        f'<span class="legend-dot" style="background:{color}"></span>'
                        f'{name}<span class="legend-pct">{pct:.0f}%</span></span>'
                        f"<span>{amount:,}원</span></div>"
                    )
                st.markdown(legend_html, unsafe_allow_html=True)
            else:
                st.info("이번 달 지출 내역이 없습니다.")

    with col_budget:
        if not month_budgets:
            st.markdown(
                '<div class="card"><div class="panel-title">예산 진행</div>예산이 설정된 카테고리가 없습니다.</div>',
                unsafe_allow_html=True,
            )
        else:
            rows_html = ""
            for b in sorted(month_budgets, key=lambda b: b["id"])[:4]:
                cat_name = category_by_id.get(b["category_id"], {}).get("name", "?")
                spent = spent_by_cat.get(b["category_id"], 0)
                budget = b["amount"]
                pct = (spent / budget * 100) if budget else 0
                bar_color = (
                    STATUS_CRITICAL if pct >= 100 else STATUS_WARNING if pct >= 80
                    else category_colors.get(b["category_id"], STATUS_GOOD)
                )
                width = min(pct, 100)
                rows_html += (
                    '<div style="margin-bottom:12px;">'
                    '<div style="display:flex; justify-content:space-between;">'
                    f'<span class="budget-name">{cat_name}</span>'
                    f'<span class="budget-name">{pct:.0f}%</span></div>'
                    f'<div class="budget-track"><div class="budget-fill" '
                    f'style="width:{width}%; background:{bar_color};"></div></div>'
                    f'<div class="budget-numbers"><span>{spent:,}원</span>'
                    f'<span>/ {budget:,}원</span></div></div>'
                )
            st.markdown(
                f'<div class="card"><div class="panel-title">예산 진행</div>{rows_html}</div>',
                unsafe_allow_html=True,
            )

    with st.container(key="chart_panel_trend1"):
        st.markdown('<div class="panel-title">최근 6개월 수입/지출 추이</div>', unsafe_allow_html=True)
        st.plotly_chart(
            build_trend_figure(transactions, st.session_state.sel_year, st.session_state.sel_month, 240),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    recent = sorted(month_tx, key=lambda t: t["date"], reverse=True)[:8]
    rows_html = ""
    for t in recent:
        cat = category_by_id.get(t["category_id"])
        cat_name = cat["name"] if cat else ("이체" if t["type"] == "transfer" else "")
        asset = asset_by_id.get(t["asset_id"])
        asset_name = asset["name"] if asset else ""
        amt_color, sign = (
            (COLOR_EXPENSE, "-") if t["type"] == "expense"
            else (COLOR_INCOME, "+") if t["type"] == "income"
            else (COLOR_TRANSFER, "")
        )
        day_label = datetime.fromisoformat(t["date"]).strftime("%m.%d")
        rows_html += (
            '<div class="tx-row"><div>'
            f'<div class="tx-title">{t["title"]}</div>'
            f'<div class="tx-sub">{day_label} · {cat_name} · {asset_name}</div></div>'
            f'<div class="tx-amount" style="color:{amt_color}">{sign}{t["amount"]:,}원</div>'
            "</div>"
        )
    st.markdown(
        f'<div class="card"><div class="panel-title">최근 거래</div>{rows_html or "이번 달 거래 내역이 없습니다."}</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════
elif page == "거래내역":
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(stat_card_html("수입", f"{income_sum:,}원", COLOR_INCOME), unsafe_allow_html=True)
    with c2:
        st.markdown(stat_card_html("지출", f"{expense_sum:,}원", COLOR_EXPENSE), unsafe_allow_html=True)
    with c3:
        st.markdown(stat_card_html("합계", f"{income_sum - expense_sum:,}원"), unsafe_allow_html=True)

    if month_tx:
        by_day = defaultdict(list)
        for t in sorted(month_tx, key=lambda t: t["date"], reverse=True):
            by_day[t["date"][:10]].append(t)

        for day, txs in by_day.items():
            day_expense = sum(t["amount"] for t in txs if t["type"] == "expense")
            d_obj = datetime.fromisoformat(day)
            weekday = WEEKDAY_LABEL[d_obj.weekday()]

            rows_html = ""
            for t in txs:
                cat = category_by_id.get(t["category_id"])
                cat_name = cat["name"] if cat else ""
                cat_color = category_colors.get(t["category_id"], INK_MUTED)
                asset = asset_by_id.get(t["asset_id"])
                asset_name = asset["name"] if asset else ""
                amt_color, sign = (
                    (COLOR_EXPENSE, "-") if t["type"] == "expense"
                    else (COLOR_INCOME, "+") if t["type"] == "income"
                    else (COLOR_TRANSFER, "")
                )
                if t["type"] == "transfer":
                    pill_label, pill_color = "이체", COLOR_TRANSFER
                else:
                    pill_label, pill_color = cat_name, cat_color
                pill = (
                    f'<span class="cat-pill" style="background:{pill_color}">{pill_label}</span>'
                    if pill_label else ""
                )
                sub_parts = [p for p in [asset_name, t.get("memo")] if p]
                sub = " · ".join(sub_parts)
                rows_html += (
                    '<div class="tx-row"><div>'
                    f'<div class="tx-title">{pill}{t["title"]}</div>'
                    f'<div class="tx-sub">{sub}</div></div>'
                    f'<div class="tx-amount" style="color:{amt_color}">{sign}{t["amount"]:,}원</div>'
                    "</div>"
                )

            st.markdown(
                f'<div class="day-header"><span>{d_obj.day}일<span class="sub">({weekday})</span></span>'
                f'<span style="color:{COLOR_EXPENSE}">{day_expense:,}원</span></div>'
                f'<div class="card">{rows_html}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("이번 달 거래 내역이 없습니다.")

# ══════════════════════════════════════════════════════════════════
elif page == "통계":
    stat_type_label = st.radio("구분", ["지출", "수입"], horizontal=True, label_visibility="collapsed")
    target_type = "expense" if stat_type_label == "지출" else "income"

    totals = defaultdict(int)
    for t in month_tx:
        if t["type"] == target_type:
            totals[t["category_id"]] += t["amount"]

    col_chart, col_legend = st.columns([1, 1])
    if totals:
        items_raw = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        colors = [category_colors.get(cid, INK_MUTED) for cid, _ in items_raw]
        total_amount = sum(v for _, v in items_raw)
        items = [(category_by_id.get(cid, {}).get("name", "미분류"), v) for cid, v in items_raw]
        with col_chart:
            with st.container(key="chart_panel_donut2"):
                st.plotly_chart(
                    build_donut_figure(items, colors, total_amount, 280),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
        with col_legend:
            legend_html = ""
            for (name, amount), color in zip(items, colors):
                pct = amount / total_amount * 100
                legend_html += (
                    '<div class="legend-row lg"><span>'
                    f'<span class="legend-dot" style="background:{color}"></span>'
                    f'{name}<span class="legend-pct">{pct:.0f}%</span></span>'
                    f"<span>{amount:,}원</span></div>"
                )
            st.markdown(f'<div class="card">{legend_html}</div>', unsafe_allow_html=True)
    else:
        st.info(f"이번 달 {stat_type_label} 내역이 없습니다.")

    with st.container(key="chart_panel_trend2"):
        st.markdown('<div class="panel-title">최근 6개월 추이</div>', unsafe_allow_html=True)
        st.plotly_chart(
            build_trend_figure(transactions, st.session_state.sel_year, st.session_state.sel_month, 300),
            use_container_width=True,
            config={"displayModeBar": False},
        )

# ══════════════════════════════════════════════════════════════════
elif page == "예산":
    if not month_budgets:
        st.info("이번 달에 설정된 예산이 없습니다. `POST /budgets/`로 카테고리별 예산을 등록해보세요.")
    else:
        remaining = total_budget - total_spent_budgeted
        st.markdown(
            stat_card_html("남은 예산", f"{remaining:,}원", STATUS_GOOD if remaining >= 0 else STATUS_CRITICAL),
            unsafe_allow_html=True,
        )
        rows_html = ""
        for b in sorted(month_budgets, key=lambda b: b["id"]):
            cat_name = category_by_id.get(b["category_id"], {}).get("name", "?")
            spent = spent_by_cat.get(b["category_id"], 0)
            budget = b["amount"]
            pct = (spent / budget * 100) if budget else 0
            bar_color = (
                STATUS_CRITICAL if pct >= 100 else STATUS_WARNING if pct >= 80
                else category_colors.get(b["category_id"], STATUS_GOOD)
            )
            width = min(pct, 100)
            rows_html += (
                '<div style="margin-bottom:16px;">'
                '<div style="display:flex; justify-content:space-between;">'
                f'<span class="budget-name">{cat_name}</span>'
                f'<span class="budget-name">{pct:.0f}%</span></div>'
                f'<div class="budget-track"><div class="budget-fill" '
                f'style="width:{width}%; background:{bar_color};"></div></div>'
                f'<div class="budget-numbers"><span>{spent:,}원 사용</span>'
                f'<span>예산 {budget:,}원</span></div></div>'
            )
        st.markdown(f'<div class="card">{rows_html}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
elif page == "자산":
    if assets:
        display_assets = [
            {**a, "current": compute_current_balance(a["id"], a["balance"], transactions)} for a in assets
        ]
        total = sum(a["current"] for a in display_assets)
        st.markdown(stat_card_html("총자산", f"{total:,}원", COLOR_INCOME), unsafe_allow_html=True)

        groups = defaultdict(list)
        for a in display_assets:
            groups[a["type"]].append(a)

        rows_html = ""
        for type_key in ["cash", "bank", "card"]:
            if type_key not in groups:
                continue
            rows_html += f'<div class="asset-group-title">{ASSET_TYPE_LABEL.get(type_key, type_key)}</div>'
            for a in groups[type_key]:
                rows_html += f'<div class="asset-row"><span>{a["name"]}</span><span>{a["current"]:,}원</span></div>'
        st.markdown(f'<div class="card">{rows_html}</div>', unsafe_allow_html=True)
    else:
        st.info("등록된 자산이 없습니다.")

# ══════════════════════════════════════════════════════════════════
elif page == "거래 추가":
    with st.form("add_transaction"):
        t_date = st.date_input("날짜", value=date.today())
        title = st.text_input("항목명")
        amount = st.number_input("금액", min_value=0, step=100)
        t_type = st.selectbox("구분", ["expense", "income", "transfer"])
        category_name = st.selectbox("카테고리", list(category_options.keys()) or ["(없음)"])
        asset_name = st.selectbox("결제수단 / 보내는 계좌", list(asset_options.keys()) or ["(없음)"])
        to_asset_name = st.selectbox(
            "받는 계좌 (이체일 때만)", ["(해당없음)"] + list(asset_options.keys())
        )
        memo = st.text_input("메모")
        submitted = st.form_submit_button("저장")
        if submitted:
            payload = {
                "date": datetime.combine(t_date, datetime.min.time()).isoformat(),
                "title": title,
                "amount": int(amount),
                "type": t_type,
                "category_id": category_options.get(category_name),
                "asset_id": asset_options.get(asset_name),
                "to_asset_id": asset_options.get(to_asset_name) if t_type == "transfer" else None,
                "source": "manual",
                "memo": memo,
            }
            r = requests.post(f"{API_URL}/transactions/", json=payload)
            if r.ok:
                st.success("저장되었습니다.")
                st.rerun()
            else:
                st.error(r.text)
