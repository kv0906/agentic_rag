# Learning journey: Agentic RAG

This document captures the questions asked while building and understanding this repo, in order, as a study path.  
It is not a product spec — it is a **learning log** tied to the code.

**Preferred teaching style (see `AGENTS.md`):** plain English + **ASCII visualizations** first, then short captions — not long jargon walls.

**Code anchors**

| Area | Path |
|------|------|
| Agent (LangGraph) | `backend/agent.py` |
| Retrieval (LlamaIndex hybrid) | `backend/rag.py` |
| API | `backend/main.py` |
| Chat UI | `src/app/ai-chat/page.tsx` |
| Stream client | `src/lib/api.ts` |
| Citations UX | `src/lib/citations.ts`, `src/components/SourceCitations.tsx` |
| Golden set + Ragas | `eval/golden.jsonl`, `eval/run_ragas.py`, `eval/README.md` |

---

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
  score vs grade vs answer (what each number means)
       │
       ▼
  Hybrid search: vector + BM25 + RRF   ◄── implemented
       │
       ▼
  Stemmer, QueryFusionRetriever, k=60  (absorbing)
       │
       ▼
  Multi-retriever: fuse vs compare (idea)
       │
       ▼
  2026 retrieval best practices (speed · cost · quality)
       │
       ▼
  Ship Tier-1 defaults (top_k≈8) + golden set + Ragas
       │
       ▼
  Product polish: page citations, coach voice, gpt-5.4-mini
       │
       ▼
  Day wrap — foundation + hybrid + eval baseline  ◄── today
```

---

## Chapter 1 — Build the learning app

### Q: Build a simple agentic RAG to learn how it works

**Ask:** Use LangGraph, LlamaIndex, simple PDF upload → retrieve → answer; install Astryx and init agent docs.

**What we built**

| Layer | Role |
|-------|------|
| Next.js + Astryx | Upload PDF, chat, show tool calls |
| FastAPI | `/api/upload`, `/api/chat`, `/api/chat/stream` |
| LlamaIndex | Chunk, embed, in-memory vector index, retrieve |
| LangGraph | Decide → retrieve → grade → rewrite → answer |
| pypdf | Extract text from PDF (before LlamaIndex indexes) |

**Later polish**

- Astryx template: `npx astryx template ai-chat ./src/app/ai-chat`
- Live UX: SSE streaming so the UI is not stuck while the agent runs
- PDF text cleaned (less raw PDF operator noise in chunks)

**Takeaway:** Full path from file → index → agent → UI, small enough to read end-to-end.

---

## Chapter 2 — See the information flow

### Q: Visualize the current RAG flow (ASCII)

**Two pipelines**

1. **Ingest** — PDF → text → clean → chunk → embed → in-memory index  
2. **Query** — question → agent loop → answer  

**Takeaway:** Ingest builds the “filing cabinet.” Query is when the agent decides whether (and how) to open it.

---

## Chapter 3 — What does LlamaIndex actually do?

### Q: Do we use LlamaIndex? (given pypdf in the pipeline)

**Answer:** Yes — but not for PDF parsing.

| Step | Library |
|------|---------|
| PDF → text | **pypdf** |
| Clean noise | our code |
| Split / embed / `VectorStoreIndex` / retrieve | **LlamaIndex** |

### Q: What logic does LlamaIndex handle — retriever? tool call?

**Answer:**

- **LlamaIndex** = search engine over the PDF (index + retrieve)  
- **LangGraph / LangChain** = tool definition, when to call it, graph routing  

### Q: So LangGraph calls LlamaIndex as a node tool call?

**Answer:** Almost.

```
LangGraph node "retrieve" (ToolNode)
  → LangChain @tool retrieve_documents
    → rag.retrieve()          ← LlamaIndex starts here
