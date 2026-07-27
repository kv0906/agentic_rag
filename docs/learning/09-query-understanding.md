# Query understanding — decontextualization, intent routing & HyDE

> Part of the [learning hub](./README.md).
> Practical techniques that improve the query **before** or **around** retrieval.

**Chapters:** Ch. 25 (decontextualization) · Ch. 26 (intent-based retrieval) · Ch. 27 (HyDE)

> **Status in this repo:** learned and documented; these three techniques are **not implemented in the main RAG graph yet**.

---

## The map

```
  conversational question
          │
          ▼
  decontextualize
  “what is this actually about?”
          │
          ▼
  classify intent
  “how much work does it deserve?”
          │
          ▼
  choose retrieval lane
          │
          ├─ factoid → normal hybrid
          ├─ summary → broad/summary retrieval
          ├─ deep    → optional step-back / HyDE / multihop / rerank
          └─ chitchat → no retrieval
```

These are separate decisions:

> **Decontextualization determines what the question is about. Intent determines how much work is needed.**

---

## Chapter 25 — Decontextualization: make the query standalone

### Life analogy

If you overhear “How does it compare with the other one?”, you cannot answer without the earlier conversation. Retrieval has the same problem.

```
  Recent turn: “We are discussing parent-child chunking.”

  Current query:
  “How does it improve retrieval?”
              │
              ▼
  Standalone query:
  “How does parent-child chunking improve retrieval?”
```

### What it does

Decontextualization replaces pronouns and conversational references with concrete subjects from recent history.

Typical signals:

```text
  EN: it, that, this, those, they, previous, continue
  VI: nó, đó, này, cái này, còn, tiếp theo, nói rõ thêm
```

Practical gated flow:

```
  query
    │
    ▼
  cheap reference-pattern check
    │
    ├─ no reference → keep original query
    │
    └─ reference found
             │
             ▼
       recent 3–4 turns + query
             │
             ▼
       cheap LLM rewrite
             │
             ▼
       validate output; on failure use original
```

### It does not answer

```text
  Input:  “How does it work?”

  Wrong:  “It works by searching small children...”  ← answered
  Right:  “How does parent-child chunking work?”      ← rewritten
```

The rewritten query should preserve language, meaning, and constraints. It must not invent a new subject.

### Why it improves retrieval

```
  “How does it work?”
      missing: parent-child, chunking, retrieval

  “How does parent-child chunking work?”
      vector + BM25 now receive the important nouns
```

### Controls worth keeping

- Skip the LLM for already-standalone questions.
- Use only a small recent window, not the entire chat.
- Time out and fall back to the original query.
- Reject empty, multiline, or wildly longer rewrites.
- Log original → rewritten for eval and debugging.
- Evaluate coreference cases separately from normal questions.

**Takeaway:** Decontextualization is not “better wording”; it restores the missing subject so retrieval has something concrete to search.

---

## Chapter 26 — Intent-based retrieval: spend effort where it matters

### What is a factoid?

In this context, **factoid** means a direct factual lookup:

```text
  “What is an MM User?”
  “What is the Group 1 distance?”
  “Which page defines Auto Refresh?”
```

Usually one or a few nearby passages contain the answer.

Contrast:

```
  FACTOID
  “What is the Group 1 distance?”
          └─► one fact: Distance = 2

  DEEP
  “Why does Group 1 use Distance 2, and how does it compare with Group 2?”
          └─► retrieve two settings + understand roles + compare + synthesize
```

### Practical intent lanes

| Intent | User needs | Suggested lane |
|--------|------------|----------------|
| Factoid | One direct fact | Hybrid retrieve; usually skip HyDE/multihop |
| Summary | Condensed section/document | Summary tree or broader retrieval |
| Deep | Why/how/comparison/multi-doc reasoning | Step-back or HyDE; rerank; possibly multihop |
| Chitchat | Conversation, not document evidence | Skip retrieval |

```
  same system
      │
      ├─ cheap lane:  factoid
      └─ strong lane: deep
```

