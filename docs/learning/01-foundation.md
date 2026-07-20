# Foundation — build the app & see the system

> Part of the [learning hub](./README.md).  
> Build agentic RAG, information flow, LlamaIndex role, memory vs DB, learning report.

**Chapters:** Ch. 1, Ch. 2, Ch. 3, Ch. 4, Ch. 5

---

## Chapter 1 — Build the learning app

### Q: Build a simple agentic RAG to learn how it works

**Ask:** Use LangGraph, LlamaIndex, simple PDF upload → retrieve → answer; install Astryx and init agent docs.

**What we built**

| Layer | Role |
|-------|------|
| Next.js + Astryx | Upload PDF, chat, show tool calls |
| FastAPI | `/api/upload`, `/api/chat`, `/api/chat/stream` |
| LlamaIndex | Chunk, embed, in-memory vector index, retrieve |
| LangGraph | Decide → retrieve → grade → rewrite → answer |
| pypdf | Extract text from PDF (before LlamaIndex indexes) |

**Later polish**

- Astryx template: `npx astryx template ai-chat ./src/app/ai-chat`
- Live UX: SSE streaming so the UI is not stuck while the agent runs
- PDF text cleaned (less raw PDF operator noise in chunks)

**Takeaway:** Full path from file → index → agent → UI, small enough to read end-to-end.

---

## Chapter 2 — See the information flow

### Q: Visualize the current RAG flow (ASCII)

**Two pipelines**

1. **Ingest** — PDF → text → clean → chunk → embed → in-memory index  
2. **Query** — question → agent loop → answer  

**Takeaway:** Ingest builds the “filing cabinet.” Query is when the agent decides whether (and how) to open it.

---

## Chapter 3 — What does LlamaIndex actually do?

### Q: Do we use LlamaIndex? (given pypdf in the pipeline)

**Answer:** Yes — but not for PDF parsing.

| Step | Library |
|------|---------|
| PDF → text | **pypdf** |
| Clean noise | our code |
| Split / embed / `VectorStoreIndex` / retrieve | **LlamaIndex** |

### Q: What logic does LlamaIndex handle — retriever? tool call?

**Answer:**

- **LlamaIndex** = search engine over the PDF (index + retrieve)  
- **LangGraph / LangChain** = tool definition, when to call it, graph routing  

### Q: So LangGraph calls LlamaIndex as a node tool call?

**Answer:** Almost.

```
LangGraph node "retrieve" (ToolNode)
  → LangChain @tool retrieve_documents
    → rag.retrieve()          ← LlamaIndex starts here
```

Not a special “LlamaIndex node” — a **tool** whose body uses LlamaIndex.

**Takeaway:** Orchestration vs retrieval are separate. That separation is the main architecture lesson.

---

## Chapter 4 — Where vectors live

### Q: Where is the vector store saved? Memory? Not a DB?

**Answer:** **In process RAM only** (`VectorStoreIndex` default). No Chroma/Qdrant/Postgres.

| Data | Where | Survives restart? |
|------|--------|-------------------|
| Vectors | RAM | No |
| PDF files | `backend/data/uploads/` | Yes (files only) |
| Index of those files | rebuilt only on upload | No auto-reload |

### Q: Tradeoffs — memory vs vector DB?

| | Memory (now) | Vector DB |
|--|--------------|-----------|
| Setup | Trivial | Extra service |
| Restart | Re-upload / re-embed | Index stays |
| Scale | One process, RAM limit | Many docs / workers |
| Best for | Learning, demos | Production, multi-user |

**Middle ground later:** LlamaIndex disk persist, then a real vector DB if needed.

**Takeaway:** Memory is the right learning default; persistence is a product decision.

---

## Chapter 5 — Report: what we built to learn

### Q: Report so far what we built to learn

Summarized as:

- **Naive RAG** = always retrieve → answer  
- **Agentic RAG** = decide → maybe retrieve → grade → maybe rewrite → answer  
- UI streams phases so the loop is visible, not a black box  

See also: root `README.md`.

---

