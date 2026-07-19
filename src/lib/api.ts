export type DocumentMeta = {
  filename: string;
  pages: number;
  path?: string;
};

export type AgentStep = {
  node: string;
  type: string;
  content: string;
  tool_calls?: Array<{
    id?: string;
    name?: string;
    args?: Record<string, unknown>;
  }>;
  tool_name?: string;
  tool_call_id?: string | null;
};

export type ChatResponse = {
  answer: string;
  steps: AgentStep[];
};

export type StreamEvent =
  | {type: "phase"; node: string; label: string}
  | {type: "step"; step: AgentStep}
  | {type: "done"; answer: string; steps: AgentStep[]}
  | {type: "error"; message: string};

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((d: {msg?: string}) => d.msg || JSON.stringify(d))
        .join("; ");
    }
    return JSON.stringify(data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function fetchHealth(): Promise<{
  ok: boolean;
  has_documents: boolean;
  openai_key_set: boolean;
}> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchDocuments(): Promise<DocumentMeta[]> {
  const res = await fetch("/api/documents");
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.documents ?? [];
}

export async function uploadPdf(file: File): Promise<DocumentMeta[]> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.documents ?? [];
}

export async function clearDocuments(): Promise<void> {
  const res = await fetch("/api/documents", {method: "DELETE"});
  if (!res.ok) throw new Error(await parseError(res));
}

export async function chat(message: string): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message}),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** Chat mode: direct agentic RAG vs multi-agent orchestrator. */
export type ChatMode = "direct" | "orchestrator";

/**
 * Prefer direct backend URL in dev so Next rewrites don't buffer SSE.
 */
function streamEndpoint(mode: ChatMode = "direct"): string {
  const path =
    mode === "orchestrator" ? "/api/orchestrate/stream" : "/api/chat/stream";
  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    return (
      (process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ||
        "http://127.0.0.1:8000") + path
    );
  }
  return path;
}

/**
 * Stream agent phases + steps via SSE (POST body).
 * Calls `onEvent` for each parsed event until done/error.
 */
export async function chatStream(
  message: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
  mode: ChatMode = "direct",
): Promise<void> {
  const res = await fetch(streamEndpoint(mode), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({message}),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  if (!res.body) {
    throw new Error("No response body from stream");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});

    // SSE frames separated by blank lines
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const raw = trimmed.slice(5).trim();
        if (!raw || raw === "[DONE]") continue;
        try {
          const event = JSON.parse(raw) as StreamEvent;
          onEvent(event);
          if (event.type === "done" || event.type === "error") {
            return;
          }
        } catch {
          // ignore partial / non-JSON frames
        }
      }
    }
  }
}