```

Not a special “LlamaIndex node” — a **tool** whose body uses LlamaIndex.

**Takeaway:** Orchestration vs retrieval are separate. That separation is the main architecture lesson.

---

## Chapter 4 — Where vectors live

### Q: Where is the vector store saved? Memory? Not a DB?

**Answer:** **In process RAM only** (`VectorStoreIndex` default). No Chroma/Qdrant/Postgres.

| Data | Where | Survives restart? |
|------|--------|-------------------|
| Vectors | RAM | No |
| PDF files | `backend/data/uploads/` | Yes (files only) |
| Index of those files | rebuilt only on upload | No auto-reload |

### Q: Tradeoffs — memory vs vector DB?

| | Memory (now) | Vector DB |
|--|--------------|-----------|
| Setup | Trivial | Extra service |
| Restart | Re-upload / re-embed | Index stays |
| Scale | One process, RAM limit | Many docs / workers |
| Best for | Learning, demos | Production, multi-user |

**Middle ground later:** LlamaIndex disk persist, then a real vector DB if needed.

**Takeaway:** Memory is the right learning default; persistence is a product decision.

---

## Chapter 5 — Report: what we built to learn

### Q: Report so far what we built to learn

Summarized as:

- **Naive RAG** = always retrieve → answer  
- **Agentic RAG** = decide → maybe retrieve → grade → maybe rewrite → answer  
- UI streams phases so the loop is visible, not a black box  

See also: root `README.md`.

---

## Chapter 6 — LangGraph agent in the source

### Q: Local + flow of core agent (graph, tools, conditional edges) — ASCII

**Source:** `backend/agent.py`

**Nodes (do work)**

| Node | Job |
|------|-----|
| `generate_query_or_respond` | LLM decides: call tool or answer |
| `retrieve` | Run tool → LlamaIndex search |
| `rewrite_question` | Improve query |
| `generate_answer` | Answer from question + context |

**Conditional edges (routing)**

| After | Router | Meaning |
|-------|--------|---------|
| decide | `route_on_tool_calls` | Search or stop with direct reply |
| retrieve | `grade_documents` | Answer or rewrite (loop) |

**Fixed edges:** rewrite → decide again; answer → END.

### Q: Same flow, but human-readable (CEO level)

Plain story:

1. Listen to the question  
2. Decide if the PDF is needed  
3. Look up passages if needed  
4. Check if those passages help  
5. If not, rephrase and look again (limited tries)  
6. Answer from what was found  

**Takeaway:** LangGraph is the process. LlamaIndex is the filing cabinet.

---

## Chapter 7 — The loop

### Q: Is the loop logic already handled?

**Yes.** Implemented in `agent.py`. Max rewrite / tool rounds (~2) force an answer so it cannot thrash.

### Q: Is that loop supported by LangGraph?

**Yes.** LangGraph is built for **graphs with cycles** and **conditional edges** — decide/retrieve/grade/rewrite is a standard pattern. LangGraph runs the control flow; we define the steps and if/else.

### Q: So we control the loop via grade?

**Mostly yes for “retry or finish.”**

```
After decide:  tool?  → enter search path (or END)
After retrieve: grade → yes: answer | no: rewrite → decide → retrieve again
```

Plus a **cap** so grade cannot loop forever.

**Takeaway:** Grade is the main **loop gate**; tool-call routing is the **entry** gate.

---

## Chapter 8 — How grade knows “good enough”

### Q: How do we know if search is good enough and grade correctly?

In this repo, grade is **not** a vector-score threshold alone.

It is a **second LLM call**:

- Input: user question + retrieved chunk text  
- Output: structured `binary_score` = `"yes"` | `"no"`  
- Prompt idea: relevant if keywords or semantic meaning match  

Good for **learning and routing**. Not a guarantee of truth or answer quality.

Possible upgrades later: stricter “answerable only from context,” min similarity, or judge the **answer** (faithfulness).

### Q: So it’s like LLM-as-a-judge?

**Yes** — a small, online **LLM-as-judge for relevance routing**.

Not a full eval suite (multi-rubric offline scoring). One binary judgment used to branch the graph.

---

## Chapter 9 — LlamaIndex as the search SDK (deepen foundation)

### Q: What is LlamaIndex’s role, really?

**Short answer:** Supporting **library/SDK** that searches docs in **vector space** (and now also BM25 — Chapter 10).  
It is **not** the agent brain.

```
  LangGraph = the process          LlamaIndex = the search
  (decide / grade / rewrite)  →    (chunk / embed / top-k)
