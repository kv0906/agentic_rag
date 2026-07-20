# Agent evals — foundation + core philosophy

> Part of the [learning hub](./README.md).  
> Locked mental models for evaluating agentic systems.

**Chapters:** Ch. 22 (six categories) · Ch. 23 (core philosophy)

---

## Chapter 23 — Core philosophy (locked)

**Human understands intention, goal, and direction → harness the system toward TRUST and RELIABILITY.**

### The one picture

```
  HUMAN                         HARNESS
  ─────                         ───────
  intention                     evals · goldens · asserts
  goal                          traces · CI gates · canaries
  direction                     review queues · new cases
           \                   /
            \                 /
             ▼               ▼
              TRUST + RELIABILITY
```

| Word | Meaning |
|------|---------|
| **Intention** | Why this agent exists; what “good” means for real users |
| **Goal** | Concrete success, safety, and cost targets |
| **Direction** | Which failures matter next; where to invest quality work |
| **Harness** | Automated checks, gates, and feedback loops that enforce the above at scale |
| **Trust** | Users (and teammates) can believe answers and behavior |
| **Reliability** | Quality holds as models, data, prompts, and traffic change |

### What this is *not*

```
  ❌  “AI judges replace humans”
  ❌  “Thumbs / vibes only”
  ❌  “Score final prose and ship”

  ✅  Humans define the destination
  ✅  Harness keeps the agent pointed there
  ✅  Periodic human audit recalibrates the harness
```

### Loop over time

```
  understand  →  define (gold / 6 categories / budgets)
              →  harness (auto eval + gates + traces)
              →  audit (sample failures, fix gold & judges)
              →  trust & reliability compound
```

| Human owns | Machine / harness owns |
|------------|-------------------------|
| Intention — what good means | Run checks at scale |
| Goal — success, safety, cost | CI, canary, rollback signals |
| Direction — priority of fixes | Turn labeled failures into regression cases |

### Standing one-liner

> Evals encode human judgment so an agentic system can be steered toward **trust** and **reliability** — not so judgment disappears.

---

## Chapter 22 — Six foundation eval categories

**Q: What should we score when evaluating an agentic system?**

### Core principle

```
  Classic LLM eval              Agentic eval
  ────────────────              ────────────
  one prompt → one text         plan → tools → retries → answer
  score final prose only        score OUTCOME + PROCESS + …
```

Treat the agent as a **small system**, not a single model call. Quality is multi-dimensional.

### Foundation categories (locked)

```
  ┌─────────────────────────────────────────────────────┐
  │  OUTCOME      Did the user get the right result?    │
  │  PROCESS      Did it use tools / steps sanely?      │
  │  GROUNDING    Are claims backed by evidence?        │
  │  SAFETY       Auth, PII, destructive actions?       │
  │  EFFICIENCY   Latency, $ , #steps, retries?         │
  │  UX           Clarified? refused? cited?            │
  └─────────────────────────────────────────────────────┘
```

These six boxes are **how intention becomes measurable**.  
Philosophy (Ch. 23) says *why* we eval; categories (Ch. 22) say *what* we measure.

| Category | Question | Example signals |
|----------|----------|-----------------|
| **OUTCOME** | Right result for the user goal? | Task success, must-have answer facts, business event resolved |
| **PROCESS** | Tools / steps sane? | Right tool called, no thrash/loops, stayed in step budget, grade→rewrite only when needed |
| **GROUNDING** | Claims backed by evidence? | Faithfulness, citation spans in retrieved text, no invent-from-nowhere |
| **SAFETY** | Auth, PII, destructive actions? | Forbidden tools never called, tenant/project scope, no leaked secrets |
| **EFFICIENCY** | Latency, $, steps, retries? | p95 latency, $/task, tool count, rewrite loops |
| **UX** | Clarify / refuse / cite well? | Asked when underspecified, “don’t know” when no evidence, page citations not “chunk 3” |

### Why all six (not only outcome)

```
  Outcome only:
    “Sounds right” but used 20 tools, ignored docs, or skipped auth

  All six:
    Useful + honest + safe + affordable + usable
    → path to TRUST + RELIABILITY
```

### How this maps to *this* repo (today)

| Category | Where it shows up |
|----------|-------------------|
| OUTCOME | `eval/golden.jsonl` answer must-haves; Ragas-ish checks |
| PROCESS | LangGraph path: decide → retrieve → grade → rewrite (trace / agent steps) |
| GROUNDING | `must_have_in_chunks`, citations, faithfulness-style metrics |
| SAFETY | (light) — no multi-tenant yet; expand when multi-user/tools grow |
| EFFICIENCY | top_k, rewrite caps, passage caps, rerank cost |
| UX | page citations, coach voice, Sources UI |

Code anchors: `eval/README.md`, `eval/golden.jsonl`, `eval/run_ragas.py`, `eval/trace_rag.py`, `backend/agent.py`.

### Eval pyramid (reminder)

```
                    ▲  rare, expensive
                   / \     Human review (intention / calibration)
                  /   \
                 /─────\   Online: thumbs, traces, escalations
                /       \
               /─────────\ Offline E2E golden + judge
              /───────────\ Component: retrieve / tools
             /─────────────\ Unit: schemas, prompts
            ▼  frequent, cheap  ← harness at scale
```

Score **categories** at every layer you can: e.g. PROCESS at component (tool choice), GROUNDING at retrieve Hit@k + answer faithfulness, OUTCOME at E2E.

### Takeaway

1. **Ch. 23** — Humans set intention, goal, direction; harness steers toward trust & reliability.  
2. **Ch. 22** — Measure with six boxes: outcome, process, grounding, safety, efficiency, UX.  
3. Do not collapse eval into “answer quality” alone.

---
