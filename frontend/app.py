"""
EmployeeFlow - Streamlit frontend.

Talks to the FastAPI backend (see API_BASE_URL). Run from the project root:

    python -m streamlit run frontend/app.py

Set EMPLOYEEFLOW_API_URL to point at a backend that is not on localhost.
"""

from __future__ import annotations

import html
import json
import os
import re

import altair as alt
import httpx
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURATION
# ==========================================

API_BASE_URL = os.getenv(
    "EMPLOYEEFLOW_API_URL", "http://127.0.0.1:8000/api/v1"
)

st.set_page_config(
    page_title="EmployeeFlow",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Palette (kept in sync with the CSS variables below)
INK = "#16212B"
BRAND = "#0E6F68"
TONE_HEX = {
    "ok": "#2E7D52",
    "warn": "#B7791F",
    "bad": "#B63D2E",
    "review": "#6B4FBB",
    "info": "#2B6CB0",
    "mute": "#8896A2",
}

# ==========================================
# STYLES
# ==========================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
    --ink: #16212B;
    --muted: #5B6B79;
    --line: #E1E7EA;
    --page: #F5F7F6;
    --panel: #FFFFFF;
    --brand: #0E6F68;
    --side: #0D2B2A;
    --ok: #2E7D52;
    --warn: #B7791F;
    --bad: #B63D2E;
    --review: #6B4FBB;
    --info: #2B6CB0;
    --mute: #8896A2;
}

/* ---------- Base ---------- */
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea,
.stApp button, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    font-family: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.stApp { background: var(--page); color: var(--ink); }
#MainMenu, footer, .stDeployButton, [data-testid="stAppDeployButton"] { visibility: hidden; }
.block-container, [data-testid="stMainBlockContainer"] {
    padding: 2.2rem 2.5rem 4rem;
    max-width: 1280px;
}
.stApp label p { font-size: 0.85rem; font-weight: 500; }
div[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
}
div[data-testid="stAlert"] { border-radius: 8px; }