```

In the wider world LlamaIndex can do agents and query engines too.  
**This repo uses a thin slice:** ingest + retrieve only.

### Q: The three steps → real code

| Step | What | Code in `rag.py` |
|------|------|------------------|
| ① | Turn text into vectors | `Settings.embed_model = OpenAIEmbedding(...)` + chunker |
| ② | Keep them in an index | `VectorStoreIndex.from_documents(...)` / `.insert` |
| ③ | Similarity search | `_index.as_retriever(...).retrieve(query)` |

```
  UPLOAD                              QUERY
  ─────                               ─────
  pypdf extract (not LlamaIndex)
       │
  Document(...)
       │
  configure_models()     ← ① embed + chunk settings
       │
  VectorStoreIndex       ← ② chunk + embed + store
       │
       └──────────────────────────────► ③ hybrid retrieve (Ch. 10)
```

You do **not** call `embed()` by hand. Building the index uses `Settings.embed_model` under the hood.

### Q: What LlamaIndex is *not* doing here

| Job | Owner |
|-----|--------|
| “Should I search?” | LangGraph |
| “Are chunks good enough?” | LangGraph grade |
| Rewrite / final answer | LangGraph |
| PDF parsing | pypdf |

**One-line model:** LlamaIndex = filing cabinet + librarian; LangGraph = manager who decides when to ask the librarian.

---

## Chapter 10 — Score, grade, and how chunks reach the answer

### Q: What is the retrieval `score`?

On each chunk, the engine attaches a **similarity / rank-related score** (how strong a match for this query).

After hybrid (Ch. 11), chunk headers show **`rrf=…`** (fused rank score), not raw cosine alone.

| | Engine score / RRF | Grade `binary_score` |
|--|--------------------|----------------------|
| **Who** | LlamaIndex search math | Second LLM call |
| **What** | “How strong a shortlist pick?” | “Is this text useful for the Q?” |
| **Values** | Float (e.g. `0.0328`) | `"yes"` / `"no"` |
| **Routes the graph?** | **No** | **Yes** — answer vs rewrite |

Higher score ≠ “the answer is true.” Only “this passage ranked well for search.”

### Q: How do chunks flow into grade and answer?

Bridge = **chat messages**. Tool returns one string → last message `content`.

```
  retrieve (search)
       │
       │  string of chunks (+ via= / rrf=)
       ▼
  ToolMessage  (state["messages"][-1].content)
       │
       ├──────────────────────┐
       ▼                      ▼
  grade_documents        generate_answer
  (router only)          (writes final reply)
```

- **Grade** reads that string + original question → yes/no → next node name only  
- **Answer** uses the **same** context string + question → final reply  
- Rewrite cap (`MAX_REWRITES ≈ 2`) forces answer if looping  

```
  score / rrf  =  math nearness / fusion rank     (search)
  grade        =  human-ish check yes/no          (loop gate)
  answer       =  write from chunks               (generation)
```

**Takeaway:** The agentic part is not the float — it’s **grade choosing the path** after search.

---

## Chapter 11 — Hybrid search (vector + BM25 + RRF) — implemented

### Q: Foundation is done — what’s the first advanced upgrade?

**Hybrid search:** upgrade the **search engine** inside the tool; LangGraph loop stays the same.

**Clarification we locked in:** hybrid was **not** in the code before this chapter — only pure vector top-k. We learned it, then implemented it.

### Q: Why hybrid? (problem pure vector has)

| Vector is strong | Vector is weak |
|------------------|----------------|
| Paraphrase / meaning | Exact codes: `E-4412`, SKUs |
| Fuzzy conceptual Qs | Rare names, literal phrases |

```
  Q: "What does error E-4412 mean?"

  Vector may fetch:  vague "error handling" paragraphs
  BM25 hits:         the line that literally says "E-4412"
  Hybrid:            both shortlists → fuse → better briefing