The point is not taxonomy for its own sake. Intent controls:

- whether retrieval runs
- top-k and context budget
- whether HyDE/rerank/multihop runs
- model tier
- latency and cost budget

### Safe routing rule

Prefer graceful degradation:

```text
  router uncertain
       │
       └─► normal hybrid retrieval
            (not “no retrieval”)
```

A false “deep” costs time. A false “chitchat” can produce an ungrounded answer. Measure routing by intent, not only aggregate accuracy.

**Takeaway:** Intent routing is a budget controller: simple questions stay fast; hard questions earn stronger retrieval.

---

## Chapter 27 — HyDE: search with an imagined answer

**HyDE = Hypothetical Document Embeddings.**

### Life analogy

A librarian imagines what a textbook answer might sound like, then searches for real passages written similarly.

```
  user question
       │
       ▼
  LLM writes a short hypothetical answer
       │
       ▼
  embed the hypothetical answer
       │
       ▼
  vector-search real chunks
       │
       ▼
  answer only from real evidence
```

Standing one-liner:

> HyDE imagines what the answer might sound like so vector search can find where the real answer lives.

### Why it can work

Questions and source passages often use different language:

```text
  Question:
  “Why does this search method work better?”

  Hypothetical answer:
  “Small child chunks improve retrieval precision while larger
   parent windows preserve context for generation.”
```

The imagined answer contains document-like terms—`retrieval precision`, `parent windows`, `context`—that may sit closer to the real passage in embedding space.

### Safe production pattern

Never replace normal retrieval with HyDE:

```
  original query ─────► hybrid search ────┐
                                          ├─► merge → rerank → real evidence
  hypothetical answer ► dense search ─────┘
```

The hypothetical answer is a **search clue**, never a citation or source of truth.

### When to use it

Good candidates:

- abstract “why/how” questions
- conceptual questions whose wording differs from the corpus
- deep analytical questions
- vocabulary mismatch between user and source

Usually skip:

- exact factoids with strong keywords
- summary requests
- chitchat
- cases where latency/cost budget is tight

### Main risk and controls

The imagined answer can guess the wrong direction and bias search.

Controls:

- always search the original query too
- intent-gate HyDE, usually to `deep`
- keep the hypothetical answer short
- merge with hybrid results
- rerank the merged shortlist
- cite and answer only from retrieved source chunks
- compare recall/quality against HyDE-off on the same goldens

### HyDE vs nearby techniques

| Technique | Produces |
|-----------|----------|
| Decontextualization | Standalone form of the current question |
| Query rewrite | More searchable wording |
| Step-back | Broader prerequisite question |
| HyDE | Hypothetical answer-like passage |
| Multi-query | Several alternative question phrasings |

Example:

```text
  Original:            “How does it improve search?”
  Decontextualized:    “How does parent-child chunking improve search?”
  Step-back:           “How does chunk size affect retrieval quality?”
  HyDE:                “Small children improve match precision while larger
                        parents preserve context for generation.”
```

**Takeaway:** HyDE bridges question language to answer-like document language, but real retrieved chunks must remain the only evidence.

---

## Practical learning/implementation order

```
  1. Build a small decontextualization golden set
  2. Add fallback-safe standalone-query rewriting
  3. Add simple factoid / summary / deep / chitchat routing
  4. Log per-intent latency, cost, and retrieval quality
  5. Add HyDE only to the deep lane
  6. A/B HyDE on vs off before keeping it
```

Do not add all techniques at once. Each new branch makes failures harder to locate.

## Advanced techniques still to learn

```
  learned now
  ├─ parent-child chunking          → Ch. 24
  ├─ decontextualization            → Ch. 25
  ├─ intent-based retrieval         → Ch. 26
  └─ HyDE                           → Ch. 27

  next
  ├─ persistent tenant-scoped vector storage
  ├─ multi-hop decomposition + parallel retrieval
  └─ per-intent eval: quality + latency + cost + security
```

These next topics should each become a focused chapter only after we study their mechanics and failure modes.
