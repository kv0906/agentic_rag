#!/usr/bin/env python3
"""Run Ragas eval against eval/golden.jsonl using *this* project's RAG.

Flow (same idea as Ragas docs, but our hybrid agentic stack):

  golden questions
       │
       ▼
  ingest playbook PDF → rag.retrieve (hybrid) + agent.run_agent
       │
       ▼
  EvaluationDataset  {user_input, retrieved_contexts, response, reference}
       │
       ▼
  ragas.evaluate → context_recall, faithfulness, factual_correctness

Usage (from repo root, venv active):

  python eval/run_ragas.py
  python eval/run_ragas.py --limit 5
  python eval/run_ragas.py --pdf "/path/to/playbook.pdf"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
EVAL_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BACKEND))
load_dotenv(ROOT / ".env")
load_dotenv(BACKEND / ".env")

# Import project modules after path + env
from agent import run_agent  # noqa: E402
from rag import clear_index, ingest_pdf, retrieve  # noqa: E402


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


def split_contexts(retrieve_text: str) -> list[str]:
    """Turn our joined tool string into a list of chunk strings for Ragas."""
    if not retrieve_text or retrieve_text.startswith("No documents"):
        return []
    text = retrieve_text.strip()
    # Current format: "### Passage N" cards; legacy: "[Chunk N]"
    if "### Passage " in text:
        parts = re.split(r"\n\n(?=### Passage )", text)
    else:
        parts = re.split(r"\n\n(?=\[Chunk )", text)
    return [p.strip() for p in parts if p.strip()]


def must_have_hit(text: str, needles: list[str]) -> bool:
    if not needles:
        return True
    low = text.lower()
    return all(n.lower() in low for n in needles)


def ingest_playbook(pdf: Path) -> None:
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")
    # Snapshot first: clear_index() wipes backend/data/uploads, which may be the source.
    tmp = EVAL_DIR / f".tmp_eval_{pdf.name}"
    shutil.copy2(pdf, tmp)
    try:
        clear_index()
        dest = BACKEND / "data" / "uploads" / f"eval_{pdf.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp, dest)
        meta = ingest_pdf(dest, original_name=pdf.name)
        print(f"Ingested {pdf.name} → pages={meta.get('pages')}")
    finally:
        tmp.unlink(missing_ok=True)


def collect_dataset(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Run our RAG for each case; return (ragas rows, row details)."""
    dataset: list[dict] = []
    details: list[dict] = []

    for i, case in enumerate(cases, start=1):
        cid = case.get("id", f"row{i}")
        q = case["question"]
        print(f"[{i}/{len(cases)}] {cid}: {q[:70]}…")

        # Hybrid retrieve (same tool body as agent)
        raw_ctx = retrieve(q)
        contexts = split_contexts(raw_ctx)

        # Full agentic path (decide → retrieve → grade → answer)
        try:
            out = run_agent(q)
            answer = out.get("answer") or ""
            steps = out.get("steps") or []
        except Exception as exc:  # noqa: BLE001
            answer = f"[agent error] {exc}"
            steps = []

        did_retrieve = any(
            s.get("type") == "tool"
            or (s.get("type") == "ai" and s.get("tool_calls"))
            for s in steps
        )

        row = {
            "user_input": q,
            "retrieved_contexts": contexts if contexts else [""],
            "response": answer,
            "reference": case.get("gold_answer") or "",
        }
        dataset.append(row)

        detail = {
            "id": cid,
            "category": case.get("category"),
            "should_retrieve": case.get("should_retrieve", True),
            "did_retrieve": did_retrieve,
            "routing_ok": (
                did_retrieve is True
                if case.get("should_retrieve", True)
                else did_retrieve is False
            ),
            "chunk_must_have_ok": must_have_hit(
                raw_ctx, case.get("must_have_in_chunks") or []
            ),
            "answer_must_have_ok": must_have_hit(answer, case.get("must_have") or []),
            "n_contexts": len(contexts),
            "answer_preview": answer[:240].replace("\n", " "),
        }
        details.append(detail)
        print(
            f"    contexts={detail['n_contexts']} routing_ok={detail['routing_ok']} "
            f"chunks_ok={detail['chunk_must_have_ok']} ans_ok={detail['answer_must_have_ok']}"
        )

    return dataset, details