```

### Q: Is BM25 a library? LlamaIndex? LangGraph?

| Name | What it is |
|------|------------|
| **BM25** | A **ranking algorithm** (keyword / sparse). Not owned by LangGraph. |
| **Underlying libs** | e.g. bm25s / rank_bm25 (pulled in as deps of the LlamaIndex package) |
| **LlamaIndex** | Package `llama-index-retrievers-bm25` → `BM25Retriever` |
| **LangGraph** | **Does not search.** Still only orchestrates decide → retrieve → grade. |

**Package added:** `llama-index-retrievers-bm25` in `backend/requirements.txt`.

### Q: What did we change in the code?

Only `backend/rag.py` retrieve path. **`agent.py` unchanged.**

```
  BEFORE                         AFTER (hybrid)
  ──────                         ──────────────
  vector top-k only              vector top pool
                                       +
                                 BM25 top pool
                                       │
                                       ▼
                                 RRF fuse ranks
                                       │
                                       ▼
                                 final top-k → tool string
```

**Ingest:** still builds `VectorStoreIndex`.  
**BM25:** built at query time from `index.docstore` (same chunks), with English **Stemmer**.

Chunk headers for learning:

```
[Chunk 1 | source=… | page=… | via=bm25+vector | rrf=0.0328]
```

`via=` shows which engine(s) hit; `rrf=` is the fused score.

### Q: Stemmer — what is it? (product owner)

Preprocessor for BM25 so word **variants** match better and fluff words matter less.

```
  refund / refunds / refunded  →  similar roots
  drop common noise words      →  focus on content terms
```

| Care about | Stemmer’s job |
|------------|---------------|
| Exact codes (`E-4412`) | Mostly unchanged |
| Everyday English variants | **The win** |
| GPT-level understanding | **Not that** — still keyword logic |

### Q: QueryFusionRetriever — what is it?

Official LlamaIndex **merger** of multiple retrievers (not a third search engine).

```
  vector.retrieve(q)  ──┐
                        ├──► QueryFusionRetriever ──► final top-k
  bm25.retrieve(q)  ────┘
```

| Arg (typical) | Product meaning |
|---------------|-----------------|
| `[vector, bm25]` | Use these two engines |
| `similarity_top_k` | Final shortlist size |
| `num_queries=1` | Don’t invent extra rewrites (cheap/simple) |
| `mode="reciprocal_rerank"` | Merge by rank (RRF-style) |

**What we use instead:** explicit `_reciprocal_rank_fusion()` in `rag.py` so we can label `via=vector` / `bm25` / `vector+bm25`.  
**Same product outcome** as QueryFusionRetriever; more transparent for learning.

### Q: Fundamentally — combine into 1 list and score?

**Yes.**

```
  Two ranked lists
       │
       ▼
  Each chunk gets a fused score
       │
       ▼
  One list, sorted high → low
       │
       ▼
  Top-k = candidates for the agent
```

Higher fused score → better rank → more likely top candidate.  
Chunks on **both** lists usually score higher (two contributions).  
Fused score ≠ “answer is true” — only “strong shortlist pick.”

### Q: Real sample (E-4412)

Chunks: C1 exact E-4412, C2 general errors, C3 refund, C4 network, C5 tickets.

```
  Vector shortlist:  C2, C1, C4
  BM25 shortlist:    C1, C2, C5
           │
      RRF fusion
           │
  Final top-2:       C1, C2     ← C1 is what we wanted
```

Live smoke test in this project confirmed:

```
via=bm25+vector | rrf=0.0328
Error code E-4412 means the valve timed out...
```

### Q: RRF formula and k=60 — meaning

```
  contribution = 1 / (k + rank)
  fused_score  = sum of contributions from every list the chunk appears in

  default k = 60
```

| Piece | Meaning |
|-------|---------|
| **rank** | Position in one engine’s list (1 = best) |
| **1/(k+rank)** | Points for that position |
| **sum over lists** | Reward multi-engine agreement |
| **k=60** | Softener so rank gaps aren’t insane (paper default, not “60 docs”) |

Tiny example:

| Rank | Score with k=60 |
|------|-----------------|
| 1 | 1/61 ≈ 0.0164 |
| 2 | 1/62 ≈ 0.0161 |
| 3 | 1/63 ≈ 0.0159 |

If C1 is BM25 #1 and vector #2: `0.0164 + 0.0161 ≈ 0.0325` — often beats a single-list #1.

**What k does (intuition — still absorbing is OK):**

```
  small k  →  #1 dominates hard (rank gaps huge)
  large k  →  #1 vs #2 is softer; multi-list agreement matters more
  k=60     →  common default from the RRF research paper
