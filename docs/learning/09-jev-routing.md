# Jev routing — proposed, not implemented

## Chapter 24 — Jev chooses the path; the answer model writes the answer

Think of Jev as the receptionist, not the person writing the report.

```text
                     ┌──────────────────┐
Request ────────────►│ Jev: typed Choice │
                     └────────┬─────────┘
                              │ code reads the decision
                   ┌──────────┴───────────┐
                   ▼                      ▼
          Fast grounded Q&A        Deep agentic RAG
          retrieve once            retrieve → grade
          answer + cite            rewrite if needed → answer + cite
```

Jev returns a structured decision, probabilities, and confidence. It does not
write the response. The existing answer model remains responsible for text.

### Start with intake routing

Use one Choice with `fast`, `deep`, and `clarify` options. Send the question and
relevant known state, such as available document names and an explicit user mode
preference. Do not infer that an answer exists from the question alone.

| Option | Meaning |
|--------|---------|
| `fast` | One factual lookup or definition; one retrieval pass may suffice |
| `deep` | Comparisons, synthesis, conflicting evidence, or several dependent questions |
| `clarify` | The request lacks the subject or scope needed to retrieve usefully |

Code owns the policy: honor explicit user preferences, use a measured confidence
threshold before selecting Fast, and fall back to Deep on uncertainty or a Jev
timeout. Fast must still retrieve and cite document evidence; weak evidence should
escalate to Deep or produce an honest refusal, not an ungrounded answer.

**Important repo distinction:** today's Direct mode already runs the full agentic
graph in `backend/agent.py`. Orchestrator adds `ask_docs` around that same graph.
Those two UI modes are not yet Fast and Deep. A true Fast path would be new.
Put intake routing at the shared API/agent boundary, not only in the browser.

### Later decision steps

After intake routing works, consider passage relevance checks and claim/citation
verification. These need the retrieved text as state. Keep permissions, retry
limits, thresholds, and tool execution in ordinary code.

### Evaluate before enabling automatic Fast routing

Use human-labeled factual, multi-document, ambiguous, missing-answer, and
Vietnamese requests. Pay particular attention to complex requests incorrectly
sent to Fast. Compare correct answers, grounded citations, refusals, routing
errors, end-to-end latency, and cost against always-Deep behavior. Follow the
six-category harness in Chapter 22; confidence alone is not correctness.

Sources: [Choice](https://docs.typesafe.ai/primitives/choice),
[intent routing](https://docs.typesafe.ai/patterns/intent-routing), and
[confidence](https://docs.typesafe.ai/confidence), read on 2026-10-11.
