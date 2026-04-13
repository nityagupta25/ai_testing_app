"""CoverIQ shell: dark theme, top bar, icon rail — shared by Streamlit pages."""

from __future__ import annotations

import streamlit as st

# Palette aligned to prototype (deep navy + teal)
BG = "#050d18"
BG_CARD = "#0a1c2e"
BG_RAIL = "#071018"
ACCENT = "#00c2d4"
TEXT = "#e8eef5"
TEXT_MUTED = "#8a9bb0"
BORDER = "#143044"

NAV_ITEMS = [
    ("dashboard", "Dashboard", "▣"),
    ("generate", "Generate", "✦"),
    ("active", "Active checklists", "☑"),
    ("projects", "Projects", "▸"),
    ("insights", "AI insights", "◉"),
    ("settings", "Settings", "⚙"),
]


def inject_theme() -> None:
    st.markdown(
        f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] {{
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  }}
  .stApp {{
    background: linear-gradient(180deg, {BG} 0%, #020810 100%);
    color: {TEXT};
  }}
  section[data-testid="stSidebar"] {{ display: none; }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  div[data-testid="stToolbar"] {{ display: none; }}
  footer {{ visibility: hidden; }}
  #MainMenu {{ visibility: hidden; }}
  .block-container {{
    padding-top: 0.75rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px;
  }}
  .coveriq-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.5rem 0 1rem 0;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 1.25rem;
  }}
  .coveriq-brand {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }}
  .coveriq-brand span.siemens {{ color: #fff; font-size: 0.95rem; }}
  .coveriq-brand span.sep {{ color: {TEXT_MUTED}; }}
  .coveriq-brand span.product {{ color: {TEXT_MUTED}; font-weight: 500; }}
  .coveriq-search-wrap {{
    flex: 1;
    max-width: 520px;
    margin: 0 auto;
  }}
  .coveriq-search {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 999px;
    padding: 0.45rem 1rem;
    color: {TEXT_MUTED};
    font-size: 0.88rem;
  }}
  .coveriq-avatar {{
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: {ACCENT};
    display: flex;
    align-items: center;
    justify-content: center;
    color: #001018;
    font-weight: 700;
    font-size: 0.75rem;
  }}
  .coveriq-rail {{
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 0.5rem 0.25rem;
    background: {BG_RAIL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    min-width: 52px;
    align-items: center;
  }}
  .coveriq-rail button {{
    width: 40px !important;
    height: 40px !important;
    border-radius: 10px !important;
    padding: 0 !important;
    font-size: 1.1rem !important;
    line-height: 1 !important;
  }}
  .coveriq-page-label {{
    color: {ACCENT};
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.25rem;
  }}
  .coveriq-title {{
    color: #fff;
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.35rem 0;
  }}
  .coveriq-sub {{
    color: {TEXT_MUTED};
    font-size: 0.95rem;
    margin: 0 0 1.25rem 0;
  }}
  .coveriq-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 0.75rem;
  }}
  .coveriq-hero {{
    background: linear-gradient(135deg, #0098a8 0%, {ACCENT} 100%);
    border: none;
    color: #001018;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
  }}
  div[data-testid="stVerticalBlock"] > div:first-child h1 {{
    font-size: 1.5rem;
    color: #fff;
    padding-top: 0;
  }}
  .stButton > button[kind="primary"] {{
    background-color: {ACCENT} !important;
    color: #001018 !important;
    border: none !important;
    font-weight: 600 !important;
  }}
  .stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div {{
    background-color: {BG_CARD} !important;
    color: {TEXT} !important;
    border-color: {BORDER} !important;
  }}
  label {{
    color: {TEXT} !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )


def _ensure_session() -> None:
    if "cq_page" not in st.session_state:
        st.session_state.cq_page = "dashboard"
    if "cq_checklists" not in st.session_state:
        st.session_state.cq_checklists = _default_checklists()
    if "cq_projects" not in st.session_state:
        st.session_state.cq_projects = _default_projects()
    if "cq_detail_id" not in st.session_state:
        st.session_state.cq_detail_id = None


def _default_checklists():
    return [
        {
            "id": "cl1",
            "title": "Add API Rate Limiting",
            "meta": "API Gateway • 2 hours ago",
            "status": "in_progress",
            "done": 7,
            "total": 11,
        },
        {
            "id": "cl2",
            "title": "New Login API",
            "meta": "User Authentication • Today",
            "status": "in_progress",
            "done": 7,
            "total": 15,
        },
        {
            "id": "cl3",
            "title": "Payment Flow Update",
            "meta": "Payment Service • Yesterday",
            "status": "completed",
            "done": 12,
            "total": 12,
        },
    ]


def _default_projects():
    return [
        {
            "name": "API Gateway",
            "desc": "Core routing and policy enforcement",
            "status": "testing",
            "checklists": 5,
            "coverage": 80,
        },
        {
            "name": "Payment Service",
            "desc": "Billing and payment orchestration",
            "status": "review",
            "checklists": 3,
            "coverage": 65,
        },
        {
            "name": "User Authentication",
            "desc": "Identity and session management",
            "status": "completed",
            "checklists": 8,
            "coverage": 100,
        },
    ]


def render_top_bar() -> None:
    st.markdown(
        f"""
<div class="coveriq-topbar">
  <div class="coveriq-brand">
    <span style="color:{TEXT_MUTED};font-size:1.1rem;">☰</span>
    <span class="siemens">SIEMENS</span>
    <span class="sep">|</span>
    <span class="product">CoverIQ</span>
  </div>
  <div class="coveriq-search-wrap">
    <div class="coveriq-search">🔍 &nbsp; Search features, tickets, or checklists</div>
  </div>
  <div class="coveriq-avatar">U</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_nav_rail(active: str) -> str:
    """Render icon buttons; returns selected page key after interaction."""
    _ensure_session()
    for key, _label, icon in NAV_ITEMS:
        is_active = key == active
        if st.button(
            icon,
            key=f"nav_{key}",
            help=_label,
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state.cq_page = key
            st.session_state.cq_detail_id = None
            st.rerun()
    return st.session_state.cq_page


def coveriq_page_header(label: str, title: str, subtitle: str) -> None:
    st.markdown(f'<p class="coveriq-page-label">{label}</p>', unsafe_allow_html=True)
    st.markdown(f'<h2 class="coveriq-title">{title}</h2>', unsafe_allow_html=True)
    st.markdown(f'<p class="coveriq-sub">{subtitle}</p>', unsafe_allow_html=True)


def shell(active_page: str, content) -> None:
    """Two-column layout: rail + main (top bar + user content)."""
    inject_theme()
    _ensure_session()
    r1, r2 = st.columns([0.55, 7], gap="small")
    with r1:
        render_nav_rail(active_page)
    with r2:
        render_top_bar()
        content()