```

**Honest note:** Van not 100% absorbed on *why* 60 specifically — that’s fine. Working model: **default dampener**, not magic from our PDFs. Rarely need to tune it when learning.

**Takeaway:** Hybrid upgrades **which passages** the tool returns. Agent loop (decide/grade/rewrite/answer) is unchanged.

---

## Chapter 12 — Multi-retriever: fuse vs compare (popup idea)

### Q: Can we have multiple retrievers, each with different logic, and compare them?

**Yes.** Industry-standard. Hybrid (Ch. 11) is already a **2-retriever** system.

```
  one question
       │
       ├─► Retriever A  (vector / meaning)
       ├─► Retriever B  (BM25 / keywords)
       ├─► Retriever C  (metadata filter: this PDF only)   ← future
       ├─► Retriever D  (other corpus / web)               ← future
       │
       ▼
  compare / merge / pick
       │
       ▼
  shortlist → grade → answer
```

Each retriever = **one search strategy**.  
A later step either **merges** or **compares** what they found.

### Q: Fuse vs compare — two product moves

| Move | Meaning | Example |
|------|---------|---------|
| **Merge (fuse)** | Combine shortlists into **one** briefing | RRF / QueryFusionRetriever (what we ship) |
| **Compare** | Keep results **side by side** to learn or choose | UI columns, logs, eval metrics, or LLM router |

```
  FUSE (production default)
  A top-k + B top-k  →  one ranked list  →  agent

  COMPARE (learning / routing / eval)
  A results | B results
       │
       ├─ show both in UI
       ├─ or LLM/rules pick which list to trust
       └─ or score A vs B offline on golden questions
```

### Q: Patterns people use

| Pattern | Shape | Good for |
|---------|--------|----------|
| **Parallel + fuse** | A ‖ B → RRF → top-k | Default hybrid (we have this) |
| **Parallel + router** | A ‖ B → pick list A or B | Query-type routing |
| **Cascade** | Try A; if grade fails → try B | Save cost; escalate |
| **Ensemble / eval** | Run A vs B offline, measure wins | Choosing strategy with data |

LangGraph shines at **router** and **cascade**.  
LlamaIndex shines at **parallel + fuse**.  
**Eval** is a test harness, not always runtime.

### Q: What we already have as a seed

```
  TODAY
  Retriever A = vector
  Retriever B = BM25
  Merge       = RRF → one list
  Soft compare signal = via=bm25+vector labels in chunk headers
```

**Takeaway:** Multiple retrievers? Yes. Compare? Yes (fuse for prod, compare for learning/eval/routing). Does not replace LangGraph.

**Possible later builds (idea only):** learning UI (Vector vs BM25 columns), router after weak grade, third retriever (metadata filter), offline win-rate notebook.

---

## Chapter 13 — 2026 retrieval best practices (speed · cost · quality)

### Q: What’s the best-practice retrieval strategy right now (2026), balanced for speed, cost, and effectiveness?

**Consensus default stack:**

```
  DEFAULT (2026)

  cheap + fast net          expensive precision
  ─────────────────         ──────────────────
  Hybrid retrieve     →     Rerank shortlist     →   top 5–10 to LLM
  (BM25 + dense)            (cross-encoder)
  top ~20–50                top ~5–10
```

Two-stage **funnel**: wide cheap recall → narrow precise ranking → small context to the model.

### Q: The funnel (mental model)

```
  Query
    │
    ▼
  ┌─────────────────────────────────────┐
  │ STAGE 1 — Recall (wide, cheap)      │
  │ BM25  ║  dense vectors  →  RRF/fuse │
  │ pull 20–50 candidates               │
  └─────────────────┬───────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────┐
  │ STAGE 2 — Precision (narrow, $$$)   │
  │ cross-encoder / rerank API          │
  │ keep 5–10 for the LLM               │
  └─────────────────┬───────────────────┘
                    │
                    ▼
              generate answer
         (biggest $ is often the LLM)
