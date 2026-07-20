# Tier-2 cross-encoder rerank

> Part of the [learning hub](./README.md).  
> Hybrid recall → cross-encoder precision, local HF ranker.

**Chapters:** Ch. 18

---

## Chapter 18 — Tier-2 cross-encoder rerank

### Q: Implement rerank (cross-encoder) to polish the RAG flow

**Why after hybrid?**

```
  hybrid (vector + BM25 + RRF)  =  RECALL  — “is the right page in the shortlist?”
  cross-encoder                 =  PRECISION — “which of these best match the query?”

  bi-encoder / BM25:  encode once, compare cheaply
  cross-encoder:      read (query + passage) together → slower, smarter reorder
```

**Pipeline now (shipped)**

```
  query
    │
    ├─► VECTOR pool ─┐
    │                ├─► RRF (candidates_k≈20) ─► CE rerank ─► top_k=8
    └─► BM25 pool  ──┘         wide shortlist      pairs        to LLM
                                    │
                                    ▼
                              PACKAGE (char cap) → tool string
```

| Knob | Default | Env |
|------|---------|-----|
| On/off | **on** | `RAG_RERANK=0` to skip |
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `RERANK_MODEL` |
| RRF width | 20 | `RERANK_CANDIDATES` |
| To LLM | 8 | `DEFAULT_TOP_K` / `--top-k` |

| Code | Role |
|------|------|
| `backend/rag.py` | `_cross_encoder_rerank`, lazy `SentenceTransformerRerank` |
| `eval/trace_rag.py` | `rerank` step + `--no-rerank` A/B |
| deps | `torch`, `sentence-transformers` |

**Trace check**

```bash
python eval/trace_rag.py --ids q06              # CE on
python eval/trace_rag.py --ids q06 --no-rerank  # hybrid only
```

Look at **RERANK** step: pages reordered vs RRF; gold page should stay high (often #1).

**Takeaway:** Tier 2 = hybrid for recall + CE for precision. Don’t rerank the whole corpus — only the shortlist.

### Q: Explain like a PM / CEO — rerank, cross-encoder, why local HF model?

**Business problem (one picture)**

```
  User asks:  “Which market statuses appear on Live Markets?”

  Library has ~45 pages of PDF text.

  Job of search:
    1) Don’t miss the right page          ← RECALL
    2) Put the best page first            ← PRECISION
    3) Only send a short list to the LLM  ← COST / CLARITY
```

If you send the LLM 30 mediocre snippets → more $ and more confusion.  
If you send 8 great ones → better answers, often cheaper.

---

**Brain A — Hybrid (Tier 1 you already had)**

```
  VECTOR (meaning)     “Live Markets statuses” ≈ similar pages
  BM25 (keywords)      exact words: status, Live, markets
           │
           ▼
  RRF = merge two ranked lists into one shortlist (~20)
```

**Office analogy:** Two interns each bring folders that *might* be relevant.  
You merge into one pile. Fast. Good at **not missing** the right folder.

**Limitation:** They score “seems related,” not “best answers *this* question.”

---

**Brain B — Rerank with a cross-encoder (Tier 2)**

```
  Shortlist of ~20 passages
           │
           ▼
  For EACH candidate, read TOGETHER:

     [ question ]  +  [ this passage ]

           │
           ▼
  Score: how well does THIS passage answer THIS question?
           │
           ▼
  Keep top 8 → send to the “answer writer” (chat LLM)
```

**Office analogy:** After interns bring 20 folders, a **senior analyst** opens each folder next to the question and ranks: “This one answers it; that one is only vaguely related.”

**Rerank** = re-order a **small shortlist** so the best evidence is #1–#8.  
Not “search the whole company drive again.”

---

**What “cross-encoder” means (no jargon wall)**

| | **Bi-encoder** (vector search) | **Cross-encoder** (rerank) |
|--|--------------------------------|----------------------------|
| How | Embed query once, embed docs once, compare vectors | Feed **query + doc as one pair** into one model |
| Speed | Very fast on many docs | Slower — only use on ~20, not whole library |
| Quality on “does this answer the Q?” | Good enough to shortlist | Usually **better precision** |
| Like | Search “find related” | Human reading Q and paragraph together |

```
  Bi-encoder:     Q ──► vec     Doc ──► vec     →  distance
  Cross-encoder:  [Q | Doc] ──► one score for the pair
```

---

**Why a local model from Hugging Face?**

```
  Answer LLM (gpt-5.4-mini)              = cloud OpenAI · $ per call · “writer”
  Embeddings (text-embedding-3-small)    = cloud OpenAI · $ per call · vectors

  Cross-encoder (ms-marco MiniLM)        = small specialist ranker
                                           download ONCE from Hugging Face Hub
                                           runs on YOUR machine (CPU/GPU)
                                           no HF API key for this setup
```

| Option | Pros | Cons |
|--------|------|------|
| **Local CE (what we ship)** | Cheap after download; no per-pair OpenAI $; private; predictable | Needs torch + disk; first download; local CPU |
| **Call GPT to score each pair** | No local install | 20 passages × API = slow + expensive |
| **No rerank** | Simplest | More junk in top-8 → weaker answers / more rewrite |

**Product framing:** CE is a **cheap specialist ranker**, not the CEO writer.  
Hugging Face Hub = **app store for open weights** — we pull a standard MS MARCO reranker once, then run offline.  
(Not “call Hugging Face cloud on every question.”)

```
  Hugging Face Hub
        │  download once
        ▼
  Mac / server: sentence-transformers + torch
        │  every user question
        ▼
  Score ~20 pairs locally (ms–hundreds of ms)
        │
        ▼
  Still call OpenAI for: embeddings + final answer only
```

---

**End-to-end product story**

```
  UPLOAD PDF          →  filing cabinet (chunks + vectors)
  USER QUESTION
        │
        ▼
  FAST WIDE NET       hybrid: vector + keyword + RRF     (~20)
        │
        ▼
  QUALITY FILTER      local cross-encoder rerank         (top 8)
        │
        ▼
  SMART WRITER        GPT answers from those 8 only
        │
        ▼
  USER sees grounded answer + page cites
```

**Roadmap language (board / PRD)**

```
  Tier 1  Hybrid only           good / cheap     ← shipped earlier
  Tier 2  Hybrid + local CE     better precision ← shipped now
  Tier 3  + eval / persist DB   production scale
```

**One sentence for a deck:**  
*We cast a wide, cheap net, then use a small open model on the machine to put the best 8 evidence cards on top before the expensive language model writes the answer.*

**Remember (PM cheat sheet)**

1. **Hybrid** finds candidates (don’t miss the right page).  
2. **Rerank** reorders so the best page is first.  
3. **Cross-encoder** judges **question + passage together**.  
4. **Local HF model** = free-to-run ranker on your box; OpenAI stays for embed + write.  
5. **Why bother:** better evidence → better answers, less noise, often fewer agent retries — without paying GPT to score every snippet.

**Hub links:** [learning README](./README.md) · question index · next steps · [Ch. 17 packaging](./05-ship-eval-polish.md)

---

