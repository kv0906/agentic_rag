"""FastAPI server: document upload + agentic RAG chat."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import iter_agent_events, run_agent
from orchestrator import iter_orchestrator_events, run_orchestrator
from rag import (
    DATA_DIR,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    clear_index,
    has_index,
    ingest_document,
    list_documents,
)

# Load .env from project root and backend/
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(
    title="Agentic RAG",
    description="LangGraph agent + LlamaIndex document retrieval (learning project)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    answer: str
    steps: list[dict]


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "has_documents": has_index(),
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/api/documents")
def get_documents():
    return {"documents": list_documents()}


@app.delete("/api/documents")
def delete_documents():
    clear_index()
    return {"ok": True, "documents": []}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    name = file.filename
    extension = Path(name).suffix.lower()
    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported extensions: {supported}",
        )

    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set. Add it to a .env file in the project root.",
        )

    # Safe on-disk name
    stem = re.sub(r"[^\w.\-]+", "_", Path(name).stem)[:80] or "document"
    saved = DATA_DIR / f"{stem}_{uuid.uuid4().hex[:8]}{extension}"

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 20MB)")
        saved.write_bytes(content)
        meta = ingest_document(saved, original_name=name)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surface ingestion errors to the UI
        if saved.exists():
            saved.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return {"ok": True, "document": meta, "documents": list_documents()}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set. Add it to a .env file in the project root.",
        )

    try:
        result = run_agent(body.message.strip())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Agent failed: {exc}") from exc

    return ChatResponse(answer=result["answer"], steps=result["steps"])


@app.post("/api/chat/stream")
def chat_stream(body: ChatRequest):
    """Server-Sent Events stream of agent phases + steps (live tool-call UX)."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set. Add it to a .env file in the project root.",
        )

    question = body.message.strip()

    def event_bytes():
        try:
            for event in iter_agent_events(question):
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_bytes(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/orchestrate", response_model=ChatResponse)
def orchestrate(body: ChatRequest):
    """Multi-agent path: orchestrator → ask_docs → agentic RAG specialist."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set. Add it to a .env file in the project root.",
        )

    try:
        result = run_orchestrator(body.message.strip())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Orchestrator failed: {exc}"
        ) from exc

    return ChatResponse(answer=result["answer"], steps=result["steps"])


@app.post("/api/orchestrate/stream")
def orchestrate_stream(body: ChatRequest):
    """SSE stream for orchestrator → ask_docs (same event shapes as /api/chat/stream)."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set. Add it to a .env file in the project root.",
        )

    question = body.message.strip()

    def event_bytes():
        try:
            for event in iter_orchestrator_events(question):
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_bytes(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
