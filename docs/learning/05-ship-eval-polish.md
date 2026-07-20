# Ship, eval & product polish

> Part of the [learning hub](./README.md).  
> 2026 practices, Tier-1 defaults, golden set + Ragas, citations/voice, day wrap, eval gap fixes.

**Chapters:** Ch. 13, Ch. 14, Ch. 15, Ch. 16, Ch. 17

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
  CE rerank → top-8         rerank before grade/answer  ◄── shipped
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
│ tool call       │────►│ vector + BM25 → RRF → CE → 8 │
│ grade (judge)   │◄────│ Document + Page passages     │
│ rewrite         │     │ in-memory VectorStoreIndex   │
│ answer + next   │     └──────────────────────────────┘
└─────────────────┘
         │
         ▼
  UI: stream phases · tool summary · Sources (p.N · file)
  Eval: golden.jsonl + Ragas (recall / faith / factual)

  2026 funnel:  hybrid (recall) → CE rerank (precision) → LLM (generate)
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
| **Passage cap** | Max **characters** per passage in tool string (`rag.retrieve`); packaging, not rank |
| **Packaging** | Did the fact survive from index → tool string → LLM? (≠ “did hybrid rank it?”) |
| **Rerank (CE)** | Cross-encoder scores (query, passage) pairs; precision after hybrid recall |
| **candidates_k** | Wide RRF shortlist (default 20) fed into CE before cutting to top_k |

---

## Chapter 17 — Fix eval gaps (q02 routing + q06 truncation)

### Q: Fix q02 / q06, then re-run Ragas (watch factual_correctness)

**Hai bug khác nhau (đừng gộp)**

```
  q02  "What is a binary market?"
  ─────────────────────────────
  Symptom: decide bỏ retrieve → trả lời kiến thức chung
  Fix:     docs có sẵn thì BẮT BUỘC tool cho glossary / "what is X?"
           (decide system + tool docstring)

  q06  "Which market statuses appear on Live Markets?"
  ───────────────────────────────────────────────────
  Symptom: trả lời All / Active / Inactive (filter UI)
  Real bug: NOTE "Live or Approved" nằm sau char 800 → bị cắt
  Fix:     passage cap 800 → 2000 + generate: ưu tiên NOTE /
           eligibility hơn filter chrome
```

---

### Walkthrough q06 — từng bước (memory teaching style)

Dùng lại khi debug “answer sai dù retrieval có vẻ hit”.

#### Bước 1 — Câu hỏi eval

```
  Q: Which market statuses appear on the Live Markets page?

  Gold (đáp án đúng trong playbook):
  → Chỉ market Live hoặc Approved mới hiện
  → Proposed / rejected thì không hiện
```

#### Bước 2 — Playbook viết gì (trang 6)

```
  ┌─ PAGE 6 (một đoạn index, ~955 ký tự) ─────────────────┐
  │  Live Markets là gì…                                   │
  │  Binary / Multi-outcome tabs…                          │
  │  ...                                                   │
  │  NOTE: Only markets that are Live or Approved          │  ◄── đáp án
  │        appear… Proposed or rejected are not shown.     │
  └────────────────────────────────────────────────────────┘
```

#### Bước 3 — Hybrid retrieve làm đúng phần “tìm”

```
  Câu hỏi ──► vector + BM25 ──► RRF ──► top-8

  Trong top-8 có Passage từ page 6  ✓
  (node trong index VẪN CÒN full text, kể cả NOTE)
```

→ **Retrieval quality = OK.** Lỗi không nằm ở hybrid.

#### Bước 4 — Lỗi nằm ở bước “cắt cho gọn” (cũ)

Trong `retrieve()`, trước đây:

```
  if độ dài > 800:
      giữ 800 ký tự đầu + "…"
```

**800 / 2000 = số ký tự (characters)** tối đa **một passage** khi ghép tool string —  
**không phải** token, không phải `top_k`, không phải RRF `k=60`.

Vị trí thật của NOTE:

```
  ký tự:  1 ········· 800 ····· 862 ········· 955
          | intro + tabs… |      | NOTE Live…     |
                          ▲
                          └── CẮT TẠI ĐÂY (cap 800)

  1–800:   model thấy
  862+:    NOTE  →  BỊ MẤT (không vào tool string)
```

