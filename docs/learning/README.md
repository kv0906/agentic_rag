# Learning hub — Agentic RAG

This folder is the **study path** for the repo: questions, mental models, and code anchors.  
Split by topic so files stay readable. Older link: [`docs/LEARNING_JOURNEY.md`](../LEARNING_JOURNEY.md) redirects here.

**Preferred teaching style** (see root `AGENTS.md`): plain language + **ASCII first**, short captions — not jargon walls. Hard concepts: life analogy → diagram → terms; Vietnamese OK when asked.

## Code anchors

| Area | Path |
|------|------|
| Agent (LangGraph) | `backend/agent.py` |
| Retrieval (LlamaIndex hybrid) | `backend/rag.py` |
| API | `backend/main.py` |
| Chat UI | `src/app/ai-chat/page.tsx` |
| Stream client | `src/lib/api.ts` |
| Citations UX | `src/lib/citations.ts`, `src/components/SourceCitations.tsx` |
| Golden set + Ragas | `eval/golden.jsonl`, `eval/run_ragas.py`, `eval/README.md` |

## Topics (read in order)

| # | File | Chapters | About |
|---|------|----------|--------|
| 1 | [01-foundation.md](./01-foundation.md) | 1–5 | Build app, system flow, LlamaIndex role, memory vs DB |
| 2 | [02-agent-loop.md](./02-agent-loop.md) | 6–8 | LangGraph, grade/rewrite loop |
| 3 | [03-retrieval-basics.md](./03-retrieval-basics.md) | 9–10 | Embed/index/search, score vs grade |
| 4 | [04-hybrid-search.md](./04-hybrid-search.md) | 11–12 | Vector + BM25 + RRF, multi-retriever |
| 5 | [05-ship-eval-polish.md](./05-ship-eval-polish.md) | 13–17 | 2026 practices, eval, polish, gap fixes |
| 6 | [06-rerank.md](./06-rerank.md) | 18 | Cross-encoder rerank |
| 7 | [07-chunking.md](./07-chunking.md) | 19–21 | Contextual, recursive (VI+ASCII), **doc↔chunking tables** |
| 8 | [08-agent-evals.md](./08-agent-evals.md) | 22–23 | Eval **philosophy** + **six categories** |

### Jump to locked mental models

| Need | Open |
|------|------|
| Recursive chunking (easy VI + ASCII) | [07-chunking.md](./07-chunking.md) § Ch. 20 |
| Doc type → which chunking? | [07-chunking.md](./07-chunking.md) § Ch. 21 |
| Contextual Retrieval labels | [07-chunking.md](./07-chunking.md) § Ch. 19 |
| Hybrid + RRF | [04-hybrid-search.md](./04-hybrid-search.md) |
| Rerank / cross-encoder | [06-rerank.md](./06-rerank.md) |
| **Core eval philosophy** (intention → trust) | [08-agent-evals.md](./08-agent-evals.md) § **Ch. 23** |
| Agent eval categories (outcome…UX) | [08-agent-evals.md](./08-agent-evals.md) § Ch. 22 |

## Journey map (high level)

```
  Build the app
       │
       ▼
  See the whole system (ingest + agent + UI)
       │
       ▼
  Who does what?  LlamaIndex vs LangGraph
       │
       ▼
  Where do vectors live?  Memory vs DB
       │
       ▼
  How does the agent loop work?
       │
       ▼
  How does grade decide "good enough"?  (LLM-as-judge)
       │
       ▼
  Deepen LlamaIndex (embed → index → search)
       │
       ▼
  score vs grade vs answer
       │
       ▼
  Hybrid search: vector + BM25 + RRF
       │
       ▼
  Multi-retriever / 2026 practices / eval + polish
       │
       ▼
  Tier-2 cross-encoder rerank
       │
       ▼
  Contextual Retrieval
       │
       ▼
  Chunking ladder + recursive model + doc-type tables
       │
       ▼
  Agent eval: philosophy (trust/reliability) + 6 categories
```

## Suggested re-read order

1. This hub → topic files in table order (or jump via locked models)  
2. Root `README.md` (how to run)  
3. `backend/rag.py` — hybrid + CE + `MAX_PASSAGE_CHARS`  
4. `backend/agent.py` — prompts (decide / grade / rewrite / generate)  
5. `src/lib/citations.ts` + chat page (Sources UX)  
6. `eval/README.md` + `python eval/trace_rag.py --ids q06`  

**UI smoke:** re-upload PDF after restart → ask playbook Q → expect `(p. N)` cites + Sources tokens + next-step questions.  
**Targeted smoke:** `python eval/run_ragas.py --ids q02,q06 --skip-ragas`  
**Step-by-step retrieve log:** `python eval/trace_rag.py --ids q06`  
(replay old bug: `--cap 800`; full graph: `--agent`; JSON: `--json /tmp/t.json`)

## Open learning next steps (not built unless you ask)

### Done this arc
- [x] Hybrid search (vector + BM25 + RRF)  
- [x] Multi-retriever fuse vs compare (concept)  
- [x] 2026 retrieval best practices (concept)  
- [x] Tier-1 defaults (top_k≈8, grade/rewrite)  
- [x] Golden set (25) + Ragas harness + baseline run  
- [x] Page citations + Sources UI  
- [x] Coach-style answer + next steps  
- [x] Model → gpt-5.4-mini  
- [x] Fix q02 force-retrieve + q06 Live/Approved (truncation + prompts)  
- [x] Re-run Ragas after those tweaks  
- [x] Tier-2 cross-encoder **rerank** after hybrid  
- [x] Contextual Retrieval notes (Ch. 19)  
- [x] Recursive + doc↔chunking reference (Ch. 20–21)  
- [x] Split learning log into `docs/learning/` by topic  
- [x] Agent eval foundation categories (Ch. 22 / `08-agent-evals.md`)  
- [x] Core eval philosophy: intention/goal/direction → harness → trust & reliability (Ch. 23)  

