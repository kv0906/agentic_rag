# Golden eval set — Huua MMBot Playbook

Source document (local):

```
/Users/van/Downloads/Huua-MMBot-Playbook Final.pdf
```

Playbook: **MMBot · Market Making Platform — External User Playbook v1.0 (July 2026)**.  
47 pages. Marked confidential in the PDF — keep the file and extracts off public remotes if needed.

## Files

| File | Purpose |
|------|---------|
| `golden.jsonl` | 25 eval cases (one JSON object per line) |
| `_playbook_extract.txt` | Optional full text dump for authoring (gitignored) |
| `README.md` | This guide |

## How to use in the app

1. Start API + UI.
2. Upload **Huua-MMBot-Playbook Final.pdf** via the chat paperclip.
3. Ask questions from `golden.jsonl` (`question` field).
4. Score by hand using the fields below.

## Field guide

| Field | Meaning |
|-------|---------|
| `id` | Stable case id (`q01`…) |
| `category` | Topic bucket |
| `question` | What you type in the UI |
| `gold_answer` | Ideal grounded answer (human reference) |
| `must_have` | Substrings that should appear in a **good final answer** (case-insensitive OK when scoring) |
| `must_have_in_chunks` | Substrings that should appear in **retrieved tool text** (retrieval Hit@k) |
| `gold_pages` | Playbook pages (1-based) where the fact lives |
| `should_retrieve` | `true` → agent should call retrieve; `false` → greeting / off-topic skip |
| `difficulty` | easy / medium / hard |
| `notes` | Optional scoring hints |

## Suggested manual scorecard (per question)

```
  [ ] should_retrieve respected?     (routing)
  [ ] Hit@8: must_have_in_chunks     (retrieval / hybrid)
  [ ] Answer has must_have           (correctness checklist)
  [ ] Faithful: no invented numbers  (grounding)
  [ ] Notes / freeform pass-fail
```

Quick pass rate:

```
  retrieval_hits / questions_with_must_have_in_chunks
  answer_passes  / questions_with_must_have
  routing_ok     / all questions
```

## Case mix (25)

| Category | Count | Why |
|----------|------:|-----|
| overview / terms | 4 | Easy semantic retrieval |
| navigation / UI | 7 | Screen workflows |
| strategies + numbers | 9 | **BM25-friendly** (distances, $, %) |
| workflow | 1 | End-to-end advice |
| routing (no docs) | 2 | `hello`, weather |
| negative / absent | 1 | Should not hallucinate API limits |

Hard cases with exact numbers (good hybrid tests): **q15–q21**.

## After you test

Record results in a simple sheet or `eval/results-YYYYMMDD.md`:

| id | retrieve? | Hit chunks | answer OK | notes |
|----|-----------|------------|-----------|-------|
| q01 | yes | yes | yes | |
| … | | | | |

## Trace retrieve step-by-step (learning / debug)

See **every stage** of hybrid retrieve (vector → BM25 → RRF → **char-cap packaging** → tool string):

```bash
source .venv/bin/activate

# By golden id (auto tracks must_have needles)
python eval/trace_rag.py --ids q06

# Replay the old packaging bug (NOTE cut at 800)
python eval/trace_rag.py --ids q06 --cap 800

# Free-form question + optional agent graph
python eval/trace_rag.py "What is a binary market?" --agent

# Full JSON dump
python eval/trace_rag.py --ids q06 --json /tmp/trace-q06.json
```

| Step in log | Meaning |
|-------------|---------|
| `index` | In-memory nodes loaded |
| `vector` / `bm25` | Each engine’s ranked pool |
| `rrf_fuse` | Wide fused shortlist (`candidates_k`, default 20) |
| `rerank` | Cross-encoder reorders pairs → `top_k` (default 8); `--no-rerank` to skip |
| `package` | Per-passage `raw_chars` vs cap; **LOST** = needle in node but cut by cap |
| `return` | Final tool string length + needles present? |

Related aha: `docs/LEARNING_JOURNEY.md` Ch. 17 (packaging vs retrieval).

## Automated eval with Ragas

Uses [Ragas](https://docs.ragas.io/en/stable/getstarted/rag_eval/) metrics on **our** hybrid agentic RAG (not a toy in-memory RAG):

| Ragas field | From our system |
|-------------|-----------------|
| `user_input` | golden `question` |
| `retrieved_contexts` | `rag.retrieve()` hybrid chunks |
| `response` | `run_agent()` final answer |
| `reference` | golden `gold_answer` |

Metrics: **context_recall**, **faithfulness**, **factual_correctness**.

```bash
source .venv/bin/activate
# optional: smaller / cheaper first pass
python eval/run_ragas.py --limit 5 --only-retrieve

# full golden set (retrieve-worthy questions only)
python eval/run_ragas.py --only-retrieve

# all 25 including greetings / off-topic
python eval/run_ragas.py
```

Reports land in `eval/results-ragas-*.md` (+ `.json`). Gitignored.

**Note:** Full runs cost OpenAI tokens (agent + Ragas judge per question). Prefer `--limit 5` while iterating.