ASCII so sánh:

```
  TRƯỚC (cap 800)
  ════════════════
  [Live Markets intro………… tabs………… Multi-outcome…]…
                                                   ▲
                                              hết 800, NOTE đã mất

  SAU (cap 2000)
  ══════════════
  [Live Markets intro………… tabs………… NOTE Live or Approved…]
                                                    ▲
                                              NOTE còn nguyên
```

#### Bước 5 — Model trả lời dựa trên thứ nó **còn** thấy

```
  Tool string (cũ) có gì?
    ✓  Active / Inactive  (filter UI, trang khác / đoạn khác)
    ✗  Live or Approved   (NOTE bị cắt)

  Model trung thành với context → trả lời:
    "All / Active / Inactive"
  → trông như “sai kiến thức”, thực ra là “thiếu bằng chứng”

  Agent (cũ)
  ──────────
  context_thấy = [filter Active/Inactive]
  gold_cần     = [Live or Approved]
  → answer_must_have FAIL
```

#### Bước 6 — Vì sao chọn 2000 (không phải “vô hạn”)

```
  800    →  trang ngắn vẫn mất phần cuối (NOTE ở ~862)
  ~1000  →  vừa khít page 6 (~955) — mong manh
  2000   →  đủ cho 1 page ngắn + chút dư
  ∞      →  tốt về đầy đủ, nhưng tool dump dài/ồn nếu chunk to

  top_k = 8  →  tối đa ~ 8 × 2000 ký tự  (vẫn ổn cho model)
```

Cap ban đầu là **giới hạn UX** (đỡ spam UI/tool), **không phải** thuật toán rank.  
Tăng 2000 = **sửa đóng gói (packaging)**, **không đổi hybrid**.

---

### Hai lớp chất lượng (đừng gộp một)

```
  1) Retrieval quality          2) Packaging quality
  ────────────────────          ────────────────────
  Node đúng có rank cao?        Fact còn được GỬI tới LLM?
         │                              │
         ▼                              ▼
    hybrid / RRF / top_k          passage char cap
    (q06: page 6 đã hit)          (q06 fail cũ: cắt mất NOTE)
```

| Số | Nghĩa |
|----|--------|
| **800 / 2000** | Cắt mỗi passage ở tối đa bao nhiêu **ký tự** (`_MAX_PASSAGE_CHARS` trong `rag.py`) |
| **top_k = 8** | Lấy **bao nhiêu đoạn** sau RRF |
| **RRF k = 60** | Hằng số trong `1/(60+rank)` |
| **tokens** | Đơn vị model (khác; không 1:1 với ký tự) |

| File | Change |
|------|--------|
| `backend/agent.py` | Decide: retrieve terms/UI when docs yes; generate: NOTE vs filters |
| `backend/rag.py` | Soft cap `_MAX_PASSAGE_CHARS = 2000` (was 800) |
| `eval/run_ragas.py` | `--ids`; safe PDF snapshot before `clear_index`; Passage split |

**Ragas re-run (23 `should_retrieve` cases)**

| Metric | Baseline (prev day) | After fix |
|--------|--------------------:|----------:|
| context_recall | ~0.85 | **0.93** |
| faithfulness | ~0.78 | **0.80** |
| factual_correctness | ~0.55 | **0.58** |
| Routing checklist | 22/23 (96%) | **23/23 (100%)** |
| Chunk must_have | 19/23 (83%) | **22/23 (96%)** |
| Answer must_have | 19/23 (83%) | **21/23 (91%)** |

q02 + q06 both pass routing / chunks / answer on the checklist.  
Remaining answer misses: **q04** (must_have wording), **q15** (Group 1 numbers).  
Report: `eval/results-ragas-20260715-085521.md`.

**Takeaways (project memory)**

1. “Wrong answer” đôi khi = **packaging** (truncation), không phải model dốt — check gold phrase **có trong tool string không**.  
2. **800 / 2000 = max characters / passage** trong `retrieve()`, không phải tokens / top_k / RRF k.  
3. Debug path: **rank OK?** → rồi mới hỏi **packaging còn giữ fact?**  
4. Prefer walkthrough **từng bước + ASCII** khi giải thích packaging vs retrieval (style học tốt cho Van).

---