```

| Stage | Job | Speed | Cost | Quality role |
|-------|-----|-------|------|----------------|
| **Hybrid** | Don’t miss good docs | Fast (+~10–50ms if parallel) | Low | **Recall** |
| **Rerank** | Order shortlist well | +~100–300ms typical | Medium | **Precision** |
| **LLM answer** | Write from context | Slowest | Highest | Generation |

Rerank is often the **largest quality jump after hybrid**. Hybrid alone is already a big step over vector-only.

### Q: Good defaults in 2026

| Layer | Common practice | Why |
|-------|-----------------|-----|
| **Sparse** | BM25 (or similar) | Exact terms, IDs, names; still strong on many enterprise docs |
| **Dense** | Solid embeddings + vector index | Meaning / paraphrase |
| **Fuse** | RRF, **k=60** baseline | No score-calibration drama |
| **Rerank** | Cross-encoder on top ~20–50 | Best precision per extra $ |
| **To LLM** | **5–10** chunks, not 30 | Cuts tokens, noise, cost |
| **Chunking** | Careful size + overlap + metadata | Underrated vs fancy agents |
| **Agentic loop** | Grade / rewrite when needed | Cheaper than always multi-hop |

**Often skip until metrics demand it:** multi-query expansion, HyDE on every request, always-on multi-hop — can add latency/cost with weak ROI on precise/numeric questions.

### Q: Balance by product tier

```
  TIER 0 — Learning / tiny demo
  vector only
  cheapest; misses exact terms

  TIER 1 — Good default  ◄── this repo (hybrid implemented)
  hybrid (BM25 + dense + RRF)
  best bang for almost free compute

  TIER 2 — Production quality default  ◄── recommended next
  hybrid → rerank → top 5–10 → LLM
  best speed / cost / quality balance in 2026

  TIER 3 — High-stakes / eval-driven
  + better chunking, metadata filters, optional router
  + golden-set metrics (Recall@k, MRR, …)

  TIER 4 — Max quality (pay for it)
  heavier ensembles / rerankers only if metrics justify $
```

| Goal | Lean toward |
|------|-------------|
| **Lowest latency** | Hybrid only, small top-k, skip rerank; parallel BM25‖dense |
| **Lowest $** | Hybrid, top-5 to LLM, no multi-query, no extra agent hops |
| **Highest quality** | Hybrid + rerank + good chunking + eval |
| **Balanced (most teams)** | **Tier 2** |

### Q: Cost reality (order of magnitude)

```
  relative $ per question (typical API stack)

  BM25 retrieve          █                 ~free
  dense retrieve         ██                embed query
  RRF merge              █                 free CPU
  rerank 20–50 docs      ████              small–medium
  LLM answer             ████████████████  usually dominates
```

**PO insight:** Don’t cheap out on retrieval and then burn LLM tokens on junk context. A slightly better shortlist often pays for itself.

### Q: Speed tips that beat exotic retrievers

1. Run BM25 ‖ dense **in parallel** (latency ≈ max of both, not sum).  
2. Rerank only a **shortlist** (20–50 in → 5–10 out), never the whole corpus.  
3. Cache embeddings / hot queries when traffic repeats.  
4. Don’t multi-hop every question — escalate when grade fails.  
5. Move off RAM-only index when scale needs a vector DB.

### Q: Where this project sits vs the 2026 target

```
  Your app now              2026 balanced target
  ────────────              ────────────────────
  hybrid BM25 + vector      hybrid
  explicit RRF              RRF (same idea)
  top-k → agent             + rerank before grade/answer
  no persist                + persist / vector DB later
  agentic grade loop        keep (agentic layer on top)
```

### Q: Practical checklist

```
  DO NOW / DEFAULT
  • Hybrid BM25 + dense + RRF (k=60)     ✅ done (Ch. 11)
  • Send ~5–10 chunks to the LLM
  • Keep agent grade/rewrite as safety net

  DO NEXT (best ROI)
  • Rerank hybrid top ~20 → final ~5–8   ← Tier 2
  • Golden-question eval (even ~20 Qs)

  DO LATER
  • Persist index / vector DB
  • Metadata filters (multi-PDF)
  • Multi-retriever compare UI / router (Ch. 12)
  • Tune k / weights only after metrics

  SKIP UNTIL NEEDED
  • HyDE / multi-query on every request
  • 5-retriever ensembles with no eval
  • Always-on multi-hop agent