### Next sessions (priority order)
- [ ] Optional: tighten **q04** / **q15** answer must_haves (wording / Group 1 numbers)  
- [ ] Re-run Ragas after CE (compare factual_correctness vs hybrid-only)  
- [ ] Persist index (disk / vector DB)  
- [ ] Optional: click source token → expand passage preview  
- [ ] Multi-PDF metadata filters  
- [ ] Token-level answer streaming  
- [ ] Local models (Ollama) if cost/privacy matters  
- [ ] Optional: agentic chunking experiment (only if eval shows boundary misses)  

## How to extend

When a session produces a new “aha” mental model:

1. Add a new **Chapter N** section to the right topic file (or create `08-….md` if it is a new theme).
2. Link it from this README (Topics table + jump table if it is a locked model).
3. Append the question to the chronological index below.
4. Keep ASCII + plain language; update root `AGENTS.md` only if agents should open it by default.

Stack one-liner:

```
UI (Astryx) → FastAPI → LangGraph agent loop → tool → LlamaIndex retrieve
Ingest: pypdf → LlamaIndex chunk/embed → in-memory VectorStoreIndex
```

## Question index (chronological)

1. Build simple agentic RAG (LangGraph + LlamaIndex + PDF + Astryx)  
2. Use LangGraph custom RAG agent tutorial pattern  
3. Scaffold UI with `astryx template ai-chat`  
4. Rebuild local after updating `.env`  
5. Optimize UX: loading / streaming during reasoning and tool calls  
6. ASCII: overall RAG information flow  
7. Do we use LlamaIndex if pypdf extracts text?  
8. What does LlamaIndex handle — retriever vs tool call?  
9. Does LangGraph call LlamaIndex as a tool-node?  
10. Where is the vector store — memory or database?  
11. Tradeoffs: memory vs vector DB  
12. Learning report of what we built  
13. LangGraph local map: nodes, tools, conditional edges (ASCII)  
14. Same flow in CEO / human language  
15. Is the loop already handled?  
16. Does LangGraph support that loop?  
17. Is the loop controlled via grade?  
18. How does grade know “search good enough”?  
19. Is grade LLM-as-a-judge?  
20. Document this journey in the repo (learning hub)  
21. What is LlamaIndex’s role? (vector search SDK)  
22. Confirm: search over docs in vector space?  
23. Show code for embed → index → retrieve  
24. What is retrieval `score`? How chunks reach grade/answer?  
25. Foundation solid — start advanced track  
26. Hybrid is not in the code yet (clarify before learning)  
27. Learn hybrid: BM25 + vector to upgrade search  
28. Is BM25 a lib / LlamaIndex / LangGraph? Implement + learn  
29. Align with official LlamaIndex BM25 + hybrid docs  
30. Stemmer + QueryFusionRetriever (PO explanation)  
31. Real QueryFusionRetriever / RRF sample (E-4412)  
32. Confirm: fuse to one list, higher score = top candidate?  
33. Why `1/(60+rank)`? What is 60? (still absorbing — OK)  
34. Document hybrid session  
35. Multi-retriever idea: each logic + compare — possible?  
36. 2026 best practices: speed · cost · effective balance  
37. Document multi-retriever + 2026 practices (Ch. 12–13)  
38. Ship DO NOW defaults (top_k=8)  
39. How to eval / ensure correctness?  
40. Golden set for Huua MMBot Playbook PDF  
41. Use Ragas on our agentic RAG + golden set  
42. Ragas UI or CLI? (CLI + reports)  
43. Manual answer list for all 25 Qs  
44. Better citation UX (page/document, not Chunk N)  
45. Model → gpt-5.4-mini  
46. Core system prompts inventory  
47. Coach voice: explain + related next steps  
48. Finalize learning log for the day (Ch. 14–16)  
49. Fix q02 (force retrieve on terms) + q06 (Live/Approved vs Active/Inactive)  
50. Re-run Ragas; document Ch. 17 (truncation aha + score delta)  
51. Clarify: 800/2000 = max **characters** per passage (packaging ≠ rank)  
52. Lock Ch. 17 walkthrough Bước 1–6 (ASCII) as project teaching memory  
53. Implement Tier-2 cross-encoder rerank (Ch. 18)  
54. Document CEO/PM explainer: rerank, cross-encoder, why local HF model  
55. Contextual Retrieval (Ch. 19) — situating context at ingest  
56. Chunking ladder (fixed / recursive / semantic / agentic) — study notes  
57. Recursive chunking mental model in VI + ASCII (Ch. 20) — teaching memory  
58. Doc type ↔ chunking strategy case tables (Ch. 21) — reference when picking a splitter  
59. Split learning log into `docs/learning/` by topic  
60. Agent eval foundation: six categories (outcome, process, grounding, safety, efficiency, UX) — Ch. 22  
61. Core philosophy: human intention/goal/direction → harness → trust & reliability — Ch. 23  

---

*Split from monolithic `LEARNING_JOURNEY.md` for readability. Chapter numbers preserved across files.*  
*Last updated: Ch. 23 core eval philosophy + Ch. 22 six categories (`08-agent-evals.md`).*
