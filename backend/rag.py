"""LlamaIndex PDF ingestion + hybrid (vector + BM25) retrieval.

This is the "retrieval" half of agentic RAG:

  Ingest:  PDF → load → chunk → embed → VectorStoreIndex (+ docstore for BM25)
  Query:   vector top-k  +  BM25 top-k  →  RRF fuse  →  best chunks

LangGraph still owns the agent loop; this module only returns passage text.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import Stemmer
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.retrievers.bm25 import BM25Retriever
from pypdf import PdfReader

# Project-local storage for uploaded PDFs
DATA_DIR = Path(__file__).resolve().parent / "data" / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Module-level index (rebuilt on each successful upload)
_index: VectorStoreIndex | None = None
_documents_meta: list[dict[str, Any]] = []

# PDF syntax / binary noise that sometimes leaks into extraction
_PDF_NOISE = re.compile(
    r"(endobj|endstream| co\s|Do\s|/Font|/Type|/Dest|/Parent|/Prev|/Next|"
    r"obj\s*<<|>>\s*stream|xref|startxref|%\s*PDF-)",
    re.IGNORECASE,
)

# Reciprocal Rank Fusion constant (standard default from the RRF paper)
_RRF_K = 60

# How many fused chunks reach grade + the LLM (2026 default band: 5–10).
# Hybrid still pulls a wider pool per engine, then fuses down to this.
DEFAULT_TOP_K = 8


def configure_models(
    model: str | None = None,
    embed_model: str | None = None,
) -> None:
    """Configure LlamaIndex global LLM + embedding models (OpenAI)."""
    import os

    chat = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
    emb = (
        embed_model
        or os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small").strip()
        or "text-embedding-3-small"
    )
    Settings.llm = OpenAI(model=chat, temperature=0)
    Settings.embed_model = OpenAIEmbedding(model=emb)
    Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=64)


def list_documents() -> list[dict[str, Any]]:
    return list(_documents_meta)


def has_index() -> bool:
    return _index is not None


def clear_index() -> None:
    """Remove all uploads and reset the in-memory index."""
    global _index, _documents_meta
    _index = None
    _documents_meta = []
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _clean_text(text: str) -> str:
    """Strip common PDF operator noise and collapse whitespace."""
    if not text:
        return ""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Drop lines dominated by PDF syntax
        if _PDF_NOISE.search(line) and sum(c.isalpha() for c in line) < 20:
            continue
        # Drop mostly non-printable / control-heavy lines
        printable = sum(1 for c in line if c.isprintable())
        if printable / max(len(line), 1) < 0.85:
            continue
        lines.append(line)
    cleaned = re.sub(r"[ \t]+", " ", "\n".join(lines))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _load_pdf_documents(file_path: Path, original_name: str) -> list[Document]:
    """Extract page text with pypdf (cleaner than raw PDF object dumps)."""
    reader = PdfReader(str(file_path))
    documents: list[Document] = []
    for i, page in enumerate(reader.pages):
        raw = page.extract_text() or ""
        text = _clean_text(raw)
        if not text:
            continue
        documents.append(
            Document(
                text=text,
                metadata={
                    "filename": original_name,
                    "page_label": str(i + 1),
                    "page": i + 1,
                    "file_name": original_name,
                },
            )
        )
    if not documents:
        raise ValueError(
            "No extractable text found in this PDF. "
            "Try a text-based PDF (not a scanned image-only file)."
        )
    return documents


def ingest_pdf(file_path: Path, original_name: str) -> dict[str, Any]:
    """Load a PDF, add it to the vector index, return metadata.

    Vector embeddings live in VectorStoreIndex.
    BM25 reuses the same nodes via index.docstore (built at query time).
    """
    global _index, _documents_meta

    configure_models()
    documents = _load_pdf_documents(file_path, original_name)

    if _index is None:
        _index = VectorStoreIndex.from_documents(documents)
    else:
        for doc in documents:
            _index.insert(doc)

    meta = {
        "filename": original_name,
        "pages": len(documents),
        "path": str(file_path),
    }
    _documents_meta = [m for m in _documents_meta if m["filename"] != original_name]
    _documents_meta.append(meta)
    return meta


def _reciprocal_rank_fusion(
    ranked_lists: list[tuple[str, list[NodeWithScore]]],
    top_k: int,
    k: int = _RRF_K,
) -> list[NodeWithScore]:
    """Merge ranked lists with Reciprocal Rank Fusion (RRF).

    score(chunk) += 1 / (k + rank)   for each list the chunk appears in

    Why ranks (not raw scores)? Vector cosine and BM25 numbers are different
    units — ranks let us fuse them without calibration.
    """
    rrf_scores: dict[str, float] = {}
    methods_hit: dict[str, set[str]] = {}
    best_node: dict[str, NodeWithScore] = {}

    for method, nodes in ranked_lists:
        for rank, node_with_score in enumerate(nodes):
            node = node_with_score.node
            node_id = node.node_id
            rrf_scores[node_id] = rrf_scores.get(node_id, 0.0) + 1.0 / (k + rank + 1)
            methods_hit.setdefault(node_id, set()).add(method)
            # Keep a node object; prefer higher original score when tying identity
            prev = best_node.get(node_id)
            if prev is None or (node_with_score.score or 0) >= (prev.score or 0):
                best_node[node_id] = node_with_score

    ordered = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    fused: list[NodeWithScore] = []
    for node_id, rrf in ordered:
        base = best_node[node_id]
        # Attach fusion score + which engines hit (for UI / learning)
        meta = dict(base.node.metadata or {})
        meta["retrieval_methods"] = "+".join(sorted(methods_hit[node_id]))
        meta["rrf_score"] = round(rrf, 6)
        base.node.metadata = meta
        fused.append(NodeWithScore(node=base.node, score=rrf))
    return fused


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    """Hybrid search: vector (semantic) + BM25 (keyword), fused with RRF.

    Returns joined text for the LangGraph retrieve_documents tool
    (grade + answer both consume this string — typically 5–10 chunks).
    """
    if _index is None:
        return (
            "No documents have been uploaded yet. "
            "Ask the user to upload a PDF first."
        )

    # Pull a wider pool from each engine, then fuse down to top_k for the LLM.
    # (Same idea as LlamaIndex Hybrid BM25 + vector docs, with explicit RRF
    # so we can label via=vector / bm25 / vector+bm25 for learning.)
    pool_k = max(top_k, min(top_k * 2, 20))

    # --- Path A: dense / semantic (embeddings in VectorStoreIndex) ---
    vector_retriever = _index.as_retriever(similarity_top_k=pool_k)
    vector_nodes = vector_retriever.retrieve(query)

    # --- Path B: sparse / keyword (BM25 — LlamaIndex package, not LangGraph) ---
    # Official pattern: BM25Retriever.from_defaults(docstore=index.docstore)
    # Stemmer + language match the LlamaIndex BM25 notebook (english defaults).
    bm25_retriever = BM25Retriever.from_defaults(
        docstore=_index.docstore,
        similarity_top_k=pool_k,
        stemmer=Stemmer.Stemmer("english"),
        language="english",
    )
    bm25_nodes = bm25_retriever.retrieve(query)

    # --- Fuse ranks (not raw scores). Docs often use QueryFusionRetriever;
    # we keep explicit RRF so chunk headers can show which engine(s) hit. ---
    nodes = _reciprocal_rank_fusion(
        [
            ("vector", vector_nodes),
            ("bm25", bm25_nodes),
        ],
        top_k=top_k,
    )

    if not nodes:
        return "No relevant passages found in the uploaded documents."

    parts: list[str] = []
    for i, node in enumerate(nodes, start=1):
        source = node.metadata.get("filename") or node.metadata.get("file_name") or "document"
        page = node.metadata.get("page_label") or node.metadata.get("page") or "?"
        methods = node.metadata.get("retrieval_methods", "hybrid")
        score = f"{node.score:.4f}" if node.score is not None else "n/a"
        content = _clean_text(node.get_content())
        if not content:
            continue
        # Keep tool payload readable in the chat UI
        if len(content) > 800:
            content = content[:800].rstrip() + "…"
        # Human-readable passage card (model should cite Document + Page, never "Chunk N")
        parts.append(
            f"### Passage {i}\n"
            f"- Document: {source}\n"
            f"- Page: {page}\n"
            f"- Match: {methods} (score {score})\n"
            f"\n{content}"
        )

    if not parts:
        return "No readable passages found after cleaning PDF text."
    return "\n\n".join(parts)