```

**Bottom line (2026):**  
**Hybrid for recall, rerank for precision, small context to the LLM for cost/speed.** Everything else is situational and should follow measurement.

---

## Chapter 14 — Ship Tier-1 defaults + eval the playbook

### Q: Implement DO NOW / DEFAULT only (no rerank yet)

| Item | Status |
|------|--------|
| Hybrid BM25 + dense + RRF (k=60) | Already in `rag.py` |
| Send 5–10 chunks to LLM | `DEFAULT_TOP_K = 8` in `rag.py` |
| Grade / rewrite safety net | Unchanged (`MAX_REWRITES = 2`) |

### Q: How do we eval? Golden set + Ragas?

**Yes.** Offline exam ≠ runtime grade.

```
  GOLDEN SET (human)          RAGAS (LLM-as-judge metrics)
  ─────────────────           ────────────────────────────
  25 Qs on MMBot playbook     context_recall
  must_have / Hit@k checks    faithfulness
  should_retrieve flags       factual_correctness
```

| Artifact | Path |
|----------|------|
| Cases | `eval/golden.jsonl` (25; Huua MMBot Playbook v1.0) |
| How-to | `eval/README.md` |
| Runner | `eval/run_ragas.py` |
| Sample run | `eval/results-ragas-*.md` / `.json` |

Ragas is a **Python library/CLI** (not a required local UI). Optional Ragas App is a separate cloud product. We check scores in the terminal + markdown report.

### Q: First Ragas baseline (23 `should_retrieve` cases)

| Metric | Score (approx) | Read |
|--------|---------------:|------|
| context_recall | ~0.85 | Hybrid usually covers gold content |
| faithfulness | ~0.78 | Mostly grounded |
| factual_correctness | ~0.55 | Room to tighten wording / retrieval |

Checklist from same run: routing ~96%, chunk/answer must-haves ~83%.  
Manual weak spots called out: **q02** (skipped retrieve), **q06** (status filters vs Live/Approved list).

### Q: Core agent prompts (where the “brain” is instructed)

All in `backend/agent.py` — **per-node**, not one giant system prompt:

| Node | Job |
|------|-----|
| Decide system | Tool vs direct reply; coach-ish greeting |
| Tool docstring | When to call hybrid retrieve |
| `GRADE_PROMPT` | yes/no relevance (LLM-as-judge router) |
| `REWRITE_PROMPT` | Better retrieval question |
| `GENERATE_PROMPT` | Answer + explain + next steps + page cites |

---

## Chapter 15 — Product polish (citations, voice, model)

### Q: Stop saying “Chunk 1 / Chunk 2”

**Problem:** Model cited internal chunk indices — bad UX.

**Fix:**

```
  retrieve format     →  Document + Page headers (not Chunk N)
  GENERATE_PROMPT     →  cite (p. N) or (Doc, p. N) only
  UI                  →  strip leftover "Chunk …"; Sources tokens
```

| Code | Role |
|------|------|
| `rag.py` | Passage cards with Document / Page / Match |
| `src/lib/citations.ts` | Parse + clean |
| `SourceCitations.tsx` | Footer chips: `p.3 · filename` |

### Q: Answer style should explain + propose next steps

Not a dry FAQ. Reply shape:

1. **Answer** — point first  
2. **Why / how it fits** — short grounded explanation  
3. **Next steps** — related questions or “want to dive into X?”

### Q: Model upgrade

Chat / grade / rewrite / answer: **`gpt-5.4-mini`** via `OPENAI_MODEL` (default in `agent.py` + `.env`).  
Embeddings stay **`text-embedding-3-small`** (retrieval, not “brain”).

---

## Chapter 16 — Day wrap (what we own now)

```
  BEFORE THIS ARC                    AFTER TODAY
  ────────────────                   ───────────
  Vector-only retrieve               Hybrid (vector + BM25 + RRF)
  top_k = 4                          top_k = 8 (5–10 band)
  gpt-4o-mini                        gpt-5.4-mini
  "Chunk N" cites                    Page + document + Sources UI
  Dry Q&A                            Coach: answer → explain → next
  No eval                            Golden 25 + Ragas baseline
  Mental model fuzzy on search       Clear: LangGraph process / LI search
