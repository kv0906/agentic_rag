/**
 * Parse hybrid retrieve tool text and clean agent answers for source UX.
 */

export type PassageSource = {
  index: number;
  document: string;
  page?: string;
  section?: string;
  match?: string;
  preview: string;
};

/** Parse `### Passage N` blocks from `rag.retrieve()` tool output. */
export function parsePassagesFromRetrieve(text: string): PassageSource[] {
  if (!text?.trim()) return [];
  const blocks = text.split(/(?=^### Passage \d+)/m).filter(b => b.trim());
  const out: PassageSource[] = [];

  for (const block of blocks) {
    const indexMatch = block.match(/^### Passage (\d+)/m);
    if (!indexMatch) continue;
    const index = Number(indexMatch[1]);
    const document =
      block.match(/^- Document:\s*(.+)$/m)?.[1]?.trim() || "document";
    const page = block.match(/^- Page:\s*(.+)$/m)?.[1]?.trim();
    const section = block.match(/^- Section:\s*(.+)$/m)?.[1]?.trim();
    const match = block.match(/^- Match:\s*(.+)$/m)?.[1]?.trim();
    // Body after the metadata lines
    const body = block
      .replace(/^### Passage \d+\n/, "")
      .replace(/^- Document:.*\n?/m, "")
      .replace(/^- Page:.*\n?/m, "")
      .replace(/^- Section:.*\n?/m, "")
      .replace(/^- Match:.*\n?/m, "")
      .trim();
    out.push({
      index,
      document,
      page,
      section,
      match,
      preview: body.length > 160 ? `${body.slice(0, 160).trimEnd()}…` : body,
    });
  }

  // Legacy fallback: [Chunk N | source=… | page=…]
  if (out.length === 0) {
    const legacy = [
      ...text.matchAll(
        /\[Chunk\s+(\d+)\s*\|\s*source=([^|]+)\s*\|\s*page=([^|\]]+)/gi,
      ),
    ];
    for (const m of legacy) {
      out.push({
        index: Number(m[1]),
        document: m[2].trim(),
        page: m[3].trim(),
        preview: "",
      });
    }
  }

  return out;
}

/** Short label for tool-call result line in ChatToolCalls. */
export function summarizeRetrieveForToolUi(text: string, max = 360): string {
  const passages = parsePassagesFromRetrieve(text);
  if (passages.length === 0) {
    const t = text.trim();
    return t.length <= max ? t : `${t.slice(0, max).trimEnd()}…`;
  }
  const lines = passages.map(
    p =>
      `${formatPassageLocation(p)} · ${shortDoc(p.document)}${p.match ? ` · ${p.match}` : ""}`,
  );
  const head = `Found ${passages.length} passage(s):\n${lines.join("\n")}`;
  return head.length <= max ? head : `${head.slice(0, max).trimEnd()}…`;
}

function shortDoc(name: string, max = 36): string {
  if (name.length <= max) return name;
  const base = name.replace(/\.(pdf|md|markdown)$/i, "");
  if (base.length <= max - 1) return `${base}…`;
  return `${base.slice(0, max - 1)}…`;
}

/**
 * Clean model answer so users never see "Chunk 1" / raw passage labels.
 * Turns common leftovers into (p. N) where possible.
 */
export function cleanAnswerCitations(text: string): string {
  if (!text) return text;
  let t = text;
  // [Chunk 2], (Chunk 3), Chunk 1, source=...|page=...
  t = t.replace(/\[Chunk\s+\d+[^\]]*\]/gi, "");
  t = t.replace(/\(Chunk\s+\d+[^)]*\)/gi, "");
  t = t.replace(/\bChunk\s+\d+\b/gi, "");
  // Markdown-ish junk: [Chunk 1](source=...|page=34)
  t = t.replace(
    /\[([^\]]*)\]\(source=[^)]*page[=:]?\s*(\d+)[^)]*\)/gi,
    " (p. $2)",
  );
  // Collapse leftover double spaces / empty parens
  t = t.replace(/\(\s*\)/g, "");
  t = t.replace(/[ \t]{2,}/g, " ");
  t = t.replace(/\n{3,}/g, "\n\n");
  return t.trim();
}

export function formatPassageLocation(
  source: Pick<PassageSource, "page" | "section">,
): string {
  if (source.page && source.page !== "?") return `p.${source.page}`;
  return `§ ${source.section || "Document"}`;
}

/** Unique document+location pairs for a Sources footer. */
export function uniqueSourceKeys(
  passages: PassageSource[],
): Array<{document: string; page?: string; section?: string}> {
  const seen = new Set<string>();
  const out: Array<{document: string; page?: string; section?: string}> = [];
  for (const p of passages) {
    const key = `${p.document}::${p.page || p.section || "Document"}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({document: p.document, page: p.page, section: p.section});
  }
  return out;
}
