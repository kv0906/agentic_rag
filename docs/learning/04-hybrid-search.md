# Hybrid search — vector + BM25 + RRF

> Part of the [learning hub](./README.md).  
> Hybrid implemented, stemmer, k=60, fuse vs compare multi-retriever idea.

**Chapters:** Ch. 11, Ch. 12

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