def run_ragas(dataset: list[dict], model: str):
    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import FactualCorrectness, Faithfulness, LLMContextRecall

    evaluation_dataset = EvaluationDataset.from_list(dataset)
    llm = ChatOpenAI(model=model, temperature=0)
    evaluator_llm = LangchainLLMWrapper(llm)

    result = evaluate(
        dataset=evaluation_dataset,
        metrics=[
            LLMContextRecall(),
            Faithfulness(),
            FactualCorrectness(),
        ],
        llm=evaluator_llm,
    )
    return result


def write_report(
    path: Path,
    result,
    details: list[dict],
    model: str,
    pdf: Path,
) -> None:
    # Ragas result behaves like a mapping / has scores
    try:
        scores = dict(result)
    except Exception:  # noqa: BLE001
        scores = {"raw": str(result)}

    lines = [
        f"# Ragas eval report",
        f"",
        f"- **When:** {datetime.now(timezone.utc).isoformat()}",
        f"- **PDF:** `{pdf}`",
        f"- **Judge model:** `{model}`",
        f"- **Cases:** {len(details)}",
        f"",
        f"## Ragas scores",
        f"",
        f"```",
        f"{scores}",
        f"```",
        f"",
        f"## Checklist (from golden set)",
        f"",
    ]

    routing = sum(1 for d in details if d["routing_ok"])
    chunks = sum(1 for d in details if d["chunk_must_have_ok"])
    answers = sum(1 for d in details if d["answer_must_have_ok"])
    n = len(details) or 1
    lines += [
        f"| Check | Pass rate |",
        f"|-------|----------:|",
        f"| Routing (`should_retrieve`) | {routing}/{len(details)} ({100*routing/n:.0f}%) |",
        f"| Chunk `must_have_in_chunks` | {chunks}/{len(details)} ({100*chunks/n:.0f}%) |",
        f"| Answer `must_have` | {answers}/{len(details)} ({100*answers/n:.0f}%) |",
        f"",
        f"## Per case",
        f"",
        f"| id | routing | chunks | answer | n_ctx | preview |",
        f"|----|---------|--------|--------|------:|---------|",
    ]
    for d in details:
        prev = d["answer_preview"].replace("|", "/")[:80]
        lines.append(
            f"| {d['id']} | {d['routing_ok']} | {d['chunk_must_have_ok']} | "
            f"{d['answer_must_have_ok']} | {d['n_contexts']} | {prev} |"
        )

    lines += [
        f"",
        f"## Metric meanings (Ragas)",
        f"",
        f"| Metric | What it measures |",
        f"|--------|------------------|",
        f"| **context_recall** | Did retrieved context cover the reference answer? |",
        f"| **faithfulness** | Is the response grounded in retrieved context (not hallucinated)? |",
        f"| **factual_correctness** | Does the response match the gold reference? |",
        f"",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ragas eval for agentic-rag")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(os.getenv("EVAL_PDF", str(DEFAULT_PDF))),
        help="Playbook PDF path",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=DEFAULT_GOLDEN,
        help="golden.jsonl path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only first N cases (0 = all)",
    )
    parser.add_argument(
        "--only-retrieve",
        action="store_true",
        help="Only cases with should_retrieve=true (recommended for Ragas)",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated case ids (e.g. q02,q06). Empty = all after other filters.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        help="Judge + already used by agent via env",
    )
    parser.add_argument(
        "--skip-ragas",
        action="store_true",
        help="Only run checklist collection (no Ragas judge LLM)",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing", file=sys.stderr)
        return 1

    cases = load_golden(args.golden)
    if args.only_retrieve:
        cases = [c for c in cases if c.get("should_retrieve", True)]
    if args.ids.strip():
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        cases = [c for c in cases if c.get("id") in want]
        missing = want - {c.get("id") for c in cases}
        if missing:
            print(f"Warning: unknown ids: {sorted(missing)}", file=sys.stderr)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    print(f"Cases: {len(cases)} | model={args.model}")
    ingest_playbook(args.pdf)
    dataset, details = collect_dataset(cases)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = EVAL_DIR / f"results-ragas-{stamp}.md"

    if args.skip_ragas:
        write_report(report_path, {"skipped": True}, details, args.model, args.pdf)
        return 0

    print("\nRunning Ragas metrics (LLM-as-judge)…")
    result = run_ragas(dataset, args.model)
    print(result)
    write_report(report_path, result, details, args.model, args.pdf)

    # Also dump machine-readable summary
    summary_path = EVAL_DIR / f"results-ragas-{stamp}.json"
    try:
        scores = dict(result)
    except Exception:  # noqa: BLE001
        scores = {"raw": str(result)}
    summary_path.write_text(
        json.dumps({"scores": scores, "details": details}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
