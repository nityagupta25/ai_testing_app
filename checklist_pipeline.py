from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

SECTIONS = ["Functional", "UI", "Edge", "Regression", "Risk"]

LLM_KEY_TO_INTERNAL = {
    "functional_tests": "Functional",
    "ui_tests": "UI",
    "edge_cases": "Edge",
    "regression": "Regression",
    "risk_areas": "Risk",
    "Functional": "Functional",
    "UI": "UI",
    "Edge": "Edge",
    "Regression": "Regression",
    "Risk": "Risk",
}

TC_FIELDS = ["id", "test_summary", "description", "action", "data", "expected_result"]


def normalize_feature_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 2]


def _extract_flows(text: str, max_flows: int = 12) -> List[str]:
    sents = _split_sentences(text)
    flows: List[str] = []
    action_pat = re.compile(
        r"\b(validate|verify|ensure|handle|support|allow|block|"
        r"redirect|authenticate|authorize|submit|cancel|retry|parse)\b",
        re.I,
    )
    for s in sents:
        if action_pat.search(s) and len(s) < 200:
            flows.append(s[:160])
        if len(flows) >= max_flows:
            break
    if not flows and sents:
        flows = [s[:160] for s in sents[:5]]
    return flows[:max_flows]


def _extract_entities(text: str, max_entities: int = 20) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for m in re.finditer(r'"([^"]+)"|`([^`]+)`', text):
        val = (m.group(1) or m.group(2) or "").strip()
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text):
        val = m.group(0).strip()
        if val not in seen and len(val) < 48:
            seen.add(val)
            out.append(val)
    for m in re.finditer(
        r"\b(user|admin|session|token|api|endpoint|payload|header|cookie|oauth)\b",
        text, re.I,
    ):
        val = m.group(1).lower()
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out[:max_entities]


def url_analyzer(url: str) -> Dict[str, Any]:
    url = (url or "").strip()
    if not url:
        return {"raw": "", "host": "", "path": "", "hints": []}
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        p = urlparse(url)
    except Exception:
        return {"raw": url, "host": "", "path": "", "hints": ["unparsed URL"]}
    hints: List[str] = []
    host = (p.netloc or "").lower()
    path = (p.path or "").strip("/")
    if "staging" in host or "stage" in host:
        hints.append("staging environment")
    if "dev" in host or "localhost" in host:
        hints.append("development environment")
    if "api" in path or host.startswith("api."):
        hints.append("likely API surface")
    return {"raw": url, "host": host, "path": path, "hints": hints}


def parse_feature_input(
    feature_description: str,
    app_url: str = "",
    project_type: str = "API",
    extras: str = "",
) -> Dict[str, Any]:
    feat = normalize_feature_text(feature_description)
    flows = _extract_flows(feat)
    entities = _extract_entities(feat)
    url_info = url_analyzer(app_url)
    extras_n = normalize_feature_text(extras) if extras else ""
    ctx_parts = [f"{project_type.lower()} application context"]
    if url_info.get("hints"):
        ctx_parts.append("URL hints: " + ", ".join(url_info["hints"]))
    if extras_n:
        ctx_parts.append("Additional preferences: " + extras_n)
    return {
        "feature": feat[:2000],
        "flows": flows,
        "entities": entities,
        "context": "; ".join(ctx_parts),
        "url_analysis": url_info,
        "extras": extras_n,
    }


def build_scenario_seeds(structured: Dict[str, Any]) -> Dict[str, List[str]]:
    feat = structured.get("feature", "")
    flows = structured.get("flows") or []
    entities = structured.get("entities") or []
    ent_sample = ", ".join(entities[:8]) if entities else "core domain objects"
    seeds = {
        "Functional": [
            f"Verify primary behavior: {feat[:120]}",
            "Validate expected outputs for valid inputs across main flows",
            "Confirm integration points behave per contract",
        ],
        "UI": [
            "Verify visible states, labels, and feedback for main user actions",
            "Check validation and error presentation on the client",
            "UI/UX checks for applicable surfaces",
        ],
        "Edge": [
            "Boundary inputs (empty, max length, special characters)",
            "Concurrency / ordering where relevant",
            "Degraded modes: timeouts, partial failures",
        ],
        "Regression": [
            f"Regression on adjacent modules touching: {ent_sample}",
            "Existing APIs/screens still behave unchanged for unchanged inputs",
        ],
        "Risk": [
            "Data integrity and authorization around sensitive operations",
            "Operational risks (load spikes, dependency outages)",
            "Compliance or audit-relevant paths if applicable",
        ],
    }
    if flows:
        seeds["Functional"].insert(0, f"Cover flows: {flows[0][:140]}")
    return seeds


def _normalize_llm_payload(parsed: Any) -> Dict[str, List[str]]:
    if not isinstance(parsed, dict):
        return {k: [] for k in SECTIONS}
    out: Dict[str, List[str]] = {k: [] for k in SECTIONS}
    for raw_key, internal in LLM_KEY_TO_INTERNAL.items():
        if raw_key in parsed:
            val = parsed[raw_key]
            if isinstance(val, list):
                out[internal] = [str(x).strip() for x in val if str(x).strip()]
    for k in SECTIONS:
        if k in parsed and isinstance(parsed[k], list):
            out[k] = [str(x).strip() for x in parsed[k] if str(x).strip()]
    return out


