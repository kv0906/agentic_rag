# Agentic RAG (learning project)

A minimal **agentic RAG** app so you can see how the pieces fit:

| Layer | Role |
|--------|------|
| **LlamaIndex** | PDF load → chunk → embed → hybrid retrieve (vector + BM25 → RRF → cross-encoder rerank) |
| **LangGraph** | Agent graph: decide → retrieve → grade → rewrite (loop) → answer |
| **Astryx + Next.js** | Upload + chat UI (tool calls visible) |
| **FastAPI** | Glue API (`/api/upload`, `/api/chat`) |

Based on the [LangGraph custom RAG agent tutorial](https://docs.langchain.com/oss/python/langgraph/agentic-rag), with **PDF upload** instead of scraping blog posts, and **LlamaIndex** as the retriever.

## How the agent works

```
                 ┌──────────────────────────┐
                 │ generate_query_or_respond│
                 │  (LLM + retrieve tool)   │
                 └────────────┬─────────────┘
                    tool?     │     no tool
                 ┌────────────┘             └──► END (direct reply)
                 ▼
           ┌──────────┐
           │ retrieve │  ← hybrid (vector+BM25→RRF) → CE rerank
           └────┬─────┘
                ▼
        ┌───────────────┐
        │ grade_docs    │  yes → generate_answer → END
        │ (relevant?)   │  no  → rewrite_question ─┐
        └───────────────┘                          │
                ▲                                  │
                └──────────────────────────────────┘
```

1. **Decide** — model either greets / answers without docs, or calls `retrieve_documents`.
2. **Retrieve** — Hybrid search (vector + BM25 → RRF wide shortlist → cross-encoder rerank) returns top-k PDF chunks.
3. **Grade** — structured yes/no relevance check.
4. **Rewrite** — if chunks are weak, improve the question and retrieve again.
5. **Answer** — final grounded response.

## Prerequisites

- Node.js 20+
- Python 3.11+
- OpenAI API key (embeddings + chat)

## Setup

```bash
# 1) Frontend deps (Astryx already listed)
npm install

# 2) Backend venv
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 3) Env
cp .env.example .env
# edit .env → set OPENAI_API_KEY
```

## Run (two terminals)

```bash
# Terminal A — API (LangGraph + LlamaIndex)
source .venv/bin/activate
cd backend && uvicorn main:app --reload --port 8000

# Terminal B — UI
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) (redirects to `/ai-chat`).

Next.js rewrites `/api/*` → `http://127.0.0.1:8000/api/*`.

## Try it

1. Upload a short PDF via the paperclip on the Astryx chat composer.
2. Ask something that needs the doc (“What is section 2 about?”).
3. Watch tool calls: `retrieve_documents`, optional `rewrite_question`, then the answer.
4. Say “hello” — the agent can reply **without** retrieving.
5. Open the side panel for indexed docs + how the graph works.

## Project layout

```
backend/
  main.py              # FastAPI routes
  rag.py               # LlamaIndex PDF ingestion + retrieve()
  agent.py             # LangGraph graph (tutorial-shaped)
src/
  app/
    ai-chat/page.tsx   # Astryx ai-chat template (wired to RAG)
    layout.tsx         # Theme + CSS
  lib/api.ts           # Client → API
```

## Astryx

```bash
npx astryx init --all                      # agent docs → .claude/CLAUDE.md
npx astryx template ai-chat ./src/app/ai-chat   # scaffold this chat UI
npx astryx build "<idea>"                  # composition kit
npx astryx component Chat                  # component API
```

Imports: `@astryxdesign/core/reset.css`, `astryx.css`, `@astryxdesign/theme-neutral/theme.css` + `<Theme theme={neutralTheme}>`.

## Learning journey

Questions asked while building this app (what LlamaIndex vs LangGraph do, where vectors live, how grade/LLM-as-judge works, etc.) are documented as a study path:

→ **[docs/LEARNING_JOURNEY.md](docs/LEARNING_JOURNEY.md)**

Agent/teaching preferences (ASCII-first explanations): **[AGENTS.md](AGENTS.md)**

## Learn next

- ~~Optional cross-encoder **rerank** after hybrid~~ — **shipped** (default on; `RAG_RERANK=0` to skip).
- Persist the vector index (disk or Chroma / Qdrant) instead of memory-only.
- Stricter grade (answerable-from-context only, or min similarity).
- Token-level LLM streaming on top of step SSE.
- Swap OpenAI for a local model (Ollama) on both LLM and embeddings.
