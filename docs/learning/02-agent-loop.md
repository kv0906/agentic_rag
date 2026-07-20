# Agent loop — LangGraph, grade, rewrite

> Part of the [learning hub](./README.md).  
> LangGraph nodes/edges, the retrieve→grade→rewrite loop, LLM-as-judge grade.

**Chapters:** Ch. 6, Ch. 7, Ch. 8

---

## Chapter 6 — LangGraph agent in the source

### Q: Local + flow of core agent (graph, tools, conditional edges) — ASCII

**Source:** `backend/agent.py`

**Nodes (do work)**

| Node | Job |
|------|-----|
| `generate_query_or_respond` | LLM decides: call tool or answer |
| `retrieve` | Run tool → LlamaIndex search |
| `rewrite_question` | Improve query |
| `generate_answer` | Answer from question + context |

**Conditional edges (routing)**

| After | Router | Meaning |
|-------|--------|---------|
| decide | `route_on_tool_calls` | Search or stop with direct reply |
| retrieve | `grade_documents` | Answer or rewrite (loop) |

**Fixed edges:** rewrite → decide again; answer → END.

### Q: Same flow, but human-readable (CEO level)

Plain story:

1. Listen to the question  
2. Decide if the PDF is needed  
3. Look up passages if needed  
4. Check if those passages help  
5. If not, rephrase and look again (limited tries)  
6. Answer from what was found  

**Takeaway:** LangGraph is the process. LlamaIndex is the filing cabinet.

---

## Chapter 7 — The loop

### Q: Is the loop logic already handled?

**Yes.** Implemented in `agent.py`. Max rewrite / tool rounds (~2) force an answer so it cannot thrash.

### Q: Is that loop supported by LangGraph?

**Yes.** LangGraph is built for **graphs with cycles** and **conditional edges** — decide/retrieve/grade/rewrite is a standard pattern. LangGraph runs the control flow; we define the steps and if/else.

### Q: So we control the loop via grade?

**Mostly yes for “retry or finish.”**

```
After decide:  tool?  → enter search path (or END)
After retrieve: grade → yes: answer | no: rewrite → decide → retrieve again
```

Plus a **cap** so grade cannot loop forever.

**Takeaway:** Grade is the main **loop gate**; tool-call routing is the **entry** gate.

---

## Chapter 8 — How grade knows “good enough”

### Q: How do we know if search is good enough and grade correctly?

In this repo, grade is **not** a vector-score threshold alone.

It is a **second LLM call**:

- Input: user question + retrieved chunk text  
- Output: structured `binary_score` = `"yes"` | `"no"`  
- Prompt idea: relevant if keywords or semantic meaning match  

Good for **learning and routing**. Not a guarantee of truth or answer quality.

Possible upgrades later: stricter “answerable only from context,” min similarity, or judge the **answer** (faithfulness).

### Q: So it’s like LLM-as-a-judge?

**Yes** — a small, online **LLM-as-judge for relevance routing**.

Not a full eval suite (multi-rubric offline scoring). One binary judgment used to branch the graph.

---

