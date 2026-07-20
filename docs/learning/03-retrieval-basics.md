# Retrieval basics — LlamaIndex, score, chunks → answer

> Part of the [learning hub](./README.md).  
> LlamaIndex as search SDK, embed→index→retrieve, score vs grade vs answer.

**Chapters:** Ch. 9, Ch. 10

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

