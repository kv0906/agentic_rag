# Chunking — contextual, recursive, doc-type matrix

> Part of the [learning hub](./README.md).  
> Contextual Retrieval, recursive mental model (VI+ASCII), doc type ↔ strategy tables.

**Chapters:** Ch. 19, Ch. 20, Ch. 21

---

## Chapter 19 — Contextual Retrieval (Contextual Embeddings + Contextual BM25)

**Q: What is the "context conundrum" in chunking, and how does Contextual Retrieval fix it?**

**Problem (classic RAG failure mode)**

When you split a long document:

```
PDF (many pages, e.g. playbook)
   │
   ▼ SentenceSplitter(512/64)
   │
   "naked chunk": "Only markets that are Live or Approved appear..."
                 ↑ missing: which page? what is the rule about? what is the document about?
```

Both embeddings and BM25 see an orphan sentence. Retrieval often fails or ranks it poorly even though the fact exists.

**Solution (Anthropic 2024 — "Contextual Retrieval")**

At **ingest time only**, before embedding and before building BM25:

For every chunk, use a cheap LLM + the *full document* to write a 50-100 token "situating context":

```
context = "This chunk is from the Huula MMBot Playbook, section on Live Markets page (p.6). It describes the eligibility filter for which markets are visible..."

augmented_for_index = context + "\n\n" + original_chunk
```

- Embed the augmented text (Contextual Embeddings)
- Index the augmented text for BM25 (Contextual BM25)

At query time the retriever (vector + BM25 + RRF + rerank) benefits from the extra context.

When packaging for the final LLM / agent, we send only the **original clean chunk** (the context was scaffolding for retrieval).

**Why this is powerful**

- One-time cost (ingest)
- Works for both semantic and keyword search
- Very large measured lift in the original paper (49% reduction in failed retrievals, 67% with rerank)
- Complements everything we already had (hybrid + CE rerank)

**Implementation in this repo (hands-on learning)**

| Location | Change |
|----------|--------|
| `backend/rag.py` | `RAG_CONTEXTUAL=1` flag, `_situate_context()`, `_create_contextual_documents()`, modified `ingest_pdf` |
| Packaging | Prefer `metadata["original_content"]` for the text sent to grade/answer |
| Trace (`RAG_TRACE=1`) | Shows `[contextual]` and a note that context helped ranking only |
| Metadata | Every node from a contextual upload has `context` + `original_content` + `contextual=True` |

**How to try it right now (for learning)**

```bash
# Terminal A
RAG_CONTEXTUAL=1 RAG_TRACE=1 \
  uvicorn backend.main:app --reload --port 8000

# In UI or curl: clear index, upload a PDF (e.g. the MMBot playbook)
# Then ask questions that rely on "buried" notes or precise terms (q06 style)
```

Watch the ingest logs: you will see "Generating situating context for N chunks..."

In traces you will see passages marked `[contextual]`.

To compare fairly:
1. `RAG_CONTEXTUAL=0` + clear + upload → baseline run (note the retrieval trace)
2. `RAG_CONTEXTUAL=1` + clear + same upload → contextual run
3. Compare which golden facts are found earlier / with higher effective rank.

**Mental model card**

```
INGEST (one time)
  full PDF text
       │
       ▼ chunk
       │
       ▼ LLM (cheap) + full doc  →  "This chunk lives in ... about X"
       │
       ▼
  text_for_index = context + chunk     ← used by embed + BM25
       │
       ▼
  VectorStoreIndex + docstore

QUERY (normal)
  query → vector(aug) + BM25(aug) → RRF → rerank → package(original only) → agent
```

**Key distinctions**

- Contextual Retrieval ≠ Reranking (different stage, different cost)
- It improves **recall** of the right chunks (what makes it into the shortlist)
- We deliberately do **not** send the generated context to the answer LLM (avoids noise)

**Tradeoffs observed / to measure**

- Ingestion slower + small $ (one time per PDF)
- Better hit rate on tricky "local" facts and eligibility notes
- In our stack it automatically upgrades both the vector path and the existing BM25 path

**Next experiments (after this chapter lands)**

- Run side-by-side on golden set (custom "pass@k" style using `must_have_in_chunks`)
- Try different context prompts (more domain specific)
- Measure token overhead in the index
- Consider storing context separately and only using it at retrieval scoring time (advanced)

**Takeaway**

Chunking throws away document-level signal.  
Contextual Retrieval gives a cheap, one-time "label" back to every chunk so the search engines can see the forest, not just the tree.

