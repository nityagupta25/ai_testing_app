"""
Phased checklist generation (Problem Statement Phases 1–3).

Phase 1 — Input processing: structured feature representation.
Phase 2 — Scenario seeds: category hints for the LLM.
Phase 3 — LLM call: normalized checklist + metadata.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Internal section keys (UI + storage)
SECTIONS = ["Functional", "UI", "Edge", "Regression", "Risk"]

# LLM output keys (problem statement §3.4) → internal keys
LLM_KEY_TO_INTERNAL = {
    "functional_tests": "Functional",
    "ui_tests": "UI",
    "edge_cases": "Edge",
    "regression": "Regression",
    "risk_areas": "Risk",
    # Aliases from older prompts
    "Functional": "Functional",
    "UI": "UI",
    "Edge": "Edge",
    "Regression": "Regression",
    "Risk": "Risk",
}


def normalize_feature_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 2]


def _extract_flows(text: str, max_flows: int = 12) -> List[str]:
    """Heuristic workflow phrases from requirements."""
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
    """Named-like tokens and quoted strings."""
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
        text,
        re.I,
    ):
        val = m.group(1).lower()
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out[:max_entities]


def url_analyzer(url: str) -> Dict[str, Any]:
    """Optional URL context (hostname, scheme, path hints)."""
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
    """
    Phase 1 output — intermediate schema (problem statement §1.4).

    Returns a JSON-serializable dict: feature, flows, entities, context, url_analysis, extras.
    """
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
    """
    Phase 2 — lightweight scenario seeds per category (deterministic, no LLM).
    Fed into the prompt as priors for categorization.
    """
    feat = structured.get("feature", "")
    flows = structured.get("flows") or []
    entities = structured.get("entities") or []
    ent_sample = ", ".join(entities[:8]) if entities else "core domain objects"

    seeds = {
        "Functional": [
            f"Verify primary behavior described in: {feat[:120]}..." if len(feat) > 120 else f"Verify primary behavior: {feat}",
            "Validate expected outputs for valid inputs across main flows",
            "Confirm integration points behave per contract",
        ],
        "UI": [
            "Verify visible states, labels, and feedback for main user actions",
            "Check validation and error presentation on the client",
            "Responsive / layout checks for target viewports" if "web" in structured.get("context", "").lower() else "UI/UX checks for applicable surfaces",
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
    # If model returned only internal keys
    for k in SECTIONS:
        if k in parsed and isinstance(parsed[k], list):
            out[k] = [str(x).strip() for x in parsed[k] if str(x).strip()]
    return out


def build_llm_user_prompt(
    structured: Dict[str, Any],
    seeds: Dict[str, List[str]],
) -> str:
    url = structured.get("url_analysis") or {}
    extras = structured.get("extras") or ""
    return f"""You are an expert QA engineer generating complete test coverage.

## Feature (normalized)
{structured.get("feature", "")}

## Extracted flows (heuristic)
{json.dumps(structured.get("flows", []), ensure_ascii=False)}

## Extracted entities (heuristic)
{json.dumps(structured.get("entities", []), ensure_ascii=False)}

## Context
{structured.get("context", "")}

## URL analysis (optional)
{json.dumps(url, ensure_ascii=False)}

## Additional tester preferences
{extras or "(none)"}

## Scenario seeds (use as inspiration; refine and extend)
{json.dumps(seeds, ensure_ascii=False)}

Return ONLY valid JSON with exactly these keys and string arrays (five items each when possible):
{{
  "functional_tests": ["...", "..."],
  "ui_tests": ["...", "..."],
  "edge_cases": ["...", "..."],
  "regression": ["...", "..."],
  "risk_areas": ["...", "..."]
}}

Rules:
- Concise, actionable, one line per test case
- No markdown, no numbering prefix in strings
- Align tests with the feature and project context
"""


def generate_checklist_with_openai(
    client: Any,
    structured: Dict[str, Any],
    seeds: Dict[str, List[str]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
    """Phase 3 — single LLM call; returns checklist + meta."""
    user_prompt = build_llm_user_prompt(structured, seeds)
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "You are an expert QA engineer. Respond with clean JSON only.",
            },
            {"role": "user", "content": user_prompt},
        ],
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    checklist = _normalize_llm_payload(parsed)
    meta = {
        "model": model,
        "generation_time_ms": elapsed_ms,
    }
    return checklist, meta


def internal_to_api_checklist(checklist: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Map internal keys to problem-statement API / §3.4 JSON shape."""
    return {
        "functional_tests": checklist.get("Functional", []),
        "ui_tests": checklist.get("UI", []),
        "edge_cases": checklist.get("Edge", []),
        "regression": checklist.get("Regression", []),
        "risk_areas": checklist.get("Risk", []),
    }


def api_to_internal_checklist(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Accept API-shaped body and normalize to internal SECTIONS."""
    out: Dict[str, List[str]] = {k: [] for k in SECTIONS}
    mapping = {
        "functional_tests": "Functional",
        "ui_tests": "UI",
        "edge_cases": "Edge",
        "regression": "Regression",
        "risk_areas": "Risk",
    }
    for api_key, internal in mapping.items():
        if api_key in data and isinstance(data[api_key], list):
            out[internal] = [str(x).strip() for x in data[api_key] if str(x).strip()]
    for k in SECTIONS:
        if k in data and isinstance(data[k], list):
            out[k] = [str(x).strip() for x in data[k] if str(x).strip()]
    return out


def run_pipeline(
    feature_description: str,
    app_url: str = "",
    project_type: str = "API",
    extras: str = "",
    client: Any = None,
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    End-to-end Phases 1–3. Requires OpenAI client for Phase 3.

    Returns:
      intermediate (phase 1),
      seeds (phase 2),
      checklist (internal section keys),
      meta (model, timing)
    """
    structured = parse_feature_input(
        feature_description, app_url=app_url, project_type=project_type, extras=extras
    )
    seeds = build_scenario_seeds(structured)
    if client is None:
        raise ValueError("OpenAI client is required for LLM step")
    checklist, meta = generate_checklist_with_openai(
        client, structured, seeds, model=model
    )
    return {
        "intermediate": structured,
        "seeds": seeds,
        "checklist": checklist,
        "meta": meta,
    }
