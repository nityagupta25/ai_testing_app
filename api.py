"""
FastAPI layer (Problem Statement §4.3): POST /generate-checklist
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field

from checklist_pipeline import (
    internal_to_api_checklist,
    run_pipeline,
)

app = FastAPI(title="AI Testing Checklist API", version="1.0.0")


def _get_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server.",
        )
    return OpenAI(api_key=key)


class GenerateRequest(BaseModel):
    feature: str = Field(..., description="Feature description / requirements")
    url: str = Field("", description="Optional application URL")
    project_type: str = Field("API", description="e.g. API, Web, Mobile, Backend")
    extras: str = Field(
        "",
        description="Optional preferences (e.g. high traffic, quick service)",
    )


class GenerateResponse(BaseModel):
    checklist: Dict[str, List[str]]
    meta: Dict[str, Any]
    intermediate: Optional[Dict[str, Any]] = None
    seeds: Optional[Dict[str, List[str]]] = None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/generate-checklist", response_model=GenerateResponse)
def generate_checklist(body: GenerateRequest) -> GenerateResponse:
    if not body.feature or not body.feature.strip():
        raise HTTPException(status_code=400, detail="feature is required")
    client = _get_client()
    try:
        result = run_pipeline(
            feature_description=body.feature.strip(),
            app_url=(body.url or "").strip(),
            project_type=(body.project_type or "API").strip(),
            extras=(body.extras or "").strip(),
            client=client,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e!s}") from e

    internal = result["checklist"]
    api_shape = internal_to_api_checklist(internal)
    raw_meta = result.get("meta") or {}
    return GenerateResponse(
        checklist=api_shape,
        meta={
            "model": raw_meta.get("model", "gpt-4o-mini"),
            "generation_time_ms": raw_meta.get("generation_time_ms", 0),
        },
        intermediate=result.get("intermediate"),
        seeds=result.get("seeds"),
    )