/* Tabs */
div[data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { padding: 10px 14px; height: auto; }
button[data-baseweb="tab"] p { font-weight: 500; }
div[data-baseweb="tab-highlight"] { background-color: var(--brand); }

/* Scrollable select dropdowns */
div[data-baseweb="popover"] [role="listbox"] {
    max-height: 280px !important;
    overflow-y: auto !important;
    overscroll-behavior: contain;
}
div[data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar { width: 7px; }
div[data-baseweb="popover"] [role="listbox"]::-webkit-scrollbar-thumb {
    background: #9AA7B1;
    border-radius: 10px;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] { background: var(--side); border-right: none; }
section[data-testid="stSidebar"] * { color: #C9DAD8; }
section[data-testid="stSidebar"] .ef-brand {
    display: flex; align-items: center; gap: 12px; padding: 6px 4px 22px;
}
section[data-testid="stSidebar"] .ef-mark {
    width: 36px; height: 36px; border-radius: 9px; background: #1FA396;
    display: grid; place-items: center; font-weight: 600; color: #FFFFFF;
    letter-spacing: 0.02em;
}
section[data-testid="stSidebar"] .ef-brand b { color: #FFFFFF; font-size: 1.05rem; font-weight: 600; }
section[data-testid="stSidebar"] .ef-brand span.sub { display: block; font-size: 0.78rem; color: #8FB0AC; }
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 2px; }
section[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 9px 12px; border-radius: 8px; width: 100%; margin: 0; cursor: pointer;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(255,255,255,0.07); }
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: #14504C; }
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: #FFFFFF; font-weight: 600; }
section[data-testid="stSidebar"] .ef-status { font-size: 0.82rem; padding: 4px 4px 0; }
section[data-testid="stSidebar"] .ef-status i {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px;
}
section[data-testid="stSidebar"] button {
    background: transparent; border: 1px solid rgba(255,255,255,0.25); border-radius: 8px;
}
section[data-testid="stSidebar"] button:hover { border-color: #FFFFFF; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12); }

/* ---------- Page header & sections ---------- */
.ef-head { margin-bottom: 22px; }
.ef-head .t { font-size: 1.8rem; font-weight: 600; letter-spacing: -0.015em; line-height: 1.2; color: var(--ink); }
.ef-head .c { margin-top: 6px; color: var(--muted); max-width: 70ch; font-size: 0.98rem; }
.ef-sec { margin: 30px 0 12px; }
.ef-sec .t { font-size: 1.08rem; font-weight: 600; color: var(--ink); }
.ef-sec .c { color: var(--muted); font-size: 0.88rem; margin-top: 2px; }

/* ---------- Stat strip ---------- */
.ef-strip {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 1px; background: var(--line); border: 1px solid var(--line);
    border-radius: 10px; overflow: hidden; margin: 4px 0 6px;
}
.ef-strip .cell { background: var(--panel); padding: 16px 20px; }
.ef-strip .k { font-size: 0.82rem; color: var(--muted); }
.ef-strip .v {
    font-size: 1.85rem; font-weight: 600; line-height: 1.25; margin-top: 2px;
    font-variant-numeric: tabular-nums; color: var(--ink);
}
.ef-strip .s { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
.t-ok { color: var(--ok) !important; } .t-warn { color: var(--warn) !important; }
.t-bad { color: var(--bad) !important; } .t-review { color: var(--review) !important; }
.t-info { color: var(--info) !important; } .t-mute { color: var(--mute) !important; }

/* ---------- Segmented status bars ---------- */
.ef-panel {
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: 18px 20px; height: 100%;
}
.ef-panel .head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 14px; }
.ef-panel .head .n { font-weight: 600; }
.ef-panel .head .m { color: var(--muted); font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.ef-seg { display: flex; gap: 2px; height: 12px; border-radius: 6px; overflow: hidden; background: #E9EEF0; }
.ef-seg span { flex: none; display: block; height: 100%; }
.ef-legend { display: flex; flex-wrap: wrap; gap: 6px 20px; margin-top: 14px; font-size: 0.85rem; color: var(--muted); }
.ef-legend b { color: var(--ink); font-variant-numeric: tabular-nums; margin-left: 2px; }
.ef-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.b-ok { background: var(--ok); } .b-warn { background: var(--warn); } .b-bad { background: var(--bad); }
.b-review { background: var(--review); } .b-info { background: var(--info); } .b-mute { background: #B9C4CC; }

/* ---------- Status pills ---------- */
.ef-pill {
    display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem;
    font-weight: 500; line-height: 1.6; white-space: nowrap;
}
.ef-pill.ok { color: #1E6B42; background: rgba(46,125,82,0.13); }
.ef-pill.warn { color: #8A5A0F; background: rgba(183,121,31,0.16); }
.ef-pill.bad { color: #9C2F22; background: rgba(182,61,46,0.13); }
.ef-pill.review { color: #5338A6; background: rgba(107,79,187,0.13); }
.ef-pill.info { color: #23558C; background: rgba(43,108,176,0.13); }
.ef-pill.mute { color: #4F5E6B; background: rgba(136,150,162,0.2); }

/* ---------- Detail grid, notes, steps ---------- */
.ef-kv {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px 28px;
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px;
}
.ef-kv .k { font-size: 0.78rem; color: var(--muted); }
.ef-kv .v { margin-top: 2px; font-weight: 500; word-break: break-word; }
.ef-note {
    border-left: 3px solid var(--brand); background: var(--panel); padding: 12px 16px;
    border-radius: 0 8px 8px 0; margin: 12px 0; max-width: 90ch;
}
.ef-note .k { font-size: 0.78rem; color: var(--muted); margin-bottom: 2px; }
.ef-step {
    background: var(--panel); border: 1px solid var(--line); border-left-width: 4px;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
}
.ef-step.s-ok { border-left-color: var(--ok); } .ef-step.s-bad { border-left-color: var(--bad); }
.ef-step.s-mute { border-left-color: var(--mute); } .ef-step.s-warn { border-left-color: var(--warn); }
.ef-step .top { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.ef-step .body { margin-top: 6px; color: var(--ink); }
.ef-step .meta { margin-top: 4px; font-size: 0.8rem; color: var(--muted); }
.ef-empty {
    background: var(--panel); border: 1px dashed #B9C4CC; border-radius: 10px;
    padding: 22px 24px; max-width: 760px;
}
.ef-empty b { font-size: 1.05rem; }
.ef-empty p { color: var(--muted); margin: 6px 0 10px; }
.ef-empty pre { background: #0D2B2A; color: #D5E9E6; padding: 12px 14px; border-radius: 8px; overflow-x: auto; margin: 0; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# ==========================================
# API CONNECTION
# ==========================================


@st.cache_data(ttl=20, show_spinner=False)
def _fetch(endpoint: str, params: tuple):
    """Cached GET. Raises on failure so errors are never cached."""
    response = httpx.get(
        f"{API_BASE_URL}{endpoint}",
        params=dict(params) if params else None,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _error_detail(exc: httpx.HTTPStatusError):
    try:
        data = exc.response.json()
        return data.get("detail", data) if isinstance(data, dict) else data
    except ValueError:
        return exc.response.text


def get_api_data(endpoint, params=None):
    """GET from the EmployeeFlow API. Returns None (and shows an error) on failure."""
    key = tuple(sorted((params or {}).items()))
    try:
        return _fetch(endpoint, key)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            st.warning("Nothing was found for that ID. Check it and try again.")
        else:
            st.error(
                f"API error ({exc.response.status_code}): {_error_detail(exc)}"
            )
    except httpx.HTTPError as exc:
        st.error(f"Could not reach the EmployeeFlow API: {exc}")
    return None


def post_api_data(endpoint, payload):
    """Send POST requests to the EmployeeFlow API."""
    try:
        response = httpx.post(
            f"{API_BASE_URL}{endpoint}", json=payload, timeout=10
        )
        response.raise_for_status()
        _fetch.clear()  # data changed, drop cached reads
        return response.json()
    except httpx.HTTPStatusError as exc:
        st.error(
            f"API error ({exc.response.status_code}): {_error_detail(exc)}"
        )
    except httpx.RequestError as exc:
        st.error(f"Could not reach the EmployeeFlow API: {exc}")
    return None


@st.cache_data(ttl=10, show_spinner=False)
def api_online() -> bool:
    try:
        return httpx.get(f"{API_BASE_URL}/health", timeout=3).is_success
    except httpx.HTTPError:
        return False


# ==========================================
# FORMATTING HELPERS
# ==========================================

TONE_BY_STATUS = {
    "approved": "ok", "paid": "ok", "active": "ok",
    "pending": "warn", "pending_approval": "warn", "medium": "warn",
    "submitted": "info", "on_leave": "info", "low": "info",
    "needs_review": "review",
    "rejected": "bad", "terminated": "bad", "high": "bad",
    "draft": "mute", "cancelled": "mute", "skipped": "mute",
}
DOT = {
    "ok": "🟢", "warn": "🟡", "bad": "🔴",
    "review": "🟣", "info": "🔵", "mute": "⚪",
}


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def label_of(value) -> str:
    text = str(value).replace("_", " ")
    text = text[:1].upper() + text[1:]
    return re.sub(r"\bId\b", "ID", re.sub(r"\bHr\b", "HR", text))


def tone_of(status) -> str:
    return TONE_BY_STATUS.get(str(status).lower(), "mute")


def badge(status) -> str:
    return f'<span class="ef-pill {tone_of(status)}">{esc(label_of(status))}</span>'


def dot_label(status) -> str:
    return f"{DOT[tone_of(status)]} {label_of(status)}"


def money(minor, currency) -> str:
    if minor is None:
        return "-"
    value = minor / 100
    if currency == "INR":
        return f"₹{value:,.2f}"
    return f"{currency} {value:,.2f}"


def norm_id(value: str) -> str:
    return value.strip().upper()


def _stretch(fn, *args, **kwargs):
    """Full-width widgets across old and new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except (TypeError, st.errors.StreamlitAPIException):
        return fn(*args, use_container_width=True, **kwargs)


# ==========================================
# UI COMPONENTS
# ==========================================


def page_header(title: str, caption: str):
    st.markdown(
        f'<div class="ef-head"><div class="t">{esc(title)}</div>'
        f'<div class="c">{esc(caption)}</div></div>',
        unsafe_allow_html=True,
    )


def section(title: str, caption: str = ""):
    cap = f'<div class="c">{esc(caption)}</div>' if caption else ""
    st.markdown(
        f'<div class="ef-sec"><div class="t">{esc(title)}</div>{cap}</div>',
        unsafe_allow_html=True,
    )


def stat_strip(items):
    """items: (label, value, tone=None, sub='') tuples rendered as one divided panel."""
    cells = []
    for item in items:
        label, value = item[0], item[1]
        tone = item[2] if len(item) > 2 else None
        sub = item[3] if len(item) > 3 else ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = f"{value:,}"
        cls = f" t-{tone}" if tone else ""
        sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ""
        cells.append(
            f'<div class="cell"><div class="k">{esc(label)}</div>'
            f'<div class="v{cls}">{esc(value)}</div>{sub_html}</div>'
        )
    st.markdown(
        f'<div class="ef-strip">{"".join(cells)}</div>', unsafe_allow_html=True
    )


def segment_panel(title: str, total: int, segments, total_label="total") -> str:
    """Proportional status bar. segments: (label, value, tone)."""
    base = total or sum(v for _, v, _ in segments)
    bar = "".join(
        f'<span class="b-{tone}" style="width:{value / base * 100:.2f}%" '
        f'title="{esc(label)}: {value:,}"></span>'
        for label, value, tone in segments
        if value > 0 and base
    )
    legend = "".join(
        f'<span><i class="b-{tone}"></i>{esc(label)} <b>{value:,}</b></span>'
        for label, value, tone in segments
        if value > 0 or tone != "mute"
    )
    return (
        f'<div class="ef-panel"><div class="head"><span class="n">{esc(title)}</span>'
        f'<span class="m">{base:,} {esc(total_label)}</span></div>'
        f'<div class="ef-seg">{bar}</div><div class="ef-legend">{legend}</div></div>'
    )


def kv_grid(pairs):
    """pairs: (label, html_value). Values must already be escaped."""
    cells = "".join(
        f'<div><div class="k">{esc(k)}</div><div class="v">{v}</div></div>'
        for k, v in pairs
    )
    st.markdown(f'<div class="ef-kv">{cells}</div>', unsafe_allow_html=True)


def note(label: str, text) -> None:
    st.markdown(
        f'<div class="ef-note"><div class="k">{esc(label)}</div>{esc(text) or "-"}</div>',
        unsafe_allow_html=True,
    )


def show_table(
    df: pd.DataFrame, export_name: str | None = None, scope: str = "", **kwargs
):
    _stretch(st.dataframe, df, hide_index=True, **kwargs)
    if export_name:
        st.download_button(
            "Export CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name=export_name,
            mime="text/csv",
            key=f"export_{scope}_{export_name}",
        )


def offline_panel():
    st.markdown(
        '<div class="ef-empty"><b>Can\'t reach the EmployeeFlow API</b>'
        f"<p>This app expects the backend at <code>{esc(API_BASE_URL)}</code>. "
        "Start it from the project root, then use Refresh data in the sidebar.</p>"
        "<pre>python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000</pre></div>",
        unsafe_allow_html=True,
    )


def pager(key: str, total_pages: int) -> int:
    """Page picker that stays valid when filters shrink the result set."""
    if total_pages <= 1:
        return 1
    if st.session_state.get(key, 1) > total_pages:
        st.session_state[key] = total_pages
    col, info = st.columns([1, 4])
    with col:
        page = st.number_input(
            "Page", min_value=1, max_value=total_pages, value=1, step=1, key=key
        )
    info.markdown(
        f'<div style="padding-top:2rem;color:#5B6B79">of {total_pages} pages</div>',
        unsafe_allow_html=True,
    )
    return int(page)


def load_page(endpoint, params, first, key):
    """Return the page selected in the pager (page 1 reuses the first fetch)."""
    page = pager(key, max(int(first.get("total_pages") or 1), 1))
    if page == 1:
        return first
    return get_api_data(endpoint, params={**params, "page": page})


# ---------- Charts ----------


def _render_chart(chart):
    chart = chart.configure_view(stroke=None).configure_axis(
        grid=False, labelFont="IBM Plex Sans", labelColor=INK
    )
    try:
        st.altair_chart(chart, theme=None, width="stretch")
    except (TypeError, st.errors.StreamlitAPIException):
        st.altair_chart(chart, theme=None, use_container_width=True)


def hbar(df, category, value, color=BRAND, color_map=None, fmt=",.0f"):
    """Sorted horizontal bar chart with direct value labels."""
    data = df[[category, value]].rename(columns={category: "label", value: "value"})
    height = max(110, 34 * len(data) + 16)
    encode_color = {}
    mark_kwargs = {"cornerRadiusEnd": 3, "size": 18}
    if color_map:
        encode_color["color"] = alt.Color(
            "label:N",
            scale=alt.Scale(
                domain=list(color_map.keys()), range=list(color_map.values())
            ),
            legend=None,
        )
    else:
        mark_kwargs["color"] = color
    base = alt.Chart(data).encode(
        y=alt.Y(
            "label:N", sort="-x", title=None,
            axis=alt.Axis(ticks=False, domain=False, labelLimit=240, labelFontSize=12),
        ),
        x=alt.X("value:Q", title=None, axis=None),
    )
    bars = base.mark_bar(**mark_kwargs).encode(
        tooltip=[alt.Tooltip("label:N", title="Name"), alt.Tooltip("value:Q", format=fmt, title="Value")],
        **encode_color,
    )
    labels = base.mark_text(align="left", dx=5, fontSize=12, color=INK).encode(
        text=alt.Text("value:Q", format=fmt)
    )
    _render_chart((bars + labels).properties(height=height))


# ==========================================
# SIDEBAR
# ==========================================

NAV = [
    "Dashboard",
    "Employees",
    "Leave Management",
    "Expense Management",
    "Approval Center",
    "Exception Management",
    "Analytics",
]


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="ef-brand"><div class="ef-mark">EF</div>'
            '<div><b>EmployeeFlow</b><span class="sub">Leave and expense operations</span></div></div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigation", NAV, key="main_navigation", label_visibility="collapsed"
        )
        st.divider()
        online = api_online()
        st.markdown(
            f'<div class="ef-status"><i style="background:{"#4CC38A" if online else "#E5604D"}"></i>'
            f'{"API connected" if online else "API unreachable"}</div>',
            unsafe_allow_html=True,
        )
        if _stretch(st.button, "Refresh data", key="refresh_data"):
            _fetch.clear()
            api_online.clear()
            st.rerun()
    return page


# ==========================================
# DASHBOARD
# ==========================================


def page_dashboard():
    page_header(
        "Dashboard",
        "Where leave, expense and reimbursement work stands right now.",
    )

    data = get_api_data("/dashboard/summary")
    if not data:
        offline_panel()
        return

    section("Needs attention", "Open items waiting on a decision or a payment.")
    items = [
        ("Leave awaiting decision", data["pending_leave_requests"], "warn"),
        ("Leave needing review", data["leave_requests_needs_review"], "review"),
        ("Expenses awaiting decision", data["pending_expense_claims"], "warn"),
        ("Expenses needing review", data["expense_claims_needs_review"], "review"),
        ("Reimbursements to pay", data["pending_reimbursements"], "info"),
    ]
    stat_strip([(l, v, t if v else None) for l, v, t in items])

    section("Pipeline", "How every request and claim is split by status.")

    def status_segments(total, approved, pending, review, rejected):
        other = max(total - approved - pending - review - rejected, 0)
        return [
            ("Approved", approved, "ok"),
            ("Pending", pending, "warn"),
            ("Needs review", review, "review"),
            ("Rejected", rejected, "bad"),
            ("Other", other, "mute"),
        ]

    left, right = st.columns(2)
    left.markdown(
        segment_panel(
            "Leave requests",
            data["total_leave_requests"],
            status_segments(
                data["total_leave_requests"],
                data["approved_leave_requests"],
                data["pending_leave_requests"],
                data["leave_requests_needs_review"],
                data["rejected_leave_requests"],
            ),
        ),
        unsafe_allow_html=True,
    )
    right.markdown(
        segment_panel(
            "Expense claims",
            data["total_expense_claims"],
            status_segments(
                data["total_expense_claims"],
                data["approved_expense_claims"],
                data["pending_expense_claims"],
                data["expense_claims_needs_review"],
                data["rejected_expense_claims"],
            ),
        ),
        unsafe_allow_html=True,
    )

    st.write("")
    left, right = st.columns(2)
    total_emp = data["total_employees"]
    active = data["active_employees"]
    left.markdown(
        segment_panel(
            "Workforce",
            total_emp,
            [("Active", active, "ok"), ("Not active", max(total_emp - active, 0), "mute")],
            "employees",
        ),
        unsafe_allow_html=True,
    )
    total_re = data["total_reimbursements"]
    paid = data["paid_reimbursements"]
    pending_re = data["pending_reimbursements"]
    right.markdown(
        segment_panel(
            "Reimbursements",
            total_re,
            [
                ("Paid", paid, "ok"),
                ("Pending payment", pending_re, "warn"),
                ("Other", max(total_re - paid - pending_re, 0), "mute"),
            ],
        ),
        unsafe_allow_html=True,
    )


# ==========================================
# EMPLOYEES
# ==========================================


def page_employees():
    page_header(
        "Employee Directory",
        "Search, browse and filter your organization's employees.",
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        search = c1.text_input(
            "Search employee", placeholder="Name, ID or email", key="emp_search"
        )
        country = c2.selectbox("Country", ["All", "IN", "US"], key="emp_country")
        department = c3.text_input(
            "Department", placeholder="Enter department", key="emp_department"
        )
        c1, c2, c3 = st.columns(3)
        employment_status = c1.selectbox(
            "Employment status",
            ["All", "active", "on_leave", "terminated"],
            format_func=lambda v: v if v == "All" else label_of(v),
            key="emp_status",
        )
        system_role = c2.selectbox(
            "System role",
            [
                "All", "employee", "manager", "hr_admin",
                "finance_admin", "operations_analyst", "system_admin",
            ],
            format_func=lambda v: v if v == "All" else label_of(v),
            key="emp_role",
        )
        page_size = c3.selectbox(
            "Records per page", [10, 20, 50, 100], index=1, key="emp_page_size"
        )

    params = {"page_size": page_size}
    if search.strip():
        params["search"] = search.strip()
    if country != "All":
        params["country"] = country
    if department.strip():
        params["department"] = department.strip()
    if employment_status != "All":
        params["employment_status"] = employment_status
    if system_role != "All":
        params["system_role"] = system_role

    first = get_api_data("/employees", params={**params, "page": 1})
    if first is None:
        return

    st.write("")
    stat_strip([
        ("Matching employees", first["total"]),
        ("Pages", first["total_pages"], None, f"{page_size} per page"),
    ])

    result = load_page("/employees", params, first, "emp_page")
    if not result:
        return

    employees = result["items"]
    if not employees:
        st.info("No employees match these filters. Try clearing one.")
        return

    rows = [
        {
            "Employee ID": e["employee_id"],
            "Name": f'{e["first_name"]} {e["last_name"]}',
            "Email": e["email"],
            "Department": e["department"],
            "Job title": e["job_title"],
            "Country": e["country_code"],
            "Manager ID": e["manager_employee_id"] or "-",
            "Status": dot_label(e["employment_status"]),
            "Role": label_of(e["system_role"]),
        }
        for e in employees
    ]
    section("Employee records")
    show_table(pd.DataFrame(rows), export_name="employees.csv")
    st.caption(
        f"Showing {len(employees)} employees on page {result['page']} "
        f"of {result['total_pages']}."
    )


# ==========================================
# SHARED APPROVAL TABLE
# ==========================================


def approvals_table(approvals, empty_message, export_name, scope=""):
    if not approvals:
        st.info(empty_message)
        return
    rows = [
        {
            "Step": a["step_order"],
            "Approver": a["approver_employee_id"],
            "Status": dot_label(a["status"]),
            "Decision reason": a["decision_reason"] or "-",
            "Assigned": a["assigned_at"],
            "Decided": a["decided_at"] or "-",
        }
        for a in approvals
    ]
    show_table(pd.DataFrame(rows), export_name=export_name, scope=scope)


# ==========================================
# LEAVE MANAGEMENT
# ==========================================


def render_leave_balances():
    employee_id = st.text_input(
        "Employee ID", placeholder="Example: EMP-000001", key="leave_employee_id"
    )
    if not employee_id.strip():
        st.info("Enter an employee ID to see their leave balances.")
        return

    balances = get_api_data(f"/leave/balances/{norm_id(employee_id)}")
    if balances is None:
        return
    if not balances:
        st.info("No leave balances found for this employee.")
        return

    rows = []
    for b in balances:
        entitled = (b["opening_days"] or 0) + (b["accrued_days"] or 0)
        used = (b["approved_used_days"] or 0) + (b["pending_reserved_days"] or 0)
        rows.append({
            "Policy": b["leave_policy_id"],
            "Year": b["period_year"],
            "Opening": b["opening_days"],
            "Accrued": b["accrued_days"],
            "Used": b["approved_used_days"],
            "Pending": b["pending_reserved_days"],
            "Available": b["available_days"],
            "Usage": min(used / entitled * 100, 100) if entitled else 0,
        })
    st.success(f"Leave balances for {norm_id(employee_id)}")
    show_table(
        pd.DataFrame(rows),
        export_name=f"leave_balances_{norm_id(employee_id)}.csv",
        column_config={
            "Usage": st.column_config.ProgressColumn(
                "Usage", min_value=0, max_value=100, format="%.0f%%",
                help="Approved plus pending days as a share of opening plus accrued days",
            )
        },
    )


def render_leave_requests():
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        filter_employee = c1.text_input(
            "Employee ID", placeholder="EMP-000001", key="leave_filter_employee"
        )
        filter_status = c2.selectbox(
            "Request status",
            [
                "All", "draft", "submitted", "pending_approval",
                "needs_review", "approved", "rejected", "cancelled",
            ],
            format_func=lambda v: v if v == "All" else label_of(v),
            key="leave_status_filter",
        )
        page_size = c3.selectbox(
            "Records per page", [10, 20, 50, 100], index=1, key="leave_page_size"
        )

    params = {"page_size": page_size}
    if filter_employee.strip():
        params["employee_id"] = norm_id(filter_employee)
    if filter_status != "All":
        params["status"] = filter_status

    first = get_api_data("/leave/requests", params={**params, "page": 1})
    if first is None:
        return

    st.write("")
    stat_strip([
        ("Matching leave requests", first["total"]),
        ("Pages", first["total_pages"], None, f"{page_size} per page"),
    ])

    result = load_page("/leave/requests", params, first, "leave_request_page")
    if not result:
        return
    requests = result["items"]
    if not requests:
        st.info("No leave requests match these filters.")
        return

    rows = [
        {
            "Request ID": r["leave_request_id"],
            "Employee ID": r["employee_id"],
            "Policy": r["leave_policy_id"],
            "Start": r["start_date"],
            "End": r["end_date"],
            "Business days": r["business_days"],
            "Status": dot_label(r["status"]),
        }
        for r in requests
    ]
    section("Leave requests")
    show_table(pd.DataFrame(rows), export_name="leave_requests.csv")
    st.caption(f"Page {result['page']} of {result['total_pages']}")

    section("Request details", "Pick a request to see its fields and approval trail.")
    selected = st.selectbox(
        "Leave request",
        [r["leave_request_id"] for r in requests],
        key="selected_leave_request",
    )
    if not selected:
        return

    detail = get_api_data(f"/leave/requests/{selected}")
    if detail:
        pairs = []
        for key, value in detail.items():
            if key.lower().endswith("status") and value:
                shown = badge(value)
            elif value is None or value == "":
                shown = "-"
            elif isinstance(value, bool):
                shown = "Yes" if value else "No"
            elif isinstance(value, (dict, list)):
                shown = esc(json.dumps(value, default=str))
            else:
                shown = esc(value)
            pairs.append((label_of(key), shown))
        kv_grid(pairs)

    section("Approval history")
    approvals = get_api_data(f"/leave/requests/{selected}/approvals")
    if approvals is not None:
        approvals_table(
            approvals,
            "No approval steps recorded for this request.",
            f"approvals_{selected}.csv",
        )


def page_leave():
    page_header(
        "Leave Management",
        "Monitor employee leave balances, requests and approval history.",
    )
    requests_tab, balances_tab = st.tabs(["Leave requests", "Leave balances"])
    with requests_tab:
        render_leave_requests()
    with balances_tab:
        render_leave_balances()


# ==========================================
# EXPENSE MANAGEMENT
# ==========================================


def render_claim(claim_id: str, scope: str):
    detail = get_api_data(f"/expenses/claims/{claim_id}")
    if not detail:
        return

    currency = detail["currency_code"]
    lines = detail.get("expense_lines") or []

    stat_strip([
        ("Claim amount", money(detail["total_amount_minor"], currency)),
        ("Expense lines", len(lines)),
        ("Status", label_of(detail["status"]), tone_of(detail["status"])),
    ])
    note("Business purpose", detail["business_purpose"])
    kv_grid([
        ("Claim ID", esc(claim_id)),
        ("Employee", esc(detail["employee_id"])),
        ("Cost center", esc(detail["cost_center_id"] or "Not assigned")),
        ("Country", esc(detail["country_code"])),
        ("Currency", esc(currency)),
    ])

    section("Expense line items")
    if lines:
        rows = [
            {
                "Line": l["line_number"],
                "Date": l["expense_date"],
                "Category": label_of(l["category"]),
                "Merchant": l["merchant"],
                "Description": l["description"],
                "Amount": money(l["amount_minor"], currency),
                "Receipt": l["receipt_filename"] or "⚠ Missing",
                "Receipt type": l["receipt_mime_type"] or "-",
            }
            for l in lines
        ]
        show_table(pd.DataFrame(rows), export_name=f"lines_{claim_id}.csv", scope=scope)
    else:
        st.info("This claim has no expense lines.")

    section("Approval history")
    approvals = get_api_data(f"/expenses/claims/{claim_id}/approvals")
    if approvals is not None:
        approvals_table(
            approvals,
            "No approval history available.",
            f"approvals_{claim_id}.csv",
            scope=scope,
        )


def page_expenses():
    page_header(
        "Expense Management",
        "Manage expense claims, line items, receipts and approval history.",
    )

    # ---- Look up one claim ----
    section("Find a claim", "Jump straight to a claim by its ID.")
    with st.form("expense_claim_lookup_form"):
        c1, c2 = st.columns([4, 1])
        claim_id_lookup = c1.text_input(
            "Expense claim ID", placeholder="Example: EXP-2026-000944"
        )
        with c2:
            st.write("")
            submitted = _stretch(st.form_submit_button, "Search claim")

    if submitted:
        if claim_id_lookup.strip():
            st.session_state["expense_lookup_id"] = norm_id(claim_id_lookup)
        else:
            st.session_state.pop("expense_lookup_id", None)
            st.warning("Enter an expense claim ID.")

    lookup_id = st.session_state.get("expense_lookup_id")
    if lookup_id:
        with st.container(border=True):
            head, clear = st.columns([5, 1])
            head.markdown(f"**Claim {esc(lookup_id)}**")
            if clear.button("Clear", key="clear_lookup"):
                st.session_state.pop("expense_lookup_id", None)
                st.rerun()
            render_claim(lookup_id, "lookup")

    # ---- Browse claims ----
    section("Browse claims")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        employee_filter = c1.text_input(
            "Employee ID", placeholder="EMP-000001", key="expense_employee_filter"
        )
        country_filter = c2.selectbox(
            "Country", ["All", "IN", "US"], key="expense_country_filter"
        )
        status_filter = c3.selectbox(
            "Claim status",
            [
                "All", "draft", "submitted", "pending_approval",
                "needs_review", "approved", "rejected", "cancelled",
            ],
            format_func=lambda v: v if v == "All" else label_of(v),
            key="expense_status_filter",
        )
        c1, c2 = st.columns(2)
        category_filter = c1.selectbox(
            "Expense category",
            [
                "All", "travel", "meals", "accommodation",
                "office_supplies", "software", "training",
            ],
            format_func=lambda v: v if v == "All" else label_of(v),
            key="expense_category_filter",
        )
        page_size = c2.selectbox(
            "Records per page", [10, 20, 50, 100], index=1, key="expense_page_size"
        )

    params = {"page_size": page_size}
    if employee_filter.strip():
        params["employee_id"] = norm_id(employee_filter)
    if country_filter != "All":
        params["country_code"] = country_filter
    if status_filter != "All":
        params["status"] = status_filter
    if category_filter != "All":
        params["category"] = category_filter

    first = get_api_data("/expenses/claims", params={**params, "page": 1})
    if first is None:
        return

    st.write("")
    stat_strip([
        ("Matching expense claims", first["total"]),
        ("Pages", first["total_pages"], None, f"{page_size} per page"),
    ])

    result = load_page("/expenses/claims", params, first, "expense_claim_page")
    if not result:
        return
    claims = result["items"]
    if not claims:
        st.info("No expense claims match these filters.")
        return

    rows = [
        {
            "Claim ID": c["expense_claim_id"],
            "Employee ID": c["employee_id"],
            "Country": c["country_code"],
            "Category": label_of(c["primary_category"]),
            "Amount": money(c["total_amount_minor"], c["currency_code"]),
            "Start": c["expense_start_date"],
            "End": c["expense_end_date"],
            "Status": dot_label(c["status"]),
        }
        for c in claims
    ]
    show_table(pd.DataFrame(rows), export_name="expense_claims.csv")
    st.caption(
        f"Showing {len(claims)} claims on page {result['page']} "
        f"of {result['total_pages']}."
    )

    section("Claim details", "Pick a claim to see its line items and approvals.")
    selected = st.selectbox(
        "Expense claim",
        [c["expense_claim_id"] for c in claims],
        key="selected_expense_claim",
    )
    if selected:
        render_claim(selected, "browse")


# ==========================================
# APPROVAL CENTER
# ==========================================


def step_card(item) -> str:
    tone = tone_of(item["decision"])
    reason = esc(item.get("decision_reason") or "No reason recorded")
    when = esc(item.get("decided_at") or "-")
    return (
        f'<div class="ef-step s-{tone}"><div class="top">'
        f'<b>Step {esc(item["step_order"])}: {esc(item["approver_name"])}</b>'
        f'{badge(item["decision"])}</div>'
        f'<div class="body">{reason}</div><div class="meta">{when}</div></div>'
    )


def render_pending_tab(params, approver_id):
    approval_data = get_api_data("/approvals/pending", params=params)
    if approval_data is None:
        st.error("Unable to retrieve approval requests. Check the API server.")
        return

    items = approval_data.get("items", [])
    leave_count = sum(1 for i in items if i["request_type"] == "leave")
    expense_count = sum(1 for i in items if i["request_type"] == "expense")

    stat_strip([
        ("Pending approvals", len(items)),
        ("Leave", leave_count),
        ("Expense", expense_count),
    ])

    if not items:
        st.write("")
        st.info("No pending approvals match your filters.")
        return

    rows = [
        {
            "Approval ID": i["approval_step_id"],
            "Request ID": i["request_id"],
            "Type": label_of(i["request_type"]),
            "Requester": i["requester_name"],
            "Employee ID": i["requester_employee_id"],
            "Department": i["department"],
            "Country": i["country_code"],
            "Approver": i["approver_employee_id"],
            "Step": i["step_order"],
            "Summary": i["summary"],
            "Start": i["start_date"],
            "End": i["end_date"],
            "Amount": money(i["amount_minor"], i["currency_code"]),
            "Status": dot_label(i["status"]),
        }
        for i in items
    ]
    section("Pending approval steps")
    show_table(pd.DataFrame(rows), export_name="pending_approvals.csv")

    # ---- Process one approval ----
    section("Process an approval")
    by_id = {i["approval_step_id"]: i for i in items}
    selected_id = st.selectbox(
        "Approval request",
        options=list(by_id.keys()),
        format_func=lambda a: (
            f'{by_id[a]["request_id"]} | {label_of(by_id[a]["request_type"])} | '
            f'{by_id[a]["requester_name"]}'
        ),
        key="selected_approval_step",
    )
    item = by_id[selected_id]

    pairs = [
        ("Request ID", esc(item["request_id"])),
        ("Requester", esc(f'{item["requester_name"]} ({item["requester_employee_id"]})')),
        ("Department", esc(item["department"])),
        ("Type", esc(label_of(item["request_type"]))),
        ("Country", esc(item["country_code"])),
        ("Assigned approver", esc(item["approver_employee_id"])),
    ]
    if item["amount_minor"] is not None:
        pairs.append(("Claim amount", esc(money(item["amount_minor"], item["currency_code"]))))
    else:
        pairs.append(("Leave dates", esc(f'{item["start_date"]} to {item["end_date"]}')))
    kv_grid(pairs)
    note("Summary", item["summary"])

    # Same rule as before: only the assigned approver can decide.
    acting = approver_id.strip().upper()
    can_process = bool(acting) and acting == item["approver_employee_id"]
    if not acting:
        st.info(
            "Enter the assigned approver's employee ID in the filter above "
            "to enable decisions."
        )
    elif not can_process:
        st.warning(
            "The employee ID you entered doesn't match the assigned approver "
            "for this request."
        )
    else:
        st.success(f"Deciding as {acting}.")

    reason = st.text_area(
        "Decision reason",
        placeholder="Explain the decision. A reason is required to reject.",
        key=f"decision_reason_{selected_id}",
    )

    c1, c2 = st.columns(2)
    with c1:
        approve = _stretch(
            st.button, "Approve request", type="primary",
            disabled=not can_process, key=f"approve_{selected_id}",
        )
    with c2:
        reject = _stretch(
            st.button, "Reject request",
            disabled=not can_process, key=f"reject_{selected_id}",
        )

    if approve:
        result = post_api_data(
            f"/approvals/{selected_id}/decision",
            {"actor_employee_id": acting, "decision": "approve", "reason": reason.strip() or None},
        )
        if result is not None:
            st.session_state["approval_action_message"] = result.get(
                "message", "Request approved."
            )
            st.rerun()

    if reject:
        if not reason.strip():
            st.error("Add a reason before rejecting.")
        else:
            result = post_api_data(
                f"/approvals/{selected_id}/decision",
                {"actor_employee_id": acting, "decision": "reject", "reason": reason.strip()},
            )
            if result is not None:
                st.session_state["approval_action_message"] = result.get(
                    "message", "Request rejected."
                )
                st.rerun()


def render_history_tab(params):
    history_status = st.selectbox(
        "Decision",
        ["All", "Approved", "Rejected", "Skipped"],
        key="approval_history_status",
    )
    history_params = dict(params)
    if history_status != "All":
        history_params["decision_status"] = history_status.lower()
    history_params["limit"] = 100

    history_data = get_api_data("/approvals/history", params=history_params)
    if history_data is None:
        st.warning("Unable to retrieve approval history. Check the API server.")
        return

    history = history_data.get("items", [])
    count = lambda d: sum(1 for i in history if i["decision"] == d)
    stat_strip([
        ("Decisions shown", len(history), None, "Latest 100"),
        ("Approved", count("approved"), "ok"),
        ("Rejected", count("rejected"), "bad"),
        ("Skipped", count("skipped")),
    ])

    if not history:
        st.write("")
        st.info("No completed approval decisions match your filters.")
        return

    rows = [
        {
            "Approval ID": i["approval_step_id"],
            "Request ID": i["request_id"],
            "Type": label_of(i["request_type"]),
            "Requester": i["requester_name"],
            "Approver": f'{i["approver_name"]} ({i["approver_employee_id"]})',
            "Step": i["step_order"],
            "Decision": dot_label(i["decision"]),
            "Request status": label_of(i["request_status"]),
            "Decided": str(i["decided_at"]) if i["decided_at"] else "-",
            "Reason": i["decision_reason"] or "-",
            "Summary": i["summary"],
            "Amount": money(i["amount_minor"], i["currency_code"]),
        }
        for i in history
    ]
    section("Completed decisions")
    show_table(pd.DataFrame(rows), export_name="approval_history.csv")

    section("Decision trail", "Every step a request went through.")
    request_ids = list(dict.fromkeys(i["request_id"] for i in history))
    selected_request = st.selectbox(
        "Request", request_ids, key="history_selected_request"
    )
    steps = [i for i in history if i["request_id"] == selected_request]
    st.markdown("".join(step_card(s) for s in steps), unsafe_allow_html=True)
    st.markdown(
        f'Overall request status: {badge(steps[0]["request_status"])}',
        unsafe_allow_html=True,
    )


def page_approvals():
    page_header(
        "Approval Center",
        "Review, approve or reject pending leave and expense requests.",
    )

    if "approval_action_message" in st.session_state:
        st.success(st.session_state.pop("approval_action_message"))

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        approver_id = c1.text_input(
            "Approver employee ID", placeholder="Example: EMP-000015", key="appr_approver"
        )
        request_type = c2.selectbox(
            "Request type", ["All", "Leave", "Expense"], key="appr_type"
        )
        country = c3.selectbox("Country", ["All", "IN", "US"], key="appr_country")

    params = {}
    if approver_id.strip():
        params["approver_employee_id"] = approver_id.strip().upper()
    if request_type != "All":
        params["request_type"] = request_type.lower()
    if country != "All":
        params["country_code"] = country

    pending_tab, history_tab = st.tabs(["Pending approvals", "Decision history"])
    with pending_tab:
        render_pending_tab(params, approver_id)
    with history_tab:
        render_history_tab(params)


# ==========================================
# EXCEPTION MANAGEMENT
# ==========================================


def page_exceptions():
    page_header(
        "Exception Management",
        "Find policy violations, missing information and unusual transactions.",
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        severity = c1.selectbox("Severity", ["All", "High", "Medium"], key="exc_severity")
        exception_type = c2.selectbox(
            "Exception type",
            [
                "All", "missing_cost_center", "missing_receipt", "duplicate_receipt",
                "per_item_limit_breach", "out_of_employment_dates",
                "overlapping_approved_leave",
            ],
            format_func=lambda v: v if v == "All" else label_of(v),
            key="exc_type",
        )
        country = c3.selectbox("Country", ["All", "IN", "US"], key="exc_country")

    params = {}
    if severity != "All":
        params["severity"] = severity.lower()
    if exception_type != "All":
        params["exception_type"] = exception_type
    if country != "All":
        params["country_code"] = country

    data = get_api_data("/exceptions/", params=params)
    if data is None:
        st.error("Unable to retrieve exceptions from the API.")
        return

    items = data.get("items", [])
    high = sum(1 for i in items if i["severity"] == "high")
    medium = sum(1 for i in items if i["severity"] == "medium")

    st.write("")
    stat_strip([
        ("Total exceptions", len(items)),
        ("High severity", high, "bad" if high else None),
        ("Medium severity", medium, "warn" if medium else None),
    ])

    if not items:
        st.write("")
        st.success("No exceptions match the selected filters.")
        return

    rows = [
        {
            "Exception ID": i["exception_id"],
            "Type": label_of(i["exception_type"]),
            "Severity": dot_label(i["severity"]),
            "Employee": i["employee_name"],
            "Employee ID": i["employee_id"],
            "Department": i["department"],
            "Country": i["country_code"],
            "Entity ID": i["entity_id"],
            "Amount": money(i["amount_minor"], i["currency_code"]),
            "Description": i["description"],
        }
        for i in items
    ]
    section("Detected exceptions")
    show_table(pd.DataFrame(rows), export_name="exceptions.csv")

    section("Investigate an exception")
    by_id = {i["exception_id"]: i for i in items}
    selected_id = st.selectbox(
        "Exception",
        list(by_id.keys()),
        format_func=lambda e: f'{e} | {label_of(by_id[e]["exception_type"])}',
        key="exc_selected",
    )
    selected = by_id[selected_id]

    st.markdown(
        f'**{esc(label_of(selected["exception_type"]))}** &nbsp; {badge(selected["severity"])}',
        unsafe_allow_html=True,
    )
    kv_grid([
        ("Employee", esc(f'{selected["employee_name"]} ({selected["employee_id"]})')),
        ("Department", esc(selected["department"])),
        ("Entity", esc(f'{label_of(selected["entity_type"])}: {selected["entity_id"]}')),
        ("Related record", esc(selected["related_id"] or "None")),
    ])
    note("What was found", selected["description"])


# ==========================================
# ANALYTICS
# ==========================================


def page_analytics():
    page_header(
        "Analytics",
        "Workforce, spend, reimbursements and policy exceptions at a glance.",
    )

    summary = get_api_data("/dashboard/summary")
    analytics = get_api_data("/analytics/breakdown")
    if summary is None or analytics is None:
        st.error("Unable to load analytics. Check the API server.")
        return

    stat_strip([
        ("Total employees", summary["total_employees"]),
        ("Active employees", summary["active_employees"]),
        ("Leave requests", summary["total_leave_requests"]),
        ("Expense claims", summary["total_expense_claims"]),
    ])

    # ---- Workforce ----
    section("Workforce distribution")
    country_df = pd.DataFrame(analytics["workforce_by_country"])
    department_df = pd.DataFrame(analytics["workforce_by_department"])
    left, right = st.columns(2)
    with left:
        st.markdown("**Employees by country**")
        if not country_df.empty:
            country_df["country"] = (
                country_df["country_code"]
                .map({"IN": "India", "US": "United States"})
                .fillna(country_df["country_code"])
            )
            hbar(country_df, "country", "employee_count")
    with right:
        st.markdown("**Employees by department**")
        if not department_df.empty:
            hbar(department_df, "department", "employee_count")

    # ---- Leave ----
    section("Leave requests by status")
    leave_df = pd.DataFrame({
        "Status": ["Approved", "Pending", "Needs review", "Rejected"],
        "Count": [
            summary["approved_leave_requests"],
            summary["pending_leave_requests"],
            summary["leave_requests_needs_review"],
            summary["rejected_leave_requests"],
        ],
    })
    hbar(
        leave_df, "Status", "Count",
        color_map={
            "Approved": TONE_HEX["ok"], "Pending": TONE_HEX["warn"],
            "Needs review": TONE_HEX["review"], "Rejected": TONE_HEX["bad"],
        },
    )

    # ---- Expenses ----
    section("Approved expense spend", "Currencies are never added together.")
    expense_df = pd.DataFrame(analytics["approved_expenses_by_department"])
    if expense_df.empty:
        st.info("No approved expense data available.")
    else:
        for currency in sorted(expense_df["currency_code"].dropna().unique()):
            part = expense_df[expense_df["currency_code"] == currency].copy()
            part["approved_amount"] = part["total_amount_minor"] / 100
            total_spend = part["total_amount_minor"].sum() / 100
            stat_strip([
                (f"Approved spend ({currency})", money(total_spend * 100, currency)),
                ("Approved claims", int(part["claim_count"].sum())),
            ])
            left, right = st.columns(2)
            with left:
                hbar(part, "department", "approved_amount", fmt=",.0f")
            with right:
                table = part[["department", "country_code", "claim_count", "approved_amount"]].copy()
                table["approved_amount"] = table["approved_amount"].round(2)
                table.columns = ["Department", "Country", "Claims", f"Approved ({currency})"]
                show_table(table)
            st.write("")

    # ---- Reimbursements ----
    section("Reimbursements")
    stat_strip([
        ("Total reimbursements", summary["total_reimbursements"]),
        ("Pending payment", summary["pending_reimbursements"], "warn" if summary["pending_reimbursements"] else None),
        ("Paid", summary["paid_reimbursements"], "ok"),
    ])

    # ---- Exceptions ----
    section("Exception analysis")
    exc = analytics["exception_summary"]
    severity_counts = {i["severity"]: i["count"] for i in exc["by_severity"]}
    stat_strip([
        ("Total findings", exc["total_findings"]),
        ("High severity", severity_counts.get("high", 0), "bad"),
        ("Medium severity", severity_counts.get("medium", 0), "warn"),
    ])
    type_df = pd.DataFrame(exc["by_type"])
    if not type_df.empty:
        value_col = next(
            (c for c in type_df.columns
             if c != "exception_type" and pd.api.types.is_numeric_dtype(type_df[c])),
            "count",
        )
        type_df["Type"] = type_df["exception_type"].map(label_of)
        left, right = st.columns(2)
        with left:
            st.markdown("**Findings by type**")
            hbar(type_df, "Type", value_col)
        with right:
            st.markdown("**Breakdown**")
            show_table(type_df[["Type", value_col]].rename(columns={value_col: "Findings"}))

    # ---- Workflow performance ----
    section("Workflow performance", "Share of all submitted work that ended in approval.")
    total_leave = summary["total_leave_requests"]
    total_expense = summary["total_expense_claims"]
    leave_rate = summary["approved_leave_requests"] / total_leave * 100 if total_leave else 0
    expense_rate = summary["approved_expense_claims"] / total_expense * 100 if total_expense else 0
    stat_strip([
        ("Leave requests approved", f"{leave_rate:.1f}%", "ok",
         f'{summary["approved_leave_requests"]:,} of {total_leave:,}'),
        ("Expense claims approved", f"{expense_rate:.1f}%", "ok",
         f'{summary["approved_expense_claims"]:,} of {total_expense:,}'),
    ])


# ==========================================
# ROUTER
# ==========================================

PAGES = {
    "Dashboard": page_dashboard,
    "Employees": page_employees,
    "Leave Management": page_leave,
    "Expense Management": page_expenses,
    "Approval Center": page_approvals,
    "Exception Management": page_exceptions,
    "Analytics": page_analytics,
}

PAGES[render_sidebar()]()
