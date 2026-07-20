"""LlamaIndex document ingestion + hybrid (vector + BM25) + cross-encoder rerank.

This is the "retrieval" half of agentic RAG:

  Ingest:  file → load → type-aware chunk → [optional: contextualize] → embed → VectorStoreIndex
  Query:   vector + BM25 → RRF fuse (wide) → cross-encoder rerank → top-k

Contextual Retrieval (RAG_CONTEXTUAL=1):
  At ingest we use a cheap LLM to write a short "situating context" for every chunk
  based on the whole document. We then embed + BM25 the *augmented* text
  (Contextual Embeddings + Contextual BM25). The clean original chunk is what
  we send to the final LLM.

LangGraph still owns the agent loop; this module only returns passage text.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import Stemmer
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.retrievers.bm25 import BM25Retriever
from pypdf import PdfReader

# For Contextual Retrieval (learning implementation)
from functools import lru_cache
from openai import OpenAI as RawOpenAIClient  # raw client for learning prompt caching behavior

# Project-local storage for uploaded documents
DATA_DIR = Path(__file__).resolve().parent / "data" / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".md", ".markdown"})
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

# Module-level index (rebuilt on each successful upload)
_index: VectorStoreIndex | None = None
_documents_meta: list[dict[str, Any]] = []
# Lazy-loaded cross-encoder (heavy; first retrieve may download weights)
_reranker: Any = None
_reranker_key: str | None = None

# PDF syntax / binary noise that sometimes leaks into extraction
_PDF_NOISE = re.compile(
    r"(endobj|endstream| co\s|Do\s|/Font|/Type|/Dest|/Parent|/Prev|/Next|"
    r"obj\s*<<|>>\s*stream|xref|startxref|%\s*PDF-)",
    re.IGNORECASE,
)

# Reciprocal Rank Fusion constant (standard default from the RRF paper)
_RRF_K = 60

# How many chunks reach grade + the LLM after rerank (2026 default band: 5–10).
DEFAULT_TOP_K = 8

# RRF keeps a wider shortlist; cross-encoder reorders then cuts to DEFAULT_TOP_K.
DEFAULT_RERANK_CANDIDATES = 20

# Soft cap when packaging each passage into the tool string (characters, not tokens).
# See docs/learning/05-ship-eval-polish.md Ch. 17 — was 800 and cut the Live/Approved NOTE on page 6.
MAX_PASSAGE_CHARS = 2000

# Default MS MARCO cross-encoder — standard for passage reranking (not STS).
DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Contextual Retrieval (Anthropic "Contextual Embeddings" + Contextual BM25)
# One-time ingest augmentation: prepend a short "situating" context to each chunk
# so both the embedding and the BM25 index see document-level context.
# Toggle with RAG_CONTEXTUAL=1
# ---------------------------------------------------------------------------

def contextual_enabled() -> bool:
    """Enable Contextual Retrieval (generate situating context per chunk at ingest)."""
    return _env_flag("RAG_CONTEXTUAL", default=False)


# ---------------------------------------------------------------------------
# PROMPT CACHING EXPLANATION (for learning Contextual Retrieval)
# ---------------------------------------------------------------------------
#
# What is Prompt Caching?
#
# When you call an LLM, you pay for every token in the prompt.
# In Contextual Retrieval, the "prompt" for each chunk looks like this:
#
#   [VERY LONG] full document (8k-20k tokens)
#   + short instruction
#   + the current chunk
#
# If you do this naively for 100 chunks of the same document, you re-send
# the full document 100 times → you pay for the document ~100x.
#
# Prompt caching solves exactly this:
# - First call for a document: "Write this big prefix into cache" (you pay full price).
# - Next calls for other chunks of the *same* document:
#     The provider sees "I already have this exact prefix cached"
#     → it charges you only ~10% (or less) for the cached part.
#
# This is why the article says Contextual Retrieval becomes cheap *only* with caching.
#
# Anthropic (what the article uses):
#   - Explicit control with cache_control on the document part.
#   - You get back in usage:
#       cache_creation_input_tokens   (first time, expensive)
#       cache_read_input_tokens       (later, 90% discount)
#
# OpenAI (what we use here):
#   - Automatic prefix caching on long, stable prefixes (for gpt-4o family etc.).
#   - In the usage object you can sometimes see prompt_tokens_details.cached_tokens.
#   - Not as explicit as Anthropic, but the idea is the same:
#     Make the long document appear as a stable prefix at the beginning of the conversation.
#
# Critical rule for cache hits:
#   You must process chunks of the SAME document one after another
#   (with the exact same document text as the prefix).
#   Our _create_contextual_documents already does this per PDF → good.
# ---------------------------------------------------------------------------


def _situate_context(full_document: str, chunk: str, doc_name: str = "") -> tuple[str, dict]:
    """
    Generate situating context for one chunk.

    Returns: (context_text, usage_info)

    We deliberately use the RAW OpenAI client (not the LangChain wrapper) for this step.
    Why? Because prompt caching is all about message structure and prefix stability.
    The wrapper hides the details we want to learn.

    Key technique for caching:
      - The LONG document is sent as the FIRST message (stable prefix).
      - The small per-chunk instruction comes after.
      - When processing many chunks of the *same* document in sequence,
        the LLM provider can recognize the repeated prefix and cache it.
    """
    import os

    model_name = (
        os.getenv("OPENAI_CONTEXTUAL_MODEL")
        or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    ).strip() or "gpt-5.4-mini"

    client = RawOpenAIClient()

    # Structure optimized for prefix caching:
    # Message 0 = the big, repeating document (this is what gets cached)
    # Message 1 = the small varying part (chunk + instruction)
    messages = [
        {
            "role": "user",
            "content": f"<document>\n{full_document[:12000]}\n</document>",
        },
        {
            "role": "user",
            "content": (
                "Here is the chunk we want to situate within the whole document\n"
                f"<chunk>\n{chunk}\n</chunk>\n\n"
                "Please give a short succinct context to situate this chunk within the overall document "
                "for the purposes of improving search retrieval of the chunk. "
                "Answer only with the succinct context and nothing else."
            ),
        },
    ]

    try:
        # Support both old models (max_tokens) and new models like gpt-5.4-mini / o-series (max_completion_tokens)
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.0,
                max_completion_tokens=300,
            )
        except Exception as param_err:
            if "max_completion_tokens" in str(param_err).lower() or "max_tokens" in str(param_err).lower():
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=300,
                )
            else:
                raise

        context_text = (response.choices[0].message.content or "").strip()

        usage = response.usage or {}
        usage_info = {
            "model": model_name,
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
            "cache_hit": "unknown",
        }

        # Try to detect OpenAI cached tokens (available on some models/responses)
        try:
            details = getattr(usage, "prompt_tokens_details", None)
            if details and getattr(details, "cached_tokens", 0):
                usage_info["cached_tokens"] = details.cached_tokens
                usage_info["cache_hit"] = True
            elif "cached" in str(usage).lower():
                usage_info["cache_hit"] = "possible"
        except Exception:
            pass

        return context_text, usage_info

    except Exception as exc:
        print(f"[contextual] Call failed for a chunk in {doc_name}: {exc}")
        # Graceful fallback so the whole ingest doesn't die while learning
        fallback = f"Part of document about {doc_name or 'the uploaded file'}."
        return fallback, {"error": str(exc), "input_tokens": 0, "output_tokens": 0}


def rerank_enabled() -> bool:
    """Tier-2 cross-encoder on by default; set RAG_RERANK=0 to skip."""
    return _env_flag("RAG_RERANK", default=True)


def rerank_model_name() -> str:
    return (
        os.getenv("RERANK_MODEL", DEFAULT_RERANK_MODEL).strip()
        or DEFAULT_RERANK_MODEL
    )


def rerank_candidates(top_k: int = DEFAULT_TOP_K) -> int:
    """How many RRF hits feed the cross-encoder (always ≥ top_k)."""
    raw = os.getenv("RERANK_CANDIDATES", "").strip()
    if raw.isdigit():
        n = int(raw)
    else:
        n = DEFAULT_RERANK_CANDIDATES
    return max(top_k, n)


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
    Settings.node_parser = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )


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


def _load_markdown_documents(file_path: Path, original_name: str) -> list[Document]:
    """Load UTF-8 Markdown without destroying its heading structure."""
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Markdown files must be UTF-8 encoded.") from exc

    if not text.strip():
        raise ValueError("No text found in this Markdown file.")

    return [
        Document(
            text=text,
            metadata={
                "filename": original_name,
                "file_name": original_name,
                "file_type": "markdown",
            },
        )
    ]


def _load_source_documents(file_path: Path, original_name: str) -> list[Document]:
    """Load a supported file into source documents before chunking."""
    extension = Path(original_name).suffix.lower()
    if extension == ".pdf":
        return _load_pdf_documents(file_path, original_name)
    if extension in {".md", ".markdown"}:
        return _load_markdown_documents(file_path, original_name)
    raise ValueError(f"Unsupported document type: {extension or 'no extension'}")


def _markdown_section(node: Any) -> str:
    """Build a human-readable heading path for a Markdown section node."""
    text = node.get_content()
    heading = next(
        (
            line.lstrip("#").strip()
            for line in text.splitlines()
            if line.startswith("#") and line.lstrip("#").startswith(" ")
        ),
        "",
    )
    parent = str(node.metadata.get("header_path", "")).strip("/")
    return " / ".join(part for part in (parent, heading) if part) or "Document"


def _parse_documents(
    documents: list[Document],
    original_name: str,
) -> list[Any]:
    """Route each file type to a structure-aware parser and enforce a size cap."""
    extension = Path(original_name).suffix.lower()
    size_splitter = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    if extension == ".pdf":
        return size_splitter.get_nodes_from_documents(documents)

    if extension in {".md", ".markdown"}:
        section_nodes = MarkdownNodeParser().get_nodes_from_documents(documents)
        for node in section_nodes:
            node.metadata["section"] = _markdown_section(node)
        return size_splitter.get_nodes_from_documents(section_nodes)

    raise ValueError(f"Unsupported document type: {extension or 'no extension'}")


def _create_contextual_documents(
    source_documents: list[Document],
    nodes: list[Any],
    original_name: str,
) -> list[Document]:
    """Contextual Retrieval step.

    1. Build a full-document view (with page markers when available).
    2. Use the chunks already produced by the file-type parser.
    3. For each chunk, ask the LLM for a short situating context.
    4. Return Documents whose .text = context + "\n\n" + original chunk
       (this text is what gets embedded + indexed for BM25 — the key for better retrieval).
    We only put small fields + the short "context" into metadata.
    The clean original chunk is recovered at query time (see _get_display_content).
    """
    if not source_documents:
        return []

    parts = []
    for document in source_documents:
        page = document.metadata.get("page_label") or document.metadata.get("page")
        marker = f"\n\n--- PAGE {page} ---\n\n" if page else "\n\n"
        parts.append(f"{marker}{document.text}")
    full_doc = "".join(parts).strip()

    contextual_docs: list[Document] = []
    print(f"[contextual] Generating situating context for {len(nodes)} chunks from {original_name}...")

    # Token accounting for learning prompt caching
    total_input = 0
    total_output = 0
    total_cached = 0
    calls = 0

    for node in nodes:
        raw_chunk = node.get_content()
        if not raw_chunk.strip():
            continue

        # Note: we pass original_name for better fallback messages
        ctx, usage = _situate_context(full_doc, raw_chunk, doc_name=original_name)

        calls += 1
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)
        if usage.get("cached_tokens"):
            total_cached += usage["cached_tokens"]

        # The text we actually embed and put in the BM25 docstore
        augmented = f"{ctx}\n\n{raw_chunk}" if ctx else raw_chunk

        meta = {
            **node.metadata,
            "filename": original_name,
            "context": ctx,
            # NOTE: We intentionally do NOT put the full original_content here.
            # LlamaIndex enforces that serialized metadata length <= chunk_size (512 by default).
            # Storing the whole chunk easily exceeds it (causing the error you saw:
            # "Metadata length (522) is longer than chunk size (512)").
            # We recover the clean original at query time by stripping the context prefix.
            # Try to carry page info (best-effort from surrounding markers or node)
            "page_label": node.metadata.get("page_label"),
            "page": node.metadata.get("page"),
        }
        # Fallback: try to guess page from the chunk text if the splitter preserved markers
        if not meta.get("page_label"):
            # very rough heuristic
            for line in raw_chunk.splitlines()[:3]:
                if "PAGE " in line:
                    try:
                        meta["page_label"] = line.split("PAGE ")[-1].strip().split()[0]
                    except Exception:
                        pass
                    break

        contextual_docs.append(Document(text=augmented, metadata=meta))

    # Beautiful educational logging (inspired by the Anthropic cookbook)
    print("\n[contextual] === Prompt Caching / Token Report ===")
    print(f"  Chunks processed: {calls}")
    print(f"  Total input tokens sent:  {total_input}")
    print(f"  Total output tokens:      {total_output}")
    if total_cached > 0:
        print(f"  Cached tokens (read from cache): {total_cached}")
        savings = (total_cached / max(total_input, 1)) * 100
        print(f"  Apparent cache savings: ~{savings:.1f}% of input tokens were served from cache")
        print("  (Lower effective cost thanks to prefix caching)")
    else:
        print("  No explicit cached_tokens reported by the provider on this run.")
        print("  → This is typical with current OpenAI setup unless using a model + prefix that triggers caching.")
        print("  Compare to Anthropic: they would show cache_creation vs cache_read here.")
    print("[contextual] =======================================\n")

    return contextual_docs


def ingest_document(file_path: Path, original_name: str) -> dict[str, Any]:
    """Load a supported document, add it to the vector index, return metadata.

    When RAG_CONTEXTUAL=1:
      - We run Contextual Retrieval: generate short situating context for each chunk
        using the full document, then embed + BM25 the *augmented* text.
      - This improves retrieval for both dense and sparse paths (the core idea
        from Anthropic's Contextual Embeddings + Contextual BM25).

    The augmented text goes into the indexed nodes (for search).
    Clean original text is recovered at display time by stripping the context prefix.
    """
    global _index, _documents_meta

    configure_models()
    source_docs = _load_source_documents(file_path, original_name)
    nodes = _parse_documents(source_docs, original_name)

    if contextual_enabled():
        nodes_to_index = _create_contextual_documents(
            source_docs,
            nodes,
            original_name,
        )
        print(f"[contextual] Using contextualized chunks for indexing (RAG_CONTEXTUAL=1)")
    else:
        nodes_to_index = nodes

    if _index is None:
        _index = VectorStoreIndex(nodes_to_index)
    else:
        _index.insert_nodes(nodes_to_index)

    extension = Path(original_name).suffix.lower()
    sections = {
        node.metadata["section"]
        for node in nodes
        if node.metadata.get("section")
    }
    meta = {
        "filename": original_name,
        "file_type": "pdf" if extension == ".pdf" else "markdown",
        "pages": len(source_docs) if extension == ".pdf" else None,
        "sections": len(sections) if sections else None,
        "chunks": len(nodes),
        "path": str(file_path),
        "contextual": contextual_enabled(),
    }
    _documents_meta = [m for m in _documents_meta if m["filename"] != original_name]
    _documents_meta.append(meta)
    return meta


def ingest_pdf(file_path: Path, original_name: str) -> dict[str, Any]:
    """Backward-compatible PDF entry point used by the eval scripts."""
    return ingest_document(file_path, original_name)


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


def _get_cross_encoder_reranker(top_n: int) -> Any:
    """Lazy-load SentenceTransformerRerank (cross-encoder). Cached per model."""
    global _reranker, _reranker_key
    model = rerank_model_name()
    key = f"{model}::{top_n}"
    if _reranker is not None and _reranker_key == key:
        return _reranker

    from llama_index.core.postprocessor import SentenceTransformerRerank

    # keep_retrieval_score stores prior RRF on node.metadata["retrieval_score"]
    _reranker = SentenceTransformerRerank(
        top_n=top_n,
        model=model,
        keep_retrieval_score=True,
    )
    _reranker_key = key
    return _reranker


def _cross_encoder_rerank(
    query: str,
    nodes: list[NodeWithScore],
    top_n: int,
) -> tuple[list[NodeWithScore], dict[str, Any]]:
    """Reorder hybrid shortlist with a cross-encoder; return (nodes, meta)."""
    if not nodes:
        return [], {"enabled": True, "applied": False, "reason": "empty input"}

    try:
        reranker = _get_cross_encoder_reranker(top_n=top_n)
    except ImportError as exc:
        return nodes[:top_n], {
            "enabled": True,
            "applied": False,
            "reason": f"import failed: {exc} (pip install torch sentence-transformers)",
            "model": rerank_model_name(),
        }
    except Exception as exc:  # noqa: BLE001
        return nodes[:top_n], {
            "enabled": True,
            "applied": False,
            "reason": f"init failed: {exc}",
            "model": rerank_model_name(),
        }

    model = rerank_model_name()
    try:
        reranked = reranker.postprocess_nodes(nodes, query_str=query)
    except Exception as exc:  # noqa: BLE001
        return nodes[:top_n], {
            "enabled": True,
            "applied": False,
            "reason": f"rerank failed: {exc}",
            "model": model,
            "n_in": len(nodes),
        }

    # Tag methods for packaging / learning
    for nws in reranked:
        meta = dict(nws.node.metadata or {})
        prior = meta.get("retrieval_methods", "hybrid")
        if "rerank" not in str(prior):
            meta["retrieval_methods"] = f"{prior}+rerank"
        meta["rerank_model"] = model
        if nws.score is not None:
            meta["rerank_score"] = round(float(nws.score), 6)
        nws.node.metadata = meta

    return list(reranked), {
        "enabled": True,
        "applied": True,
        "model": model,
        "n_in": len(nodes),
        "n_out": len(reranked),
        "top_n": top_n,
    }


def _get_display_content(node: Any) -> str:
    """Return clean original chunk text for display / the agent.

    When using Contextual Retrieval:
      - The indexed node.text = situating_context + "\n\n" + original_chunk
      - We store only the short "context" in metadata (to keep metadata size << chunk_size)
      - Here we strip the prefix so the LLM and UI see only the real content.

    This avoids the LlamaIndex error:
      "Metadata length (522) is longer than chunk size (512)"
    """
    if node is None:
        return ""
    text = node.get_content() if hasattr(node, "get_content") else str(node)
    meta = getattr(node, "metadata", {}) or {}
    ctx = meta.get("context")
    if ctx and isinstance(ctx, str) and text.startswith(ctx):
        # strip context + any leading whitespace/newlines
        remainder = text[len(ctx):]
        return remainder.lstrip("\n\r\t ")
    return text


def _node_location(node: Any) -> tuple[str, str]:
    """Return the citation field and value appropriate for this node."""
    page = node.metadata.get("page_label") or node.metadata.get("page")
    if page:
        return "Page", str(page)
    section = node.metadata.get("section")
    if section:
        return "Section", str(section)
    return "Section", "Document"


def _hit_summary(node_with_score: NodeWithScore, rank: int) -> dict[str, Any]:
    """Compact one-line hit for traces (page, score, short preview).

    When the index was built with contextual retrieval, we show preview of
    the *original* content (the context prefix is only for better retrieval).
    """
    node = node_with_score.node
    display_text = _get_display_content(node)
    text = _clean_text(display_text)
    location_type, location = _node_location(node)
    score = node_with_score.score
    return {
        "rank": rank,
        "page": location if location_type == "Page" else "?",
        "section": location if location_type == "Section" else None,
        "score": round(float(score), 6) if score is not None else None,
        "node_id": node.node_id[:12],
        "chars": len(text),
        "preview": (text[:120] + "…") if len(text) > 120 else text,
        "has_context": bool(node.metadata.get("context")),
    }


def retrieve_trace(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    *,
    max_passage_chars: int = MAX_PASSAGE_CHARS,
    needles: list[str] | None = None,
    use_rerank: bool | None = None,
) -> dict[str, Any]:
    """Run hybrid (+ optional cross-encoder) retrieve with a step-by-step trace.

    Steps mirror the pipeline:

      query → vector → BM25 → RRF (wide) → [cross-encoder rerank] → package → tool string

    Use ``retrieve()`` for the agent; use this (or ``eval/trace_rag.py``) to inspect.
    """
    steps: list[dict[str, Any]] = []
    needles = needles or []
    do_rerank = rerank_enabled() if use_rerank is None else use_rerank
    candidates_k = rerank_candidates(top_k) if do_rerank else top_k

    # --- Step 0: index ---
    if _index is None:
        msg = (
            "No documents have been uploaded yet. "
            "Ask the user to upload a PDF or Markdown file first."
        )
        steps.append({"step": "index", "ok": False, "detail": "no index in memory"})
        steps.append({"step": "return", "tool_string_chars": len(msg), "ok": False})
        return {
            "query": query,
            "top_k": top_k,
            "max_passage_chars": max_passage_chars,
            "rerank": do_rerank,
            "ok": False,
            "tool_string": msg,
            "steps": steps,
        }

    n_nodes = len(_index.docstore.docs) if _index.docstore else 0
    steps.append(
        {
            "step": "index",
            "ok": True,
            "n_nodes": n_nodes,
            "docs_meta": list(_documents_meta),
        }
    )

    # Pull a wider engine pool when reranking so RRF has room to feed the CE.
    pool_k = max(candidates_k, min(max(candidates_k, top_k) * 2, 32))
    steps.append(
        {
            "step": "params",
            "top_k": top_k,
            "pool_k": pool_k,
            "rrf_k": _RRF_K,
            "candidates_k": candidates_k,
            "rerank": do_rerank,
            "rerank_model": rerank_model_name() if do_rerank else None,
            "max_passage_chars": max_passage_chars,
        }
    )

    # --- Path A: dense / semantic ---
    vector_retriever = _index.as_retriever(similarity_top_k=pool_k)
    vector_nodes = vector_retriever.retrieve(query)
    steps.append(
        {
            "step": "vector",
            "engine": "VectorStoreIndex.as_retriever",
            "requested": pool_k,
            "n_hits": len(vector_nodes),
            "hits": [
                _hit_summary(n, i) for i, n in enumerate(vector_nodes, start=1)
            ],
        }
    )

    # --- Path B: sparse / keyword (BM25) ---
    bm25_retriever = BM25Retriever.from_defaults(
        docstore=_index.docstore,
        similarity_top_k=pool_k,
        stemmer=Stemmer.Stemmer("english"),
        language="english",
    )
    bm25_nodes = bm25_retriever.retrieve(query)
    steps.append(
        {
            "step": "bm25",
            "engine": "BM25Retriever + english stemmer",
            "requested": pool_k,
            "n_hits": len(bm25_nodes),
            "hits": [_hit_summary(n, i) for i, n in enumerate(bm25_nodes, start=1)],
        }
    )

    # --- Fuse ranks (wide shortlist when rerank is on) ---
    fused = _reciprocal_rank_fusion(
        [
            ("vector", vector_nodes),
            ("bm25", bm25_nodes),
        ],
        top_k=candidates_k,
    )
    steps.append(
        {
            "step": "rrf_fuse",
            "formula": "score += 1/(rrf_k + rank)",
            "rrf_k": _RRF_K,
            "n_fused": len(fused),
            "candidates_k": candidates_k,
            "hits": [
                {
                    **_hit_summary(n, i),
                    "methods": n.metadata.get("retrieval_methods"),
                    "rrf_score": n.metadata.get("rrf_score"),
                }
                for i, n in enumerate(fused, start=1)
            ],
        }
    )

    if not fused:
        msg = "No relevant passages found in the uploaded documents."
        steps.append({"step": "package", "n_passages": 0, "detail": "empty fuse"})
        steps.append({"step": "return", "tool_string_chars": len(msg), "ok": False})
        return {
            "query": query,
            "top_k": top_k,
            "max_passage_chars": max_passage_chars,
            "rerank": do_rerank,
            "ok": False,
            "tool_string": msg,
            "steps": steps,
        }

    # --- Tier-2: cross-encoder rerank → top_k for the LLM ---
    if do_rerank:
        nodes, rerank_meta = _cross_encoder_rerank(query, fused, top_n=top_k)
        steps.append(
            {
                "step": "rerank",
                "kind": "cross-encoder",
                **rerank_meta,
                "hits": [
                    {
                        **_hit_summary(n, i),
                        "methods": n.metadata.get("retrieval_methods"),
                        "rrf_score": n.metadata.get("rrf_score")
                        or n.metadata.get("retrieval_score"),
                        "rerank_score": n.metadata.get("rerank_score", n.score),
                    }
                    for i, n in enumerate(nodes, start=1)
                ],
            }
        )
    else:
        nodes = fused[:top_k]
        steps.append(
            {
                "step": "rerank",
                "kind": "cross-encoder",
                "enabled": False,
                "applied": False,
                "reason": "RAG_RERANK disabled",
                "n_in": len(fused),
                "n_out": len(nodes),
                "hits": [
                    {
                        **_hit_summary(n, i),
                        "methods": n.metadata.get("retrieval_methods"),
                        "rrf_score": n.metadata.get("rrf_score"),
                    }
                    for i, n in enumerate(nodes, start=1)
                ],
            }
        )

    # --- Package: clean + char cap → passage cards ---
    parts: list[str] = []
    packaged: list[dict[str, Any]] = []
    for i, node_ws in enumerate(nodes, start=1):
        node = node_ws.node
        source = (
            node.metadata.get("filename")
            or node.metadata.get("file_name")
            or "document"
        )
        location_type, location = _node_location(node)
        page = location if location_type == "Page" else "?"
        section = location if location_type == "Section" else None
        methods = node.metadata.get("retrieval_methods", "hybrid")
        score = f"{node_ws.score:.4f}" if node_ws.score is not None else "n/a"

        # IMPORTANT for Contextual Retrieval:
        # The node text may contain the synthetic context prefix.
        # We send the *original* clean content to the agent/LLM.
        # The context only helped the retriever (vector + BM25) find it.
        display_source = _get_display_content(node)
        raw = _clean_text(display_source)

        if not raw:
            packaged.append(
                {
                    "passage": i,
                    "page": page,
                    "skipped": True,
                    "reason": "empty after clean",
                }
            )
            continue

        raw_chars = len(raw)
        truncated = raw_chars > max_passage_chars
        content = (
            raw[:max_passage_chars].rstrip() + "…" if truncated else raw
        )
        needle_hits = {
            n: (n.lower() in content.lower()) for n in needles
        } if needles else {}
        needle_in_raw = {
            n: (n.lower() in raw.lower()) for n in needles
        } if needles else {}
        # Gold lost to packaging: in raw node but not after cap
        packaging_loss = {
            n: (needle_in_raw.get(n) and not needle_hits.get(n))
            for n in needles
        } if needles else {}

        is_contextual = bool(node.metadata.get("context"))
        match_line = f"- Match: {methods} (score {score})"
        if is_contextual:
            match_line += " [contextual]"

        card = (
            f"### Passage {i}\n"
            f"- Document: {source}\n"
            f"- {location_type}: {location}\n"
            f"{match_line}\n"
            f"\n{content}"
        )
        parts.append(card)
        packaged.append(
            {
                "passage": i,
                "page": page,
                "section": section,
                "document": source,
                "methods": methods,
                "rrf_score": node.metadata.get("rrf_score")
                or node.metadata.get("retrieval_score"),
                "rerank_score": node.metadata.get("rerank_score", node_ws.score),
                "score": node_ws.score,
                "raw_chars": raw_chars,
                "capped_chars": len(content),
                "max_passage_chars": max_passage_chars,
                "truncated": truncated,
                "chars_cut": max(0, raw_chars - max_passage_chars) if truncated else 0,
                "head_preview": content[:100] + ("…" if len(content) > 100 else ""),
                "tail_preview": content[-100:] if len(content) > 100 else content,
                "needle_in_raw": needle_in_raw,
                "needle_in_packaged": needle_hits,
                "packaging_loss": packaging_loss,
                "contextual": is_contextual,
                "retrieval_context": node.metadata.get("context") if is_contextual else None,
            }
        )

    steps.append(
        {
            "step": "package",
            "max_passage_chars": max_passage_chars,
            "n_passages": len(parts),
            "n_truncated": sum(1 for p in packaged if p.get("truncated")),
            "passages": packaged,
        }
    )

    if not parts:
        msg = "No readable passages found after cleaning document text."
        steps.append({"step": "return", "tool_string_chars": len(msg), "ok": False})
        return {
            "query": query,
            "top_k": top_k,
            "max_passage_chars": max_passage_chars,
            "rerank": do_rerank,
            "ok": False,
            "tool_string": msg,
            "steps": steps,
        }

    tool_string = "\n\n".join(parts)
    tool_needles = {
        n: (n.lower() in tool_string.lower()) for n in needles
    } if needles else {}
    steps.append(
        {
            "step": "return",
            "ok": True,
            "tool_string_chars": len(tool_string),
            "n_passages": len(parts),
            "needle_in_tool_string": tool_needles,
        }
    )

    return {
        "query": query,
        "top_k": top_k,
        "max_passage_chars": max_passage_chars,
        "rerank": do_rerank,
        "ok": True,
        "tool_string": tool_string,
        "steps": steps,
    }


def _trace_enabled() -> bool:
    return os.getenv("RAG_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}


def _emit_trace_ascii(trace: dict[str, Any]) -> None:
    """Print a teaching-style ASCII summary to the backend console (RAG_TRACE=1).

    Full interactive dump: ``python eval/trace_rag.py --ids q06``.
    """
    q = (trace.get("query") or "").replace("\n", " ")
    if len(q) > 56:
        q = q[:55] + "…"
    cap = trace.get("max_passage_chars")
    steps = {s.get("step"): s for s in (trace.get("steps") or [])}
    package = steps.get("package") or {}
    ret = steps.get("return") or {}
    rrf = steps.get("rrf_fuse") or {}
    rerank = steps.get("rerank") or {}
    n_trunc = package.get("n_truncated") or 0
    n_pass = package.get("n_passages") or ret.get("n_passages") or 0
    rerank_on = rerank.get("applied") or (
        rerank.get("enabled") and not rerank.get("reason")
    )

    # Detect if this retrieval is benefiting from Contextual Retrieval
    pkg_passages = package.get("passages") or []
    any_contextual = any(p.get("contextual") for p in pkg_passages)
    ctx_label = " + contextual" if any_contextual else ""

    lines = [
        "",
        "═" * 64,
        f" RAG_TRACE — hybrid + rerank{ctx_label}",
        "═" * 64,
        f"  query: “{q}”",
        "",
        "  ┌───────┐   ┌────────┐   ┌─────┐   ┌────────┐   ┌─────────┐   ┌────────┐",
        "  │ INDEX │──►│ VECTOR │──►│ RRF │──►│ RERANK │──►│ PACKAGE │──►│ RETURN │",
        "  └───────┘   │ + BM25 │   │fuse │   │  CE    │   │ char cap│   │  tool  │",
        "              └────────┘   └─────┘   └────────┘   └─────────┘   └────────┘",
        f"  fused={rrf.get('n_fused')}  rerank_out={rerank.get('n_out', n_pass)}  "
        f"packaged={n_pass}  truncated={n_trunc}  cap={cap} chars",
    ]
    if any_contextual:
        lines.append("  [contextual retrieval] context prefix used only for ranking (clean original sent to LLM)")
    if rerank:
        if rerank.get("applied"):
            lines.append(
                f"  CE model={rerank.get('model')}  "
                f"in={rerank.get('n_in')} → out={rerank.get('n_out')}"
            )
            for h in (rerank.get("hits") or [])[:5]:
                lines.append(
                    f"  · CE #{h.get('rank')} p.{h.get('page')} "
                    f"score={h.get('rerank_score')}"
                )
        else:
            lines.append(
                f"  CE skipped: {rerank.get('reason') or 'off'} "
                f"(rerank_on={bool(rerank_on)})"
            )
    for p in package.get("passages") or []:
        if p.get("skipped"):
            continue
        lost = any((p.get("packaging_loss") or {}).values())
        flag = "LOST" if lost else ("CUT" if p.get("truncated") else "ok")
        lines.append(
            f"  · pass #{p.get('passage')} p.{p.get('page')} "
            f"raw={p.get('raw_chars')} → {p.get('capped_chars')}  [{flag}]"
        )
        if lost:
            lines.append(
                f"      ⚠ packaging dropped needles: {p.get('packaging_loss')}"
            )
    needles = ret.get("needle_in_tool_string") or {}
    if needles:
        lines.append("  final tool string needles:")
        for k, v in needles.items():
            lines.append(f"    {'✓' if v else '✗'}  {k}")
    lines.append(
        f"  tool_string_chars={ret.get('tool_string_chars')}  "
        f"ok={ret.get('ok')}"
    )
    lines.append("═" * 64)
    lines.append("")
    print("\n".join(lines), flush=True)


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    """Hybrid search + optional cross-encoder rerank.

    Pipeline: vector + BM25 → RRF (wide) → CE rerank → top_k → package.

    Returns joined text for the LangGraph retrieve_documents tool
    (grade + answer both consume this string — typically 5–10 chunks).

    Env:
      RAG_RERANK=0|1     cross-encoder on (default 1)
      RERANK_MODEL=…     default cross-encoder/ms-marco-MiniLM-L-6-v2
      RERANK_CANDIDATES= how many RRF hits feed CE (default 20)
      RAG_TRACE=1        compact ASCII log on each retrieve (uvicorn)

      RAG_CONTEXTUAL=1   enable Contextual Retrieval at ingest time
                         (short situating context prepended before embed + BM25)
                         See _create_contextual_documents + _situate_context.

    Full dump: ``python eval/trace_rag.py --ids q06``
    """
    trace = retrieve_trace(query, top_k=top_k)
    if _trace_enabled():
        _emit_trace_ascii(trace)
    return trace["tool_string"]
