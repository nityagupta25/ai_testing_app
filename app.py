import json
import os
import uuid
from typing import Dict, List

import pandas as pd
import streamlit as st
#from openai import OpenAI
import google.generativeai as genai

from checklist_pipeline import SECTIONS, run_pipeline
from coveriq_ui import coveriq_page_header, shell
from export_utils import (
    checklist_to_df,
    checklist_to_docx_bytes,
    checklist_to_excel_bytes,
    checklist_to_jira_json_bytes,
    checklist_to_testrail_csv_bytes,
)

PROJECT_TYPES = ["API", "Web", "Mobile", "Backend", "Desktop"]


def get_api_key() -> str:
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    return os.getenv("OPENAI_API_KEY", "")

# def get_client() -> OpenAI:
#     api_key = get_api_key()
#     if not api_key:
#         raise ValueError(
#             "OpenAI API key not found. Set OPENAI_API_KEY in environment "
#             "variables or Streamlit secrets."
#         )
#     return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
def get_client():
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "Gemini API key not found. Set OPENAI_API_KEY in "
            "environment variables or Streamlit secrets."
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")




def _init_session() -> None:
    if "cq_page" not in st.session_state:
        st.session_state.cq_page = "dashboard"
    if "checklist" not in st.session_state:
        st.session_state.checklist = {s: [] for s in SECTIONS}
    if "cq_checklists" not in st.session_state:
        st.session_state.cq_checklists = [
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
    if "cq_projects" not in st.session_state:
        st.session_state.cq_projects = [
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
    if "cq_detail_id" not in st.session_state:
        st.session_state.cq_detail_id = None
    if "cq_checklist_store" not in st.session_state:
        st.session_state.cq_checklist_store = {}
    if "cq_completed" not in st.session_state:
        st.session_state.cq_completed = {}
    if "feature_title" not in st.session_state:
        st.session_state.feature_title = ""
    if "last_pipeline" not in st.session_state:
        st.session_state.last_pipeline = None


def _mock_checklist_body() -> Dict[str, List[str]]:
    return {
        "Functional": [
            "Validate request threshold enforcement",
            "Validate correct error response",
            "Validate retry behavior",
        ],
        "UI": [
            "Validate UI responsiveness across different screen sizes",
            "Verify button states (hover, active, disabled)",
            "Check form validation messages and error handling",
        ],
        "Edge": ["Burst traffic behavior", "Invalid API key handling", "Network interruption"],
        "Regression": ["Existing authentication APIs", "API gateway routing"],
        "Risk": ["Traffic spikes", "Token validation"],
    }


def _ensure_store(cid: str) -> None:
    if cid in st.session_state.cq_checklist_store:
        return
    if cid == "cl1":
        body = _mock_checklist_body()
        title = "Add API Rate Limiting"
    elif cid == "cl2":
        body = {s: [f"{s} sample {i}" for i in range(1, 4)] for s in SECTIONS}
        title = "New Login API"
    elif cid == "cl3":
        body = {s: [f"{s} sample {i}" for i in range(1, 4)] for s in SECTIONS}
        title = "Payment Flow Update"
    else:
        return
    total = sum(len(v) for v in body.values())
    st.session_state.cq_checklist_store[cid] = {
        "title": title,
        "checklist": body,
        "meta": next(
            (c["meta"] for c in st.session_state.cq_checklists if c["id"] == cid),
            "",
        ),
        "total": total,
    }
    if cid not in st.session_state.cq_completed:
        st.session_state.cq_completed[cid] = set()


def _item_key(cid: str, section: str, idx: int) -> str:
    return f"{cid}|{section}|{idx}"


def _sync_list_done(cid: str) -> None:
    done, total = _count_progress(cid)
    for c in st.session_state.cq_checklists:
        if c["id"] == cid:
            c["done"] = done
            c["total"] = total
            c["status"] = "completed" if total and done >= total else "in_progress"
            break


def _count_progress(cid: str) -> tuple[int, int]:
    _ensure_store(cid)
    data = st.session_state.cq_checklist_store.get(cid)
    if not data:
        return 0, 0
    body = data["checklist"]
    total = sum(len(v) for v in body.values())
    done_set = st.session_state.cq_completed.get(cid, set())
    done = 0
    for sec in SECTIONS:
        for i, _ in enumerate(body.get(sec, [])):
            if _item_key(cid, sec, i) in done_set:
                done += 1
    return done, total


def page_dashboard() -> None:
    coveriq_page_header(
        "SIEMENS",
        "Dashboard",
        "Welcome back! Here's your testing productivity overview.",
    )
    st.markdown(
        """
<div style="background:linear-gradient(135deg,#0098a8 0%,#00c2d4 100%);border-radius:12px;
padding:1.25rem 1.5rem;color:#001018;margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;">
  <div>
    <div style="font-weight:600;font-size:0.95rem;">📈 AI Productivity Impact</div>
    <div style="font-size:2rem;font-weight:800;line-height:1.2;">+25% <span style="font-size:1rem;font-weight:600;">testing productivity</span></div>
    <div style="opacity:0.85;font-size:0.9rem;">~60 hours saved weekly</div>
  </div>
  <div style="font-size:1.5rem;">↗</div>
</div>
""",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown("**Active Testing Projects**")
        for p in st.session_state.cq_projects:
            status = p["status"]
            badge = {
                "testing": ("Testing", "#00c2d4"),
                "review": ("In Review", "#f5a623"),
                "completed": ("Completed", "#3ecf8e"),
            }.get(status, ("", "#888"))
            st.markdown(
                f'<div class="coveriq-card" style="padding:0.75rem 1rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<strong>{p["name"]}</strong>'
                f'<span style="border:1px solid {badge[1]};color:{badge[1]};border-radius:999px;padding:2px 10px;font-size:0.75rem;">{badge[0]}</span></div>'
                f'<div style="color:#8a9bb0;font-size:0.85rem;margin-top:0.35rem;">{p["coverage"]}% Coverage</div></div>',
                unsafe_allow_html=True,
            )
    with c2:
        st.markdown("**Recent AI Generated Checklists**")
        for c in st.session_state.cq_checklists[:2]:
            pct = int(100 * c["done"] / c["total"]) if c["total"] else 0
            st.markdown(
                f'<div class="coveriq-card" style="padding:0.75rem 1rem;">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<div><strong>{c["title"]}</strong><br/><span style="color:#8a9bb0;font-size:0.85rem;">{c["meta"].split("•")[-1].strip()}</span></div>'
                f'<span style="color:#8a9bb0;">{pct}% Coverage</span></div></div>',
                unsafe_allow_html=True,
            )


def page_generate() -> None:
    coveriq_page_header(
        "SIEMENS",
        "Generate AI Testing Checklist",
        "Provide feature details and let AI generate comprehensive testing scenarios",
    )
    app_url = st.text_input(
        "Application URL (Optional)",
        placeholder="Paste application URL or environment link (e.g., staging / dev URL)",
        key="gen_url",
    )
    st.caption(
        "Providing an application link helps AI understand workflows and generate more accurate test scenarios"
    )
    feature_description = st.text_area(
        "Feature Description",
        placeholder="Paste feature description, Jira ticket, or PR details",
        height=200,
        key="gen_feature",
    )
    st.caption("Include as much detail as possible for better AI-generated test scenarios")
st.markdown(
    """
<div style="background:#0a1c2e;border:1px solid #143044;border-radius:8px;padding:0.75rem 1rem;margin-top:0.5rem;font-size:0.85rem;color:#8a9bb0;">
💡 <strong style="color:#00c2d4;">Tips for accurate results:</strong><br>
- Mention <strong style="color:#e8eef5;">exact UI element names</strong> (e.g. "Report an Issue button")<br>
- Describe <strong style="color:#e8eef5;">expected behavior</strong> (e.g. "should open in a new tab")<br>
- Include <strong style="color:#e8eef5;">location context</strong> (e.g. "top right corner under '?' icon")<br>
- Add any <strong style="color:#e8eef5;">URLs, flows, or conditions</strong> involved
</div>
""",
    unsafe_allow_html=True,
)
    extras = st.text_area(
        "Additional preferences (optional)",
        placeholder='e.g. "high traffic", "quick service", latency SLOs, compliance notes…',
        height=80,
        key="gen_extras",
    )
    st.caption("Notes like workload, constraints, or rollout assumptions improve scenario quality.")
    project_type = st.selectbox("Project Type", PROJECT_TYPES, index=0, key="gen_pt")

    can_generate = bool(feature_description and feature_description.strip())
    gen = st.button(
        "✦ Generate AI Checklist",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
    )

    if gen and can_generate:
        with st.spinner("Phases 1–2: parsing context · Phase 3: calling LLM…"):
            try:
                result = run_pipeline(
                    feature_description.strip(),
                    app_url=app_url or "",
                    project_type=project_type,
                    extras=(extras or "").strip(),
                    client=get_client(),
                )
                st.session_state.checklist = result["checklist"]
                st.session_state.last_pipeline = result
                st.session_state.feature_title = (
                    feature_description.strip()[:120] + "…"
                    if len(feature_description) > 120
                    else feature_description.strip()
                )
                meta = result.get("meta") or {}
                st.success(
                    f"Checklist generated · {meta.get('model', 'model')} · "
                    f"{meta.get('generation_time_ms', 0)} ms"
                )
            except json.JSONDecodeError:
                st.error("AI response could not be parsed as JSON. Please try again.")
            except Exception as exc:
                st.error(f"Failed to generate checklist: {exc}")

    lp = st.session_state.last_pipeline
    if lp and lp.get("intermediate"):
        with st.expander("Phase 1 — structured input (intermediate schema)", expanded=False):
            st.json(lp["intermediate"])
        with st.expander("Phase 2 — scenario seeds", expanded=False):
            st.json(lp.get("seeds") or {})

    checklist: Dict[str, List[str]] = st.session_state.checklist
    if any(checklist.get(s) for s in SECTIONS):
        st.markdown("---")
        st.subheader("Editable Checklist")
        for section in SECTIONS:
            st.markdown(f"### {section}")
            section_cases = checklist.get(section, [])
            if not section_cases:
                st.info(f"No {section.lower()} test cases yet.")
            for i in range(len(section_cases)):
                c_text, c_del = st.columns([5, 1])
                with c_text:
                    checklist[section][i] = st.text_input(
                        label=f"{section} #{i + 1}",
                        value=section_cases[i],
                        key=f"case_{section}_{i}",
                        label_visibility="collapsed",
                        placeholder=f"Enter {section.lower()} test case...",
                    )
                with c_del:
                    st.caption("")
                    if st.button(
                        "❌",
                        key=f"del_{section}_{i}",
                        help="Delete this test case",
                    ):
                        checklist[section].pop(i)
                        st.rerun()

        st.markdown("#### Manage Test Cases")
        mc1, mc2, mc3 = st.columns([2, 1, 1])
        with mc1:
            target_section = st.selectbox("Section", SECTIONS, key="target_section")
        with mc2:
            if st.button("Add Empty Test Case", use_container_width=True):
                checklist[target_section].append("")
                st.rerun()
        with mc3:
            if st.button("Delete Last Test Case", use_container_width=True):
                if checklist[target_section]:
                    checklist[target_section].pop()
                    st.rerun()
                else:
                    st.warning(f"No test cases in {target_section} section.")

        st.markdown("---")
        st.subheader("Export")
        df = checklist_to_df(checklist)
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv_data = df.to_csv(index=False).encode("utf-8")
        title = st.session_state.feature_title or "checklist"
        safe = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))[:40].strip()
        ex0, ex1, ex2, ex3, ex4 = st.columns(5)
        with ex0:
            st.download_button(
                label="CSV",
                data=csv_data,
                file_name=f"{safe or 'checklist'}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with ex1:
            st.download_button(
                "Excel (.xlsx)",
                data=checklist_to_excel_bytes(checklist),
                file_name=f"{safe or 'checklist'}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with ex2:
            st.download_button(
                "Word (.docx)",
                data=checklist_to_docx_bytes(checklist, title=title),
                file_name=f"{safe or 'checklist'}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        with ex3:
            st.download_button(
                "Jira (JSON)",
                data=checklist_to_jira_json_bytes(checklist, summary=title),
                file_name=f"{safe or 'checklist'}_jira.json",
                mime="application/json",
                use_container_width=True,
            )
        with ex4:
            st.download_button(
                "TestRail (CSV)",
                data=checklist_to_testrail_csv_bytes(checklist),
                file_name=f"{safe or 'checklist'}_testrail.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if st.button("Save to Active Checklists", type="primary", use_container_width=True):
            cid = f"u{uuid.uuid4().hex[:10]}"
            body = {s: list(checklist.get(s, [])) for s in SECTIONS}
            total = sum(len(v) for v in body.values())
            title = st.session_state.feature_title or "Untitled feature"
            st.session_state.cq_checklist_store[cid] = {
                "title": title,
                "checklist": body,
                "meta": f"{project_type} • Just now",
                "total": total,
            }
            st.session_state.cq_completed[cid] = set()
            st.session_state.cq_checklists.insert(
                0,
                {
                    "id": cid,
                    "title": title,
                    "meta": f"{project_type} • Just now",
                    "status": "in_progress",
                    "done": 0,
                    "total": total,
                },
            )
            st.success("Saved to Active Checklists.")
            st.session_state.cq_page = "active"
            st.rerun()


def page_active() -> None:
    coveriq_page_header(
        "SIEMENS",
        "Active Checklists",
        "Manage and track your AI-generated testing checklists",
    )
    for c in st.session_state.cq_checklists:
        pct = int(100 * c["done"] / c["total"]) if c["total"] else 0
        status = c["status"]
        badge = (
            "🕐 In Progress"
            if status == "in_progress"
            else "✓ Completed"
        )
        col_a, col_b = st.columns([4, 1])
        with col_a:
            st.markdown(
                f"**{c['title']}**  \n"
                f"<span style='color:#8a9bb0;font-size:0.9rem;'>📄 {c['meta']}</span>",
                unsafe_allow_html=True,
            )
            st.progress(min(pct / 100.0, 1.0))
            st.caption(f"{c['done']} / {c['total']} items")
        with col_b:
            st.caption(badge)
            if st.button("Open", key=f"open_{c['id']}", use_container_width=True):
                st.session_state.cq_detail_id = c["id"]
                st.session_state.cq_page = "detail"
                st.rerun()


def page_projects() -> None:
    coveriq_page_header(
        "SIEMENS",
        "Projects",
        "Overview of all testing projects and their coverage",
    )
    cols = st.columns(3, gap="medium")
    for i, p in enumerate(st.session_state.cq_projects):
        status = p["status"]
        badge_style = {
            "testing": ("Testing", "#00c2d4"),
            "review": ("In Review", "#f5a623"),
            "completed": ("Completed", "#3ecf8e"),
        }.get(status, ("", "#888"))
        with cols[i]:
            st.markdown(
                f'<div class="coveriq-card">'
                f'<div style="display:flex;justify-content:space-between;align-items:start;">'
                f'<span style="font-size:1.25rem;">📁</span>'
                f'<span style="border:1px solid {badge_style[1]};color:{badge_style[1]};border-radius:999px;padding:2px 8px;font-size:0.72rem;">{badge_style[0]}</span></div>'
                f'<h4 style="margin:0.5rem 0 0.25rem 0;">{p["name"]}</h4>'
                f'<p style="color:#8a9bb0;font-size:0.88rem;margin:0 0 0.75rem 0;">{p["desc"]}</p>'
                f'<div style="display:flex;justify-content:space-between;color:#8a9bb0;font-size:0.88rem;"><span>Checklists</span><span>{p["checklists"]}</span></div>'
                f'<div style="display:flex;justify-content:space-between;color:#8a9bb0;font-size:0.88rem;"><span>Coverage</span><span>{p["coverage"]}%</span></div>'
                f'<div style="margin-top:0.5rem;">',
                unsafe_allow_html=True,
            )
            st.progress(p["coverage"] / 100.0)
            st.markdown("</div>", unsafe_allow_html=True)


def page_insights() -> None:
    coveriq_page_header(
        "SIEMENS",
        "AI Insights",
        "AI-powered recommendations and testing intelligence",
    )
    insights = [
        ("🎯", "High Test Coverage Patterns", "Projects with API integration testing show 23% higher coverage rates", "#0d2a22"),
        ("⚠", "Common Testing Gaps", "Authentication edge cases are frequently missed in 40% of feature tests", "#2a2210"),
        ("📈", "Productivity Trend", "Team testing velocity increased by 32% after adopting AI-generated checklists", "#0f1c2a"),
    ]
    for icon, title, desc, tint in insights:
        st.markdown(
            f'<div class="coveriq-card" style="background:{tint};border-color:#143044;">'
            f'<div style="display:flex;gap:1rem;align-items:flex-start;">'
            f'<div style="font-size:1.5rem;width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:#0a1c2e;border-radius:10px;">{icon}</div>'
            f'<div><strong>{title}</strong><p style="color:#8a9bb0;margin:0.35rem 0 0 0;font-size:0.92rem;">{desc}</p></div>'
            f"</div></div>",
            unsafe_allow_html=True,
        )


def page_settings() -> None:
    coveriq_page_header(
        "SIEMENS",
        "Settings",
        "Manage your account and application preferences",
    )
    settings_rows = [
        ("👤", "Profile", "Manage your account information and preferences"),
        ("🔔", "Notifications", "Configure email and in-app notification settings"),
        ("🛡", "Security", "Manage password and two-factor authentication"),
        ("🎨", "Appearance", "Customize theme and display preferences"),
    ]
    for icon, title, desc in settings_rows:
        st.markdown(
            f'<div class="coveriq-card"><div style="display:flex;gap:1rem;align-items:center;">'
            f'<div style="font-size:1.35rem;">{icon}</div>'
            f"<div><strong>{title}</strong><br/><span style='color:#8a9bb0;font-size:0.9rem;'>{desc}</span></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )


def page_detail() -> None:
    cid = st.session_state.cq_detail_id
    if not cid:
        st.session_state.cq_page = "active"
        st.rerun()
        return
    _ensure_store(cid)
    data = st.session_state.cq_checklist_store.get(cid)
    if not data:
        st.error("Checklist not found.")
        if st.button("Back"):
            st.session_state.cq_page = "active"
            st.session_state.cq_detail_id = None
            st.rerun()
        return

    title = data["title"]
    body = data["checklist"]
    done, total = _count_progress(cid)
    pct = int(100 * done / total) if total else 0

    chead, cback = st.columns([5, 1])
    with chead:
        st.markdown(f"## Feature: {title}")
        st.progress(pct / 100.0 if total else 0.0)
        st.caption(f"{done} of {total} items completed · {pct}%")
    with cback:
        if st.button("← Back", use_container_width=True):
            st.session_state.cq_page = "active"
            st.session_state.cq_detail_id = None
            st.rerun()

    st.markdown(
        f'<div style="background:linear-gradient(90deg,#0098a8,#00c2d4);color:#001018;padding:0.65rem 1rem;border-radius:8px;font-weight:600;margin:0.5rem 0 1rem 0;">'
        f"AI Generated — You can edit or remove items in Generate view</div>",
        unsafe_allow_html=True,
    )

    main_c, sug_c = st.columns([2.2, 1], gap="medium")
    with main_c:
        done_set = st.session_state.cq_completed.setdefault(cid, set())
        for section in SECTIONS:
            st.markdown(f"### {section}")
            items = body.get(section, [])
            if not items:
                st.caption("No items.")
            for idx, item in enumerate(items):
                key = _item_key(cid, section, idx)
                was = key in done_set
                new = st.checkbox(
                    item,
                    value=was,
                    key=f"chk_{cid}_{section}_{idx}",
                )
                if new != was:
                    if new:
                        done_set.add(key)
                    else:
                        done_set.discard(key)
                    _sync_list_done(cid)
                    st.rerun()

        st.markdown("---")
        b1, b2, b3, b4, b5 = st.columns(5)
        with b1:
            if st.button("Mark Complete", type="primary", use_container_width=True):
                st.success("Marked complete (local session).")
        df = checklist_to_df(body)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        with b2:
            st.download_button(
                "Export CSV",
                csv_bytes,
                file_name="checklist.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with b3:
            if st.button("Jira", use_container_width=True):
                st.caption("Placeholder")
        with b4:
            if st.button("TestRail", use_container_width=True):
                st.caption("Placeholder")
        with b5:
            if st.button("Word", use_container_width=True):
                st.caption("Placeholder")

    with sug_c:
        st.markdown("### 💡 AI Suggestions")
        tips = [
            "Similar features often miss testing session expiration.",
            "Consider testing rate limit under burst traffic.",
            "Regression risk detected in authentication module.",
        ]
        for t in tips:
            st.markdown(
                f'<div class="coveriq-card" style="border-color:#5c4a1a;background:#1a1408;">'
                f'<span style="color:#f5a623;">⚠</span> {t}</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div class="coveriq-card" style="border-color:#143044;"><strong style="color:#00c2d4;">Pro Tip</strong>'
            '<p style="color:#8a9bb0;font-size:0.88rem;margin:0.5rem 0 0 0;">Suggestions reflect common patterns from similar features and typical testing gaps.</p></div>',
            unsafe_allow_html=True,
        )


def main_content() -> None:
    page = st.session_state.cq_page
    if page == "detail":
        page_detail()
    elif page == "dashboard":
        page_dashboard()
    elif page == "generate":
        page_generate()
    elif page == "active":
        page_active()
    elif page == "projects":
        page_projects()
    elif page == "insights":
        page_insights()
    elif page == "settings":
        page_settings()
    else:
        page_dashboard()


def main() -> None:
    st.set_page_config(
        page_title="CoverIQ · AI Testing",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _init_session()
    active_nav = st.session_state.get("cq_page", "dashboard")
    if st.session_state.get("cq_detail_id"):
        active_nav = "active"
    shell(active_nav, main_content)


if __name__ == "__main__":
    main()
