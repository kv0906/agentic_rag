"""Minimal multi-agent demo: orchestrator → ask_docs → agentic RAG.

Architecture (learning sketch):

  You (UI or CLI)
   │
   ▼
  ┌─────────────────────────────┐
  │  Orchestrator (LangGraph)   │  decides: greet vs call tool
  │  tool: ask_docs(query)      │
  └─────────────┬───────────────┘
                │  same contract as POST /api/chat
                │  (local in-process by default; HTTP optional)
                ▼
  ┌─────────────────────────────┐
  │  Agentic RAG specialist     │  retrieve → grade → rewrite? → answer
  └─────────────────────────────┘

Run CLI (API must be up if RAG_ASK_DOCS_MODE=http):

  source .venv/bin/activate
  cd backend
  python orchestrator.py "What is a binary market?"

Env:
  RAG_API_URL          default http://127.0.0.1:8000  (HTTP mode only)
  RAG_ASK_DOCS_MODE    local (default) | http
  OPENAI_API_KEY / OPENAI_MODEL  same as the RAG agent
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

DEFAULT_CHAT_MODEL = "gpt-5.4-mini"
DEFAULT_RAG_API = "http://127.0.0.1:8000"
ASK_DOCS_TIMEOUT_S = 180

NODE_PHASES: dict[str, str] = {
    "orchestrator": "Orchestrator — decide whether to call ask_docs…",
    "tools": "Calling document specialist (ask_docs)…",
}


def _chat_model_name() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_CHAT_MODEL).strip() or DEFAULT_CHAT_MODEL


def _rag_api_base() -> str:
    return os.getenv("RAG_API_URL", DEFAULT_RAG_API).rstrip("/")


def _ask_docs_mode() -> str:
    """local = same process as /api/chat; http = real network call to RAG API."""
    return (os.getenv("RAG_ASK_DOCS_MODE") or "local").strip().lower()


@lru_cache(maxsize=1)
def _orchestrator_model():
    return init_chat_model(f"openai:{_chat_model_name()}", temperature=0)


# ---------------------------------------------------------------------------
# Specialist call — same payload shape as POST /api/chat
# ---------------------------------------------------------------------------


def _http_chat(query: str) -> dict[str, Any]:
    url = f"{_rag_api_base()}/api/chat"
    payload = json.dumps({"message": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=ASK_DOCS_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _local_chat(query: str) -> dict[str, Any]:
    # Same graph the FastAPI /api/chat route uses — capability boundary without
    # self-HTTP (which can stall a single-process server under load).
    from agent import run_agent

    return run_agent(query)


def invoke_docs_specialist(query: str) -> dict[str, Any]:
    """Call the agentic RAG specialist. Returns {answer, steps}."""
    mode = _ask_docs_mode()
    if mode == "http":
        return _http_chat(query)
    return _local_chat(query)


def _format_specialist_result(body: dict[str, Any]) -> str:
    answer = body.get("answer") or ""
    steps = body.get("steps") or []
    tool_bits: list[str] = []
    for step in steps:
        if step.get("type") == "tool" and step.get("tool_name"):
            tool_bits.append(str(step["tool_name"]))
        elif step.get("type") == "tool" and step.get("name"):
            tool_bits.append(str(step["name"]))
        elif step.get("tool_calls"):
            for tc in step["tool_calls"]:
                name = tc.get("name") if isinstance(tc, dict) else None
                if name:
                    tool_bits.append(str(name))
        # Surface rewrite node so the orchestrator UI path is richer
        if step.get("node") == "rewrite_question":
            tool_bits.append("rewrite_question")

    # Dedupe while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tool_bits:
        if t not in seen:
            seen.add(t)
            ordered.append(t)

    trace = " → ".join(ordered) if ordered else "(direct / no tools)"
    return f"[specialist steps: {trace}]\n\n{answer}"


@tool
def ask_docs(query: str) -> str:
    """Ask the document specialist about uploaded PDFs.

    Use this for any question that might be answered from the user's documents
    (definitions, workflows, screens, numbers, strategies). Pass a clear,
    self-contained question — the specialist has its own retrieval loop.
    Do NOT use for pure greetings or small talk.
    """
    try:
        body = invoke_docs_specialist(query)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return f"ask_docs failed (HTTP {exc.code}): {detail}"
    except urllib.error.URLError as exc:
        return (
            f"ask_docs could not reach the RAG API at {_rag_api_base()}/api/chat: "
            f"{exc.reason}. Is uvicorn running?"
        )
    except TimeoutError:
        return (
            f"ask_docs timed out after {ASK_DOCS_TIMEOUT_S}s "
            f"(mode={_ask_docs_mode()})"
        )
    except Exception as exc:  # noqa: BLE001 — surface to orchestrator LLM
        return f"ask_docs failed: {exc}"

    return _format_specialist_result(body)


# ---------------------------------------------------------------------------
# Orchestrator graph (decide → tool? → reply)
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are a lightweight orchestrator. You do NOT read PDFs yourself.\n"
    "For any document / playbook / product question, call ask_docs with a clear query.\n"
    "For greetings or meta questions about your role, reply briefly without tools.\n"
    "After ask_docs returns, give the user a clean final answer grounded in that result. "
    "You may lightly polish wording; do not invent facts the specialist did not provide."
)


def orchestrator_node(state: MessagesState) -> dict[str, Any]:
    messages = [{"role": "system", "content": SYSTEM}, *state["messages"]]
    response = _orchestrator_model().bind_tools([ask_docs]).invoke(messages)
    return {"messages": [response]}


def route_on_tool_calls(state: MessagesState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def build_orchestrator():
    g = StateGraph(MessagesState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("tools", ToolNode([ask_docs]))
    g.add_edge(START, "orchestrator")
    g.add_conditional_edges(
        "orchestrator",
        route_on_tool_calls,
        {"tools": "tools", END: END},
    )
    g.add_edge("tools", "orchestrator")
    return g.compile()


orchestrator = build_orchestrator()


def _message_to_step(node_name: str, msg: Any) -> dict[str, Any]:
    msg_type = getattr(msg, "type", None) or msg.__class__.__name__.lower()
    content = getattr(msg, "content", "") or ""
    if not isinstance(content, str):
        content = str(content)

    tool_calls = getattr(msg, "tool_calls", None) or []
    normalized_calls = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            normalized_calls.append(
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args") or {},
                }
            )
        else:
            normalized_calls.append(
                {
                    "id": getattr(tc, "id", None),
                    "name": getattr(tc, "name", None),
                    "args": getattr(tc, "args", {}) or {},
                }
            )

    step: dict[str, Any] = {
        "node": node_name,
        "type": msg_type,
        "content": content,
    }
    if normalized_calls:
        step["tool_calls"] = normalized_calls
    if msg_type == "tool":
        step["tool_name"] = getattr(msg, "name", "ask_docs")
        step["tool_call_id"] = getattr(msg, "tool_call_id", None)
    return step


def iter_orchestrator_events(question: str):
    """Yield UI events (same shapes as agent.iter_agent_events).

    Event shapes:
      {"type": "phase", "node": str, "label": str}
      {"type": "step", "step": {...}}
      {"type": "done", "answer": str, "steps": [...]}
      {"type": "error", "message": str}
    """
    steps: list[dict[str, Any]] = []
    final_answer = ""

    yield {
        "type": "phase",
        "node": "orchestrator",
        "label": NODE_PHASES["orchestrator"],
    }

    try:
        for event in orchestrator.stream(
            {"messages": [{"role": "user", "content": question}]},
            stream_mode="updates",
        ):
            for node_name, update in event.items():
                label = NODE_PHASES.get(node_name)
                if label:
                    yield {"type": "phase", "node": node_name, "label": label}

                messages = update.get("messages") or []
                for msg in messages:
                    step = _message_to_step(node_name, msg)
                    steps.append(step)
                    yield {"type": "step", "step": step}

                    if (
                        step["type"] in ("ai", "aimessage")
                        and step.get("content")
                        and not step.get("tool_calls")
                    ):
                        final_answer = step["content"]
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        return

    if not final_answer:
        for step in reversed(steps):
            if step["type"] in ("ai", "aimessage") and step.get("content"):
                final_answer = step["content"]
                break

    yield {
        "type": "done",
        "answer": final_answer or "I could not produce an answer.",
        "steps": steps,
    }


def run_orchestrator(question: str) -> dict[str, Any]:
    """Run one turn; return final answer + steps (API-friendly)."""
    answer = "I could not produce an answer."
    steps: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for event in iter_orchestrator_events(question):
        if event["type"] == "done":
            answer = event["answer"]
            steps = event["steps"]
        elif event["type"] == "error":
            raise RuntimeError(event["message"])
        elif event["type"] == "step":
            step = event["step"]
            if step.get("tool_calls"):
                for tc in step["tool_calls"]:
                    events.append(
                        {
                            "node": step.get("node"),
                            "event": "tool_call",
                            "tool": tc.get("name"),
                            "args": tc.get("args"),
                        }
                    )
            elif step.get("type") == "tool":
                content = step.get("content") or ""
                preview = content if len(content) <= 240 else content[:240] + "…"
                events.append(
                    {
                        "node": step.get("node"),
                        "event": "tool_result",
                        "tool": step.get("tool_name") or "tool",
                        "preview": preview,
                    }
                )
            elif step.get("content") and not step.get("tool_calls"):
                content = step["content"]
                events.append(
                    {
                        "node": step.get("node"),
                        "event": "ai",
                        "content": content if len(content) <= 200 else content[:200] + "…",
                    }
                )

    return {"answer": answer, "steps": steps, "events": events}


def _print_run(question: str) -> int:
    print("=" * 60)
    print("Orchestrator → ask_docs → Agentic RAG")
    print("=" * 60)
    print(f"Mode    : {_ask_docs_mode()}")
    if _ask_docs_mode() == "http":
        print(f"RAG API : {_rag_api_base()}")
    print(f"Model   : {_chat_model_name()}")
    print(f"Query   : {question}")
    print("-" * 60)

    if _ask_docs_mode() == "http":
        health_url = f"{_rag_api_base()}/api/health"
        try:
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                health = json.loads(resp.read().decode("utf-8"))
            print(
                f"Health  : ok={health.get('ok')} "
                f"docs={health.get('has_documents')} "
                f"key={health.get('openai_key_set')}"
            )
            if not health.get("has_documents"):
                print(
                    "Warning: no documents indexed. Upload a PDF via the UI "
                    "or POST /api/upload first."
                )
        except Exception as exc:  # noqa: BLE001
            print(f"Health  : FAILED ({exc})")
            print("Start the API first:  cd backend && uvicorn main:app --port 8000")
            return 1
    else:
        try:
            from rag import has_index

            print(f"Index   : has_documents={has_index()}")
        except Exception as exc:  # noqa: BLE001
            print(f"Index   : (could not check: {exc})")

    print("-" * 60)
    result = run_orchestrator(question)

    for i, ev in enumerate(result.get("events") or [], 1):
        if ev["event"] == "tool_call":
            print(f"[{i}] orchestrator calls {ev['tool']}({ev.get('args')})")
        elif ev["event"] == "tool_result":
            print(f"[{i}] {ev['tool']} → {ev['preview']!r}")
        elif ev["event"] == "ai":
            print(f"[{i}] ai: {ev['content']!r}")

    print("-" * 60)
    print("FINAL ANSWER")
    print(result["answer"] or "(empty)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]).strip() or "What is covered in the uploaded documents?"
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set (project root .env).", file=sys.stderr)
        sys.exit(1)
    # CLI defaults to HTTP so it exercises the real API boundary when API is up
    if not os.getenv("RAG_ASK_DOCS_MODE"):
        os.environ["RAG_ASK_DOCS_MODE"] = "http"
    raise SystemExit(_print_run(q))