This was implemented live as Chapter 19 to learn by doing.
```

---

**Standing note:** All previous chapters remain valid. Contextual Retrieval is an **upstream augmentation** of the chunks that feed the hybrid + rerank pipeline we built in Ch. 11 + Ch. 18.

---

## Chapter 20 — Recursive chunking (mental model, tiếng Việt + ASCII)

**Q: Recursive chunking khó hiểu — giải thích dễ, có ví dụ đời thường.**

**Locked teaching memory** (Van confirmed: easy to understand + ASCII works well). Reuse this style for chunking explanations.

### One-liner

**Recursive** = cắt văn bản **thông minh theo thứ tự ưu tiên**: ưu tiên chỗ “tự nhiên” (đoạn, câu). Chỉ khi mảnh vẫn **còn quá dài** mới cắt nhỏ hơn (từ, ký tự).

### Ví dụ đời thường

Bạn có một **cuốn sách**, hộp đựng chỉ chứa **tối đa 500 từ**.

```
  Cách ngốc (fixed-size):
  Cắt đúng 500 từ, dù đang giữa câu.
  → "Anh ấy đi ra đường và gặp ..." | "... một con chó."

  Cách recursive (thông minh hơn):
  1. Cắt theo đoạn (paragraph) trước
  2. Đoạn nào vẫn > 500 từ → cắt theo câu
  3. Câu nào vẫn > 500 → cắt theo từ
  4. Vẫn dài? → cắt theo ký tự (bất đắc dĩ)
```

**“Recursive”** = làm lại bước “cắt nhỏ hơn” **cho đến khi** mỗi mảnh vừa khung giới hạn.

### Sơ đồ (đọc từ trên xuống)

```
  CẢ BÀI VĂN (rất dài)
         │
         │  Bước 1: cắt theo ĐOẠN (xuống dòng đôi, ¶)
         ▼
  [đoạn A]  [đoạn B]  [đoạn C siêu dài........]
     ✓ vừa     ✓ vừa            │
                                │  đoạn C vẫn > max
                                ▼
                    Bước 2: cắt theo CÂU (. ! ?)
                    [câu1] [câu2] [câu3... còn dài]
                       ✓     ✓         │
                                       ▼
                           Bước 3: cắt theo TỪ
                           [nhóm từ 1] [nhóm từ 2]
                                       │
                           (hiếm) Bước 4: cắt thô theo ký tự
```

### Thứ tự ưu tiên (càng trên càng “đẹp”)

| Ưu tiên | Cắt ở đâu | Vì sao tốt hơn |
|--------|-----------|----------------|
| 1 | Đoạn / paragraph | Ý thường trọn trong 1 đoạn |
| 2 | Câu | Không xé nửa câu |
| 3 | Từ | Vẫn đọc được |
| 4 | Ký tự | Chỉ khi bất khả kháng |

```
  ¶  >  .!?  >  từ  >  ký tự thô
  (tốt)                    (xấu nhất)
```

### Vì sao gọi là “recursive”?

Logic kiểu:

```
  function cắt(text):
      nếu text đã ngắn đủ → xong, trả về text

      thử cắt bằng separator hiện tại (vd: "\n\n")
      với mỗi mảnh:
          nếu mảnh vẫn dài → gọi lại cắt(mảnh) với separator yếu hơn
          nếu mảnh vừa → giữ nguyên
```

Gọi lại chính nó với quy tắc cắt “yếu hơn” → recursive (đệ quy).

**Không cần nhớ từ “đệ quy”.** Nhớ hình này:

```
  Cắt thô theo ý lớn  →  còn to thì cắt mịn hơn  →  lặp đến khi vừa
```

### Markdown / code giúp gì?

Nếu văn bản có cấu trúc rõ, “chỗ cắt đẹp” nhiều hơn:

```
  # Tiêu đề 1          ← cắt ở đây rất hợp lý
  đoạn...

  ## Tiêu đề 2
  đoạn...

  def foo():           ← code: cắt theo hàm / class
      ...
