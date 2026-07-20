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
6. Switch **Orchestrator** in the composer — a second LangGraph agent calls `ask_docs` → the same agentic RAG specialist (`POST /api/orchestrate/stream`).

### Multi-agent (orchestrator) CLI

With the API running:

```bash
source .venv/bin/activate
cd backend
python orchestrator.py "What is a binary market?"
```

## Project layout

```
backend/
  main.py              # FastAPI routes (+ orchestrate stream)
  rag.py               # PDF ingest, hybrid retrieve, CE rerank, optional contextual
  agent.py             # LangGraph agentic RAG graph
  orchestrator.py      # Multi-agent: ask_docs → specialist RAG
eval/
  golden.jsonl         # Task / must-have checklist
  run_ragas.py         # Offline eval harness
  trace_rag.py         # Step-by-step retrieve debug
  README.md            # How to run evals
docs/
  learning/            # Study path (topic files) — start at README.md
  LEARNING_JOURNEY.md  # Redirect stub → docs/learning/
src/
  app/ai-chat/         # Astryx chat UI (wired to RAG + orchestrator)
  lib/api.ts           # Client → API
  lib/citations.ts     # Page / source citation helpers
AGENTS.md              # How agents should teach & where locked models live
```

## Eval (offline)

```bash
source .venv/bin/activate
# Full-ish run (see eval/README.md for flags)
python eval/run_ragas.py
# Debug one case
python eval/trace_rag.py --ids q06
```

Details: **[eval/README.md](eval/README.md)**.

Agent quality is multi-dimensional (outcome · process · grounding · safety · efficiency · UX) — philosophy + categories in **[docs/learning/08-agent-evals.md](docs/learning/08-agent-evals.md)**.

## Astryx

```bash
npx astryx init --all                      # agent docs → .claude/CLAUDE.md
npx astryx template ai-chat ./src/app/ai-chat   # scaffold this chat UI
npx astryx build "<idea>"                  # composition kit
npx astryx component Chat                  # component API
```

Imports: `@astryxdesign/core/reset.css`, `astryx.css`, `@astryxdesign/theme-neutral/theme.css` + `<Theme theme={neutralTheme}>`.

## Learning hub

Study path from building this app (LlamaIndex vs LangGraph, hybrid, rerank, chunking, evals, …), split by topic:

→ **[docs/learning/README.md](docs/learning/README.md)**  
→ Old monolith path: [`docs/LEARNING_JOURNEY.md`](docs/LEARNING_JOURNEY.md) redirects here.

| Topic | File |
|-------|------|
| Foundation (Ch. 1–5) | [docs/learning/01-foundation.md](docs/learning/01-foundation.md) |
| Agent loop (Ch. 6–8) | [docs/learning/02-agent-loop.md](docs/learning/02-agent-loop.md) |
| Retrieval basics (Ch. 9–10) | [docs/learning/03-retrieval-basics.md](docs/learning/03-retrieval-basics.md) |
| Hybrid search (Ch. 11–12) | [docs/learning/04-hybrid-search.md](docs/learning/04-hybrid-search.md) |
| Ship / eval / polish (Ch. 13–17) | [docs/learning/05-ship-eval-polish.md](docs/learning/05-ship-eval-polish.md) |
| Rerank (Ch. 18) | [docs/learning/06-rerank.md](docs/learning/06-rerank.md) |
| Chunking (Ch. 19–21) | [docs/learning/07-chunking.md](docs/learning/07-chunking.md) |
| Agent evals (Ch. 22–23) | [docs/learning/08-agent-evals.md](docs/learning/08-agent-evals.md) |

**Locked jump-ins:** recursive chunking (Ch. 20), doc↔chunking tables (Ch. 21), eval philosophy intention→trust (Ch. 23).

Teaching style (ASCII-first, etc.): **[AGENTS.md](AGENTS.md)**

## Learn next

- ~~Cross-encoder **rerank** after hybrid~~ — **shipped** (`RAG_RERANK=0` to skip).
- ~~Contextual Retrieval at ingest~~ — **shipped for learning** (`RAG_CONTEXTUAL=1`; see `backend/rag.py`).
- ~~Learning log split by topic~~ — **shipped** (`docs/learning/`).
- Persist the vector index (disk or Chroma / Qdrant) instead of memory-only.
- Stricter grade (answerable-from-context only, or min similarity).
- Token-level LLM streaming on top of step SSE.
- Swap OpenAI for a local model (Ollama) on both LLM and embeddings.
- Optional: agentic chunking only if eval shows boundary misses (see Ch. 21).
