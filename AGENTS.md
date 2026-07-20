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
6. **Hard concepts:** life analogy first (e.g. book + box size for chunking), then the diagram, then jargon. Vietnamese is fine when Van asks (`giải thích tiếng Việt`).
7. **Locked mental models** live under `docs/learning/` (hub: `docs/learning/README.md`). Especially [07-chunking.md](docs/learning/07-chunking.md) Ch. 20–21 (chunking) and [08-agent-evals.md](docs/learning/08-agent-evals.md) Ch. 22–23 (evals). Reuse those explainers; don’t reinvent a denser version. When picking a splitter, open Ch. 21; when designing agent evals, open Ch. 22–23 first.

### Core eval philosophy (locked — Ch. 23)

**Human understands intention, goal, and direction → harness the system toward TRUST and RELIABILITY.**

- Humans define what “good” means; evals **encode** that judgment — they do not replace it.
- Harness = goldens, asserts, traces, CI gates, canaries, review loops.
- Measure with six categories (Ch. 22): outcome, process, grounding, safety, efficiency, UX.
- Full write-up: `docs/learning/08-agent-evals.md`.


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

- Study path (hub): `docs/learning/README.md`
- Topics: `docs/learning/01-foundation.md` … `08-agent-evals.md` (by theme; chapter numbers preserved)
- Legacy redirect: `docs/LEARNING_JOURNEY.md` → hub
- Runbook: `README.md`
- When a session produces a new “aha” mental model, **add a chapter to the right topic file** under `docs/learning/`, link it from the hub README, and append the question index.

## Stack reminder (one-liner)

```
UI (Astryx) → FastAPI → LangGraph agent loop → tool → LlamaIndex retrieve
Ingest: pypdf → LlamaIndex chunk/embed → in-memory VectorStoreIndex
```

## Astryx UI

See `.claude/CLAUDE.md` (Astryx block). Prefer `npx astryx build/component/template` over inventing layout.