```

Chunker “thấy” ranh giới → chunk **gần với cách người đọc chia mục**.

### Map to this repo

| Idea | In code |
|------|---------|
| Classic name (LangChain) | `RecursiveCharacterTextSplitter` |
| **This repo** | `SentenceSplitter(chunk_size=512, chunk_overlap=64)` in `backend/rag.py` |
| Spirit | Sentence-aware + size cap + overlap — not blind fixed char cuts |
| Related | Ch. 19 Contextual Retrieval = labels after split, not a different splitter |

```
  FIXED-SIZE                 RECURSIVE
  ──────────                 ─────────
  Thước kẻ: mỗi N token      Dao bếp: cắt khớp “khớp xương” của bài
  Nhanh, đơn giản            Ưu tiên giữ trọn đoạn / câu
```

**Takeaway:** Recursive = ưu tiên ranh giới tự nhiên trước; chỉ cắt thô khi mảnh vẫn quá to. Overlap (lặp đuôi chunk) là lớp **khác**, thường dùng kèm để không mất ý ở đường nối.

---

## Chapter 21 — Doc type ↔ chunking strategy (case reference)

**Q: Văn bản nào phù hợp cách chunking nào?**

**Locked reference tables** — dùng khi chọn strategy theo từng corpus / file type.  
Nguyên tắc: nhìn **cấu trúc + mật độ ý + chi phí**, không phải “agentic luôn tốt hơn”.

### Decision sketch

```
  Có khung rõ (mục, ¶, code)?  ──yes──► recursive / structure-aware
           │
           no
           ▼
  Ý nhảy “nhảy topic” liên tục? ──yes──► semantic (hoặc agentic)
           │
           no
           ▼
  Cần rẻ + ổn định?  ──────────► fixed-size (+ overlap)
           │
  Doc hỗn tạp / critical RAG? ─► hybrid: recursive trước → LLM merge/label
```

### Bảng nhanh — loại văn bản → strategy

| Loại văn bản | Ví dụ | Ưu tiên | Tránh / cẩn thận |
|--------------|--------|---------|------------------|
| **Tài liệu có mục lục rõ** | handbook, playbook, docs sản phẩm, RFC | **Recursive** (+ header markdown) | Agentic full-doc nếu đã có `#`/`##` tốt — tốn tiền ít lợi |
| **PDF báo cáo / whitepaper** | IBM article, research PDF | Recursive; **Contextual** nếu chunk “trần” | Fixed thuần (cắt giữa mục) |
| **Sách / ebook dài** | textbook, novel | Recursive theo chương → paragraph; semantic nếu chương hỗn topic | Agentic một shot cả sách (context + $) |
| **Chat / email / ticket** | Slack, support, Zendesk | **Semantic** hoặc small recursive; metadata (thread, time) | Fixed lớn (lẫn nhiều ticket) |
| **FAQ / Q&A** | help center | **1 Q + A = 1 chunk** (structure) | Cắt ngang giữa Q và A |
| **Hợp đồng / pháp lý** | contract, policy | Recursive theo **điều / khoản**; giữ số điều trong metadata | Semantic thuần (dễ gộp sai điều); agentic chỉ khi cấu trúc scan kém |
| **Code / repo** | `.py`, monorepo | **Theo AST / hàm / class** (structure), không char-split | Fixed-size trên code |
| **Markdown wiki / Notion** | internal wiki | Recursive theo `#` headings | Bỏ heading → mất “địa chỉ” |
| **Bảng / CSV / số liệu** | bảng giá, metrics | **Row / section table** + caption; đôi khi không embed cả bảng | Chunk ngang giữa hàng liên quan |
| **Tin tức / blog** | 1 bài 1–3 chủ đề | Recursive paragraph; semantic nếu bài “lang mang” | Agentic overkill cho bài ngắn |
| **Transcript họp / podcast** | Zoom, YouTube | Semantic (topic shift) hoặc theo **speaker turn** + time | Fixed 512 mù (cắt giữa ý) |
| **Slide / pitch deck** | PDF slide | **1 slide ≈ 1 chunk** (+ title slide) | Recursive sentence giữa slide |
| **Log / telemetry** | server logs | Fixed / time window; filter trước | Semantic/agentic (vô nghĩa + đắt) |
| **OCR scan lởm** | PDF scan, layout vỡ | Fixed + overlap; clean trước | Recursive “tưởng” có ¶ đẹp |
| **Knowledge base mixed** | PDF + wiki + ticket | **Per-type router**: mỗi nguồn 1 strategy | Một splitter cho tất cả |

### Chi tiết theo họ chunking

#### Fixed-size (+ overlap)

```
  Hợp khi:
  • Cần rẻ, nhanh, ổn định, reproducible
  • Text khá đồng đều, ít “mục thần thánh”
  • Log, raw dump, OCR lởm

  Kém khi:
  • Ý nằm gọn theo section (playbook, contract)
  • Câu/định nghĩa dài — dễ xé đôi fact quan trọng
```

