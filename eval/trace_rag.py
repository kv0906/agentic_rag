#!/usr/bin/env python3
"""Step-by-step RAG retrieve trace (learning / debug).

Shows every stage of hybrid retrieve + cross-encoder rerank:

  query → vector → BM25 → RRF (wide) → CE rerank → package (char cap) → tool string

Optional: also run the LangGraph agent and print node/tool steps.

Usage (from repo root, venv active):

  python eval/trace_rag.py "Which market statuses appear on the Live Markets page?"
  python eval/trace_rag.py --ids q06
  python eval/trace_rag.py --ids q06 --needles "Live or Approved,Active,Inactive"
  python eval/trace_rag.py --ids q06 --cap 800   # replay old packaging bug
  python eval/trace_rag.py --ids q06 --no-rerank # hybrid only (skip CE)
  python eval/trace_rag.py --ids q02 --agent     # + agent decide/retrieve/grade/answer
  python eval/trace_rag.py --json out.json "What is a binary market?"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
EVAL_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BACKEND))
load_dotenv(ROOT / ".env")
load_dotenv(BACKEND / ".env")

from rag import (  # noqa: E402
    MAX_PASSAGE_CHARS,
    clear_index,
    has_index,
    ingest_pdf,
    retrieve_trace,
    rerank_enabled,
    rerank_model_name,
)

DEFAULT_PDF = Path.home() / "Downloads" / "Huua-MMBot-Playbook Final.pdf"
DEFAULT_GOLDEN = EVAL_DIR / "golden.jsonl"


def load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def ensure_index(pdf: Path) -> None:
    if has_index():
        print(f"[index] already loaded (reuse in-process)")
        return
    if not pdf.is_file():
        raise FileNotFoundError(
            f"PDF not found: {pdf}\n"
            "Pass --pdf or place playbook at ~/Downloads/Huua-MMBot-Playbook Final.pdf"
        )
    # Snapshot first — clear_index wipes backend/data/uploads
    tmp = EVAL_DIR / f".tmp_trace_{pdf.name}"
    shutil.copy2(pdf, tmp)
    try:
        clear_index()
        dest = BACKEND / "data" / "uploads" / f"trace_{pdf.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp, dest)
        meta = ingest_pdf(dest, original_name=pdf.name)
        print(f"[index] ingested {pdf.name} → pages={meta.get('pages')}")
    finally:
        tmp.unlink(missing_ok=True)


def _ascii_block(*lines: str) -> None:
    """Print an indented ASCII diagram block."""
    print()
    for line in lines:
        print(f"  {line}")
    print()


def _bar(filled: int, total: int, width: int = 40) -> str:
    """Simple proportional bar (characters)."""
    if total <= 0:
        return "░" * width
    n = max(0, min(width, round(width * filled / total)))
    return "█" * n + "░" * (width - n)


def _short_q(q: str, n: int = 52) -> str:
    q = q.replace("\n", " ").strip()
    return q if len(q) <= n else q[: n - 1] + "…"


def print_trace(trace: dict) -> None:
    q = trace.get("query", "")
    cap = trace.get("max_passage_chars")
    top_k = trace.get("top_k")

    print()
    print("=" * 72)
    print(f"QUERY: {q}")
    print("=" * 72)

    rerank_on = trace.get("rerank")
    _ascii_block(
        "MAP — hybrid retrieve + cross-encoder (LlamaIndex half)",
        "",
        "  ┌─────────┐   ┌────────┐   ┌──────┐   ┌────────┐   ┌─────────┐   ┌────────┐",
        "  │  INDEX  │──►│ VECTOR │──►│      │──►│ RERANK │──►│ PACKAGE │──►│ RETURN │",
        "  │  nodes  │   │  pool  │   │ RRF  │   │  CE    │   │ char cap│   │ tool   │",
        "  └─────────┘   └────────┘   │ fuse │   │(pair)  │   └─────────┘   │ string │",
        "       │        ┌────────┐   │ wide │   └────────┘                 └────────┘",
        "       └───────►│  BM25  │──►└──────┘        │                          │",
        "                │  pool  │                   ▼                          ▼",
        "                └────────┘            top_k for LLM          grade + answer",
        "",
        f"  query: “{_short_q(q)}”",
        f"  knobs: top_k={top_k}  max_passage_chars={cap}  "
        f"rerank={'ON' if rerank_on else 'OFF'}",
        "",
        "  retrieval quality = right node in shortlist (recall)",
        "  rerank quality    = best pairs rise to top (precision)",
        "  packaging quality = fact still present after char cap",
    )

    for step in trace.get("steps") or []:
        name = step.get("step", "?")
        print()
        print(f"── {name.upper()} " + "─" * max(0, 60 - len(name)))

        if name == "index":
            ok = step.get("ok")
            n_nodes = step.get("n_nodes")
            _ascii_block(
                "Filing cabinet in RAM (not a DB)",
                "",
                "  PDF ──ingest──► [node][node]…[node]   ← VectorStoreIndex + docstore",
                f"                  └─ {n_nodes or 0} nodes ready for search",
                "",
                f"  status: {'OK — search can run' if ok else 'EMPTY — upload a PDF first'}",
            )
            print(f"  ok={ok}  n_nodes={n_nodes}")
            for d in step.get("docs_meta") or []:
                print(f"  doc: {d.get('filename')} pages={d.get('pages')}")

        elif name == "params":
            _ascii_block(
                "Knobs for this run",
                "",
                f"  pool_k       = {step.get('pool_k')}   ← each engine pulls this many",
                f"  candidates_k = {step.get('candidates_k')}   ← RRF shortlist size",
                f"  top_k        = {step.get('top_k')}    ← after CE, keep this many for LLM",
                f"  rrf_k        = {step.get('rrf_k')}   ← 1/(rrf_k + rank)",
                f"  rerank       = {step.get('rerank')}  model={step.get('rerank_model')}",
                f"  cap          = {step.get('max_passage_chars')}  ← max CHARACTERS / passage",
            )
            print(
                f"  top_k={step.get('top_k')}  pool_k={step.get('pool_k')}  "
                f"candidates_k={step.get('candidates_k')}  "
                f"rrf_k={step.get('rrf_k')}  max_passage_chars={step.get('max_passage_chars')}"
            )

        elif name in ("vector", "bm25"):
            kind = "semantic (embeddings)" if name == "vector" else "keyword (BM25 + stemmer)"
            label = "VECTOR" if name == "vector" else "BM25"
            hits = step.get("hits") or []
            n = step.get("n_hits") or 0
            req = step.get("requested")
            _ascii_block(
                f"Path {'A' if name == 'vector' else 'B'}: {kind}",
                "",
                f"  query ──► {label} retriever ──► ranked list (pool)",
                f"             requested {req}  ·  got {n}",
                "",
                "  rank  page   score-ish     preview",
                "  ────  ────   ──────────    ───────",
            )
            # diagram already closed; print hit rows under it
            for h in hits[:12]:
                prev = (h.get("preview") or "").replace("\n", " ")[:56]
                print(
                    f"  #{h.get('rank'):>2}  p.{str(h.get('page')):<4}  "
                    f"{str(h.get('score')):<12}  {prev}"
                )
            if len(hits) > 12:
                print(f"  … +{len(hits) - 12} more (see --json)")
            if hits:
                top_pages = ", ".join(f"p.{h.get('page')}" for h in hits[:5])
                print(f"  top pages: {top_pages}")
            print(
                f"  engine={step.get('engine')}  hits={n}/{req}"
            )

        elif name == "rrf_fuse":
            hits = step.get("hits") or []
            n = step.get("n_fused") or 0
            rk = step.get("rrf_k")
            cand = step.get("candidates_k")
            _ascii_block(
                "Fuse ranks (not raw scores) — Reciprocal Rank Fusion",
                "",
                "  vector ranks:  #1  #2  #3  …",
                "  bm25 ranks:    #1  #2  #3  …",
                "        │",
                f"        ▼  score += 1/({rk}+rank)   per list the chunk appears in",
                "  fused shortlist (higher RRF = better)",
                f"        │  keep candidates_k={cand} → {n} passages (wide for CE)",
                "        ▼",
                "  [p.?] [p.?] …  methods: vector / bm25 / both",
            )
            print(
                f"  {step.get('formula')}  rrf_k={rk}  fused={n}"
            )
            for h in hits:
                print(
                    f"  #{h.get('rank'):>2} page={h.get('page')!s:>4} "
                    f"rrf={h.get('rrf_score')}  methods={h.get('methods')}  "
                    f"chars={h.get('chars')}"
                )

        elif name == "rerank":
            hits = step.get("hits") or []
            applied = step.get("applied")
            _ascii_block(
                "Cross-encoder rerank — scores (query, passage) pairs",
                "",
                "  bi-encoder / BM25 / RRF   =  fast shortlist (recall)",
                "  cross-encoder            =  read query+doc together (precision)",
                "",
                "  candidates ──► CE ──► top_k for grade/answer",
                f"  model: {step.get('model') or '—'}",
                f"  in={step.get('n_in')} → out={step.get('n_out')}  "
                f"applied={applied}",
            )
            if not applied:
                print(f"  skipped: {step.get('reason')}")
            for h in hits:
                print(
                    f"  #{h.get('rank'):>2} page={h.get('page')!s:>4} "
                    f"ce={h.get('rerank_score')}  rrf={h.get('rrf_score')}  "
                    f"methods={h.get('methods')}"
                )

        elif name == "package":
            cap_n = step.get("max_passage_chars") or 0
            n_pass = step.get("n_passages") or 0
            n_trunc = step.get("n_truncated") or 0
            passages = step.get("passages") or []
            any_lost = any(
                any((p.get("packaging_loss") or {}).values()) for p in passages
            )

            _ascii_block(
                "Packaging — this is where char cap can drop a gold fact",
                "",
                "  fused node (full text in index)",
                "       │",
                f"       ▼  if len > {cap_n}: keep first {cap_n} chars + \"…\"",
                "  passage card  →  tool string  →  grade / answer",
                "",
                "  ký tự:  1 ········· cap ········· end",
                "          |  model sees  |  CUT AWAY  |",
                "",
                f"  this run: {n_pass} passages · {n_trunc} truncated · "
                f"{'⚠ packaging LOSS' if any_lost else 'no needle loss detected'}",
            )

            print(
                f"  max_passage_chars={cap_n}  "
                f"passages={n_pass}  truncated={n_trunc}"
            )
            print()
            print(
                f"  {'#':>2}  {'page':>4}  {'raw':>5}  {'cap':>5}  "
                f"{'cut?':>5}  {'loss':>6}  methods"
            )
            print(f"  {'─'*2}  {'─'*4}  {'─'*5}  {'─'*5}  {'─'*5}  {'─'*6}  ───────")
            for p in passages:
                if p.get("skipped"):
                    print(f"  {p.get('passage'):>2}  skip: {p.get('reason')}")
                    continue
                loss = p.get("packaging_loss") or {}
                lost = any(loss.values()) if loss else False
                raw_c = int(p.get("raw_chars") or 0)
                print(
                    f"  {p.get('passage'):>2}  {str(p.get('page')):>4}  "
                    f"{raw_c:>5}  {p.get('capped_chars'):>5}  "
                    f"{'YES' if p.get('truncated') else 'no':>5}  "
                    f"{'LOST' if lost else ('ok' if loss else '—'):>6}  "
                    f"{p.get('methods')}"
                )
                # Mini bar: how much of the node survived the cap
                if cap_n:
                    kept = min(raw_c, cap_n)
                    print(f"       [{_bar(kept, max(raw_c, cap_n))}] "
                          f"{kept}/{raw_c} chars kept")
                if p.get("needle_in_raw") or p.get("needle_in_packaged"):
                    print(f"       raw needles:       {p.get('needle_in_raw')}")
                    print(f"       packaged needles:  {p.get('needle_in_packaged')}")
                    if lost:
                        print(f"       packaging_loss:    {loss}")
                        print()
                        print("       LOST diagram (this passage):")
                        print(
                            f"         1 ········· {cap_n} ····· … ········· {raw_c}"
                        )
                        print(
                            "         |  still sent   |  CUT — needles here may vanish |"
                        )
                        print(f"         tail after cut would include: "
                              f"…{p.get('tail_preview')!r}")

        elif name == "return":
            ok = step.get("ok")
            n_chars = step.get("tool_string_chars") or 0
            n_pass = step.get("n_passages")
            needles = step.get("needle_in_tool_string") or {}
            hit = [k for k, v in needles.items() if v]
            miss = [k for k, v in needles.items() if not v]
            _ascii_block(
                "Hand-off to the agent",
                "",
                "  tool string  ──►  grade_documents  ──yes──►  generate_answer",
                "                         │ no",
                "                         └──► rewrite_question ──► retrieve again",
                "",
                f"  payload size: {n_chars} chars · {n_pass} passage cards",
                f"  status: {'OK' if ok else 'FAILED / empty'}",
            )
            if needles:
                print("  needles in FINAL tool string:")
                for k, v in needles.items():
                    mark = "✓" if v else "✗"
                    print(f"    {mark}  {k}")
                if miss:
                    _ascii_block(
                        "⚠ Some gold phrases never reached the model",
                        "",
                        f"  missing: {miss}",
                        "  → check PACKAGE step (truncation) or RRF (never ranked)",
                        "  → this is packaging/retrieval, not “model is dumb”",
                    )
                elif hit:
                    print("  (all tracked needles present in tool string)")
            print(
                f"  ok={ok}  tool_string_chars={n_chars}  n_passages={n_pass}"
            )

        else:
            print(f"  {json.dumps(step, ensure_ascii=False)[:200]}")

    print()
    print("── TOOL STRING (what grade/answer see) " + "─" * 30)
    _ascii_block(
        "This block = evidence the LLM is allowed to use",
        "",
        "  if a fact is missing here, answer cannot cite it faithfully",
    )
    ts = trace.get("tool_string") or ""
    # Keep console readable; full string is in --json
    if len(ts) > 2500:
        print(ts[:2500] + f"\n… [{len(ts) - 2500} more chars — use --json for full]")
    else:
        print(ts)
    print()
    _ascii_block(
        "Done — re-read map",
        "",
        "  INDEX → VECTOR+BM25 → RRF(wide) → CE rerank → PACKAGE(cap) → RETURN",
        "  Debug tip: in shortlist? → CE top? → packaging keep the fact?",
    )


def print_agent(question: str) -> dict:
    from agent import run_agent

    print()
    print("=" * 72)
    print("AGENT (LangGraph process — not LlamaIndex search)")
    print("=" * 72)
    _ascii_block(
        "LangGraph loop",
        "",
        "                 ┌──────────────────────────┐",
        "                 │ generate_query_or_respond│",
        "                 │  (decide: tool or chat)  │",
        "                 └────────────┬─────────────┘",
        "                    tool?     │     no tool",
        "                 ┌────────────┘             └──► END",
        "                 ▼",
        "           ┌──────────┐",
        "           │ retrieve │  ← hybrid tool (see trace above)",
        "           └────┬─────┘",
        "                ▼",
        "        ┌───────────────┐",
        "        │ grade_docs    │  yes → generate_answer → END",
        "        │ (relevant?)   │  no  → rewrite ─┐",
        "        └───────────────┘                 │",
        "                ▲                         │",
        "                └─────────────────────────┘",
    )
    out = run_agent(question)
    steps = out.get("steps") or []
    print("  live path this run:")
    for i, s in enumerate(steps, start=1):
        node = s.get("node") or s.get("type") or "?"
        stype = s.get("type")
        preview = (s.get("content") or s.get("summary") or "")[:160]
        preview = preview.replace("\n", " ")
        tools = s.get("tool_calls") or []
        arrow = "└─►" if i == len(steps) else "├─►"
        print(f"  {arrow} [{i}] {node} ({stype})")
        if tools:
            for tc in tools:
                print(f"         tool={tc.get('name')} args={tc.get('args')}")
        if preview:
            print(f"         {preview}")
    answer = (out.get("answer") or "")[:500]
    print()
    _ascii_block(
        "Final answer (user-facing)",
        "",
        f"  “{_short_q(answer, 60)}”",
    )
    print(f"  ANSWER: {answer}")
    print()
    return out

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trace hybrid retrieve (and optional agent) step by step"
    )
    parser.add_argument("question", nargs="?", default="", help="Query text")
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated golden ids (e.g. q02,q06) — uses question from golden.jsonl",
    )
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--pdf", type=Path, default=Path(os.getenv("EVAL_PDF", str(DEFAULT_PDF))))
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--cap",
        type=int,
        default=MAX_PASSAGE_CHARS,
        help=f"max chars per passage when packaging (default {MAX_PASSAGE_CHARS})",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Skip cross-encoder (hybrid RRF only) for A/B comparison",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Force cross-encoder on (default follows RAG_RERANK env, usually on)",
    )
    parser.add_argument(
        "--needles",
        default="",
        help='Comma-separated phrases to track through packaging, e.g. "Live or Approved,Active"',
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Also run LangGraph agent and print node/tool steps",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write full trace JSON to this path",
    )
    parser.add_argument(
        "--reuse-index",
        action="store_true",
        help="Do not clear/re-ingest if index already warm (same process only)",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing", file=sys.stderr)
        return 1

    questions: list[tuple[str, str]] = []  # (label, question)
    if args.ids.strip():
        golden = {r["id"]: r for r in load_golden(args.golden)}
        for cid in [x.strip() for x in args.ids.split(",") if x.strip()]:
            if cid not in golden:
                print(f"Unknown id: {cid}", file=sys.stderr)
                return 1
            row = golden[cid]
            questions.append((cid, row["question"]))
            # auto-needles from golden if user did not pass --needles
            if not args.needles:
                auto = list(row.get("must_have_in_chunks") or []) + list(
                    row.get("must_have") or []
                )
                # de-dupe preserve order
                seen: set[str] = set()
                uniq: list[str] = []
                for n in auto:
                    k = n.lower()
                    if k not in seen:
                        seen.add(k)
                        uniq.append(n)
                args.needles = ",".join(uniq)
    elif args.question.strip():
        questions.append(("q", args.question.strip()))
    else:
        parser.error("Provide a question or --ids q06")

    needles = [n.strip() for n in args.needles.split(",") if n.strip()]

    if not args.reuse_index or not has_index():
        ensure_index(args.pdf)
    else:
        print("[index] --reuse-index and warm")

    if args.no_rerank and args.rerank:
        print("Pick at most one of --rerank / --no-rerank", file=sys.stderr)
        return 1
    use_rerank: bool | None
    if args.no_rerank:
        use_rerank = False
    elif args.rerank:
        use_rerank = True
    else:
        use_rerank = None  # follow env default
    print(
        f"[rerank] default_env={rerank_enabled()} model={rerank_model_name()} "
        f"this_run={use_rerank if use_rerank is not None else 'env'}"
    )

    all_payloads: list[dict] = []
    for label, question in questions:
        print(f"\n### case {label}")
        if needles:
            print(f"tracking needles: {needles}")
        trace = retrieve_trace(
            question,
            top_k=args.top_k,
            max_passage_chars=args.cap,
            needles=needles,
            use_rerank=use_rerank,
        )
        print_trace(trace)
        payload: dict = {"id": label, "retrieve_trace": trace}

        if args.agent:
            agent_out = print_agent(question)
            payload["agent"] = {
                "answer": agent_out.get("answer"),
                "steps": agent_out.get("steps"),
            }

        all_payloads.append(payload)

    if args.json:
        args.json.write_text(
            json.dumps(all_payloads if len(all_payloads) > 1 else all_payloads[0], indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