```

**Still true (unchanged architecture):**

```
  LangGraph = process (decide → retrieve → grade → rewrite → answer)
  LlamaIndex = search (ingest + hybrid retrieve)
  Index = RAM only (re-upload after restart)
```

**Honest loose ends:** RRF `k=60` intuition still “good enough default”; factual_correctness ~0.55; no rerank yet; no index persist.

---

## Mental model card (keep this)

```
┌─────────────────┐     ┌──────────────────────────────┐
│   LangGraph     │     │   LlamaIndex (search SDK)    │
│   "the process" │     │   "the filing cabinet"       │
├─────────────────┤     ├──────────────────────────────┤
│ decide (coach)  │     │ chunk / embed                │
│ tool call       │────►│ vector + BM25 → RRF → top-8  │
│ grade (judge)   │◄────│ Document + Page passages     │
│ rewrite         │     │ in-memory VectorStoreIndex   │
│ answer + next   │     └──────────────────────────────┘
└─────────────────┘
         │
         ▼
  UI: stream phases · tool summary · Sources (p.N · file)
  Eval: golden.jsonl + Ragas (recall / faith / factual)

  2026 funnel:  hybrid (recall) → [rerank later] → LLM (generate)
```

| Term | In this project / learning |
|------|----------------------------|
| **Agentic RAG** | Agent chooses when/how to use retrieval |
| **Tool** | `retrieve_documents` → hybrid `rag.retrieve()` |
| **Loop** | Bad chunks → rewrite → search again (max ~2) |
| **Judge** | Grade node (LLM yes/no relevance) — not answer truth |
| **Hybrid** | Vector + BM25, fused with RRF (k=60) |
| **RRF** | `score += 1/(60+rank)` per list; higher = better shortlist |
| **Eval** | Offline golden + Ragas; ≠ runtime grade |
| **Citation** | `(p. N)` + Sources strip; never Chunk N |
| **Voice** | Answer → explain → related next steps |
| **Tier 1 / 2** | Hybrid shipped / rerank still next ROI |

---

## Suggested re-read order

1. This file — **Ch. 9–16** for today’s arc; 1–8 for foundation  
2. `README.md` (how to run)  
3. `backend/rag.py` — hybrid + `DEFAULT_TOP_K`  
4. `backend/agent.py` — prompts (decide / grade / rewrite / generate)  
5. `src/lib/citations.ts` + chat page (Sources UX)  
6. `eval/README.md` + re-run `python eval/run_ragas.py --only-retrieve`  

**UI smoke:** re-upload PDF after restart → ask playbook Q → expect `(p. N)` cites + Sources tokens + next-step questions.

---

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

### Next sessions (priority order)
- [ ] Fix eval fails: **q02** force retrieve on terms, **q06** Live/Approved vs Active/Inactive  
- [ ] Re-run Ragas after prompt/retrieval tweaks (track factual_correctness)  
- [ ] **Tier 2:** cross-encoder **rerank** after hybrid (best quality ROI)  
- [ ] Persist index (disk / vector DB)  
- [ ] Optional: click source token → expand passage preview  
- [ ] Multi-PDF metadata filters  
- [ ] Token-level answer streaming  
- [ ] Local models (Ollama) if cost/privacy matters  

---

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
20. Document this journey in the repo (this file)  
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
34. Document hybrid session in this file  
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
48. Finalize LEARNING_JOURNEY for the day (Ch. 14–16)  

---

*Last updated: end of a big learning day — hybrid retrieval shipped, eval baseline with Ragas, product polish (citations + coach answers), model gpt-5.4-mini. Next natural build: Tier-2 rerank and fixing q02/q06-class eval gaps. Update when a new “aha” changes the mental model.*