def _normalize_structured_payload(parsed: Any) -> Dict[str, List[Dict]]:
    """Normalize structured test case payload from LLM."""
    if not isinstance(parsed, dict):
        return {k: [] for k in SECTIONS}
    out: Dict[str, List[Dict]] = {k: [] for k in SECTIONS}
    key_map = {
        "functional_tests": "Functional",
        "ui_tests": "UI",
        "edge_cases": "Edge",
        "regression": "Regression",
        "risk_areas": "Risk",
    }
    for llm_key, section in key_map.items():
        items = parsed.get(llm_key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    out[section].append({
                        "id": str(item.get("id", "")),
                        "test_summary": str(item.get("test_summary", "")),
                        "description": str(item.get("description", "")),
                        "action": str(item.get("action", "")),
                        "data": str(item.get("data", "N/A")),
                        "expected_result": str(item.get("expected_result", "")),
                    })
    return out


def build_llm_user_prompt(
    structured: Dict[str, Any],
    seeds: Dict[str, List[str]],
) -> str:
    url = structured.get("url_analysis") or {}
    extras = structured.get("extras") or ""
    project_context = structured.get("context", "").split(";")[0]
    return f"""You are a Senior Software QA Engineer with 10+ years of experience.

## Feature Description (MOST IMPORTANT — base ALL tests strictly on this)
{structured.get("feature", "")}

## Project Type
{project_context}

## Application URL Info
{json.dumps(url, ensure_ascii=False)}

## Additional Tester Notes
{extras or "(none)"}

## Strict Rules
- Every test case MUST directly reference specific elements from the feature description
- Mention exact UI elements, button names, links, flows, or behaviors
- Be precise and actionable
- Generate minimum 5 test cases per category
- Each test case must have all 6 fields filled in completely

## Output Format
Return ONLY valid JSON. Each category contains a list of test case objects with exactly these fields:
- id: sequential ID like "FN-001", "UI-001", "ED-001", "RG-001", "RK-001"
- test_summary: one line summary of what is being tested
- description: detailed description of the test case
- action: exact step-by-step actions the tester should perform
- data: test data to use (write "N/A" if not applicable)
- expected_result: what should happen after the action

{{
  "functional_tests": [
    {{
      "id": "FN-001",
      "test_summary": "Verify Report an Issue button click",
      "description": "Verify that clicking the Report an Issue button navigates to the correct URL",
      "action": "1. Click the ? icon on top right\\n2. Click Report an Issue (myIT) button",
      "data": "N/A",
      "expected_result": "The Report issue section opens at https://myit.siemens.com in a new tab"
    }}
  ],
  "ui_tests": [
    {{
      "id": "UI-001",
      "test_summary": "...",
      "description": "...",
      "action": "...",
      "data": "N/A",
      "expected_result": "..."
    }}
  ],
  "edge_cases": [
    {{
      "id": "ED-001",
      "test_summary": "...",
      "description": "...",
      "action": "...",
      "data": "...",
      "expected_result": "..."
    }}
  ],
  "regression": [
    {{
      "id": "RG-001",
      "test_summary": "...",
      "description": "...",
      "action": "...",
      "data": "N/A",
      "expected_result": "..."
    }}
  ],
  "risk_areas": [
    {{
      "id": "RK-001",
      "test_summary": "...",
      "description": "...",
      "action": "...",
      "data": "...",
      "expected_result": "..."
    }}
  ]
}}"""


def generate_checklist_with_openai(
    client: Any,
    structured: Dict[str, Any],
    seeds: Dict[str, List[str]],
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    user_prompt = build_llm_user_prompt(structured, seeds)
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "You are an expert QA engineer. Respond with clean JSON only. No markdown, no extra text."},
            {"role": "user", "content": user_prompt},
        ],
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    content = response.choices[0].message.content or "{}"
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    parsed = json.loads(content.strip())
    checklist = _normalize_structured_payload(parsed)
    meta = {"model": model, "generation_time_ms": elapsed_ms}
    return checklist, meta


def internal_to_api_checklist(checklist: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "functional_tests": checklist.get("Functional", []),
        "ui_tests": checklist.get("UI", []),
        "edge_cases": checklist.get("Edge", []),
        "regression": checklist.get("Regression", []),
        "risk_areas": checklist.get("Risk", []),
    }


def api_to_internal_checklist(data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, List] = {k: [] for k in SECTIONS}
    mapping = {
        "functional_tests": "Functional",
        "ui_tests": "UI",
        "edge_cases": "Edge",
        "regression": "Regression",
        "risk_areas": "Risk",
    }
    for api_key, internal in mapping.items():
        if api_key in data and isinstance(data[api_key], list):
            out[internal] = data[api_key]
    return out


def run_pipeline(
    feature_description: str,
    app_url: str = "",
    project_type: str = "API",
    extras: str = "",
    client: Any = None,
    model: str = "llama-3.3-70b-versatile",
) -> Dict[str, Any]:
    structured = parse_feature_input(
        feature_description, app_url=app_url, project_type=project_type, extras=extras
    )
    seeds = build_scenario_seeds(structured)
    if client is None:
        raise ValueError("Client is required for LLM step")
    checklist, meta = generate_checklist_with_openai(
        client, structured, seeds, model=model
    )
    return {
        "intermediate": structured,
        "seeds": seeds,
        "checklist": checklist,
        "meta": meta,
    }