# Agent instructions — agentic-rag

Project-specific guidance for AI coding agents working in this repo.

## How Van learns (prefer this style)

Van learns systems best through **plain language + ASCII diagrams**, not long walls of prose or jargon-first explanations.

When explaining architecture, RAG, LangGraph, LlamaIndex, chunking, loops, tradeoffs, or “how does X work”:

1. **Lead with an ASCII visualization** (boxes, arrows, before/after, side-by-side).
2. Follow with a **short** plain-English caption (1–3 sentences).
3. Use a **small table** only when comparing options (memory vs DB, who owns what).
4. Point to **concrete files** (`backend/agent.py`, `backend/rag.py`) after the picture.
5. Prefer “CEO level” / human-readable first when asked how something works; add node/edge detail only if requested.

### ASCII style that works well here

```
Good:  show flow, split paths, before/after, ownership boxes

  Without overlap          With overlap
  ──────────────           ────────────
  [====]|[====]            [====]
                             [==|====]

  decide ──tool?──► retrieve ──grade──► answer
                      │           no
                      └◄─ rewrite ┘
```

Avoid dense paragraphs that restate the same diagram twice. **Less is more** — one clear picture beats three sections of text.

### Learning docs in this repo

- Study path / Q&A journey: `docs/LEARNING_JOURNEY.md`
- Runbook: `README.md`
- When a session produces a new “aha” mental model, **update `docs/LEARNING_JOURNEY.md`** (and link from README if it’s a new chapter).

## Stack reminder (one-liner)

```
UI (Astryx) → FastAPI → LangGraph agent loop → tool → LlamaIndex retrieve
Ingest: pypdf → LlamaIndex chunk/embed → in-memory VectorStoreIndex
```

## Astryx UI

See `.claude/CLAUDE.md` (Astryx block). Prefer `npx astryx build/component/template` over inventing layout.
