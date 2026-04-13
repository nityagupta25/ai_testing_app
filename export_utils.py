"""Export checklist to Excel, Word, Jira-shaped JSON, TestRail CSV."""

from __future__ import annotations

import io
import json
from typing import Dict, List

import pandas as pd

from checklist_pipeline import SECTIONS


def checklist_to_df(checklist: Dict[str, List[str]]) -> pd.DataFrame:
    rows = []
    for section in SECTIONS:
        for idx, test_case in enumerate(checklist.get(section, []), start=1):
            rows.append(
                {"Section": section, "Test Case #": idx, "Test Case": test_case}
            )
    return pd.DataFrame(rows)


def checklist_to_excel_bytes(checklist: Dict[str, List[str]]) -> bytes:
    df = checklist_to_df(checklist)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Checklist")
    return buf.getvalue()


def checklist_to_docx_bytes(
    checklist: Dict[str, List[str]], title: str = "AI Testing Checklist"
) -> bytes:
    from docx import Document

    doc = Document()
    doc.add_heading(title, 0)
    for section in SECTIONS:
        items = checklist.get(section, [])
        if not items:
            continue
        doc.add_heading(section, level=1)
        for item in items:
            doc.add_paragraph(item, style="List Bullet")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def checklist_to_jira_json_bytes(
    checklist: Dict[str, List[str]], summary: str = "Generated test checklist"
) -> bytes:
    """Minimal Jira-import-friendly structure (customize for your Jira CSV/JSON importer)."""
    issues = []
    n = 0
    for section in SECTIONS:
        for item in checklist.get(section, []):
            n += 1
            issues.append(
                {
                    "summary": f"[{section}] {item[:200]}",
                    "description": item,
                    "labels": ["ai-checklist", section.lower().replace(" ", "-")],
                }
            )
    payload = {
        "source": "CoverIQ AI Checklist",
        "summary": summary,
        "issues": issues,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def checklist_to_testrail_csv_bytes(checklist: Dict[str, List[str]]) -> bytes:
    """TestRail-style flat CSV: Section, Title, Type."""
    rows = []
    for section in SECTIONS:
        for item in checklist.get(section, []):
            rows.append(
                {
                    "section": section,
                    "title": item,
                    "type": "Functional",
                }
            )
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")