Overlap gần như luôn bật nếu dùng fixed (repo: `chunk_overlap=64` trên `chunk_size=512`).

#### Recursive (đoạn → câu → từ) — Ch. 20

```
  Hợp khi:  ★ default an toàn cho hầu hết RAG docs
  • Docs, handbook, blog, PDF có paragraph
  • Markdown có heading
  • “Muốn chunk đọc được” mà không muốn gọi LLM lúc cắt

  Kém khi:
  • Không có separator rõ (1 khối text)
  • Code (nên dùng code splitter)
  • Topic nhảy trong cùng 1 đoạn dài (recursive không “hiểu” topic)
```

Repo: `SentenceSplitter(512, 64)` ≈ nhánh này — hợp playbook / PDF học tập.

#### Semantic (cắt khi topic / embedding đổi)

```
  Hợp khi:
  • Transcript, narrative, essay “chảy”
  • 1 file trộn nhiều chủ đề không có heading
  • Muốn chunk = “cùng một ý”, không chỉ cùng một ¶

  Kém khi:
  • Chi phí embed từng câu
  • Threshold sai → cắt quá mảnh / quá to
  • Đoạn đa topic trong 1 câu phức tạp
  • Contract (sợ gộp hai điều khác nhau)
```

#### Agentic (LLM quyết định chỗ cắt ± label)

```
  Hợp khi:
  • Doc hỗn tạp, layout xấu, heading giả/OCR
  • Cần section “như biên tập viên” + title/summary cho retrieval
  • Corpus nhỏ–vừa, quality > cost (demo, internal KB tinh)
  • Pre-split recursive xong, LLM chỉ merge/split khó

  Kém / overkill khi:
  • Docs đã có markdown/toc đẹp → recursive đủ
  • Hàng nghìn PDF / re-ingest thường xuyên → $ và latency
  • Cần bit-identical chunks giữa các lần build (eval/CI)
  • Log, CSV, code (sai tool)
```

```
  Agentic “đáng tiền” nhất:
    messy PDF  ──►  LLM sections + labels  ──►  RAG quality ↑

  Agentic “lãng phí”:
    clean ## wiki  ──►  LLM cắt lại  ──►  gần như recursive + chậm hơn
```

#### Contextual labels (Ch. 19) — không thay splitter

```
  Hợp khi:  chunk đã cắt xong nhưng “trần” — mất tên doc / section
  • Playbook, multi-chapter PDF
  • Fact local (“Live or Approved”) dễ lẫn trang

  Không thay:
  • Agentic split — cái này gắn NHÃN, không đổi ranh giới cắt
```

### Router thực dụng (copy khi implement)

```
  if code:              → structure (function/class)
  if faq:               → pair Q+A
  if table-heavy:       → row/section + caption
  if markdown/toc đẹp:  → recursive by headings
  if transcript:        → semantic (± speaker)
  if messy PDF/critical → recursive pre-split
                          + optional agentic merge/label
                          + optional contextual
  else (default docs):  → recursive + overlap
                          (± contextual nếu eval còn miss)
```

### Map stack hiện tại

```
  PDF playbook / learning docs
       │
       ▼
  SentenceSplitter 512/64     ← recursive-ish, default tốt
       │
       ├─ RAG_CONTEXTUAL=1    ← khi miss fact “local”
       │
       └─ agentic split?      ← chỉ khi eval chứng minh
                                boundary rule đang làm hỏng retrieval
```

**Khi nào mới nhảy agentic:**  
(1) golden set miss vì **chunk xé ý** (không phải query/rerank), hoặc  
(2) doc **không có** cấu trúc để recursive bám.

### One-liner cheat sheet

| Nhu cầu | Chọn |
|--------|------|
| Rẻ + ổn định | Fixed + overlap |
| Default docs/PDF | **Recursive** (Ch. 20) |
| Chảy topic, ít heading | Semantic |
| Messy + cần “mục + nhãn” | **Agentic** (thường hybrid) |
| Chunk đúng nhưng search kém | **Contextual** (Ch. 19 label), không đổi dao cắt |

**Takeaway:** Chọn chunking theo **loại văn bản + cấu trúc + budget**, không theo trend. Bảng này là cheat sheet case-by-case; default của repo vẫn là recursive-ish `SentenceSplitter` ± contextual.

---

