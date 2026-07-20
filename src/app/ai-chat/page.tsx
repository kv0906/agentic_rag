// Copyright (c) Meta Platforms, Inc. and affiliates.
// Adapted from `npx astryx template ai-chat` for Agentic RAG (LangGraph + LlamaIndex).

'use client';

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ChangeEvent,
} from 'react';

import {
  HStack,
  VStack,
  StackItem,
  Layout,
  LayoutContent,
} from '@astryxdesign/core/Layout';
import {Text, Heading} from '@astryxdesign/core/Text';
import {
  ChatComposer,
  ChatComposerDrawer,
  ChatComposerInput,
  ChatLayout,
  ChatMessage,
  ChatMessageBubble,
  ChatMessageList,
  ChatMessageMetadata,
  ChatSystemMessage,
  ChatToolCalls,
} from '@astryxdesign/core/Chat';
import {Avatar} from '@astryxdesign/core/Avatar';
import {Card} from '@astryxdesign/core/Card';
import {ClickableCard} from '@astryxdesign/core/ClickableCard';
import {Section} from '@astryxdesign/core/Section';
import {Markdown} from '@astryxdesign/core/Markdown';
import {Timestamp} from '@astryxdesign/core/Timestamp';
import {Token} from '@astryxdesign/core/Token';
import {Button} from '@astryxdesign/core/Button';
import {Icon} from '@astryxdesign/core/Icon';
import {Dialog, DialogHeader} from '@astryxdesign/core/Dialog';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {Banner} from '@astryxdesign/core/Banner';
import {Toolbar} from '@astryxdesign/core/Toolbar';
import {useResizable, ResizeHandle} from '@astryxdesign/core/Resizable';
import {
  SegmentedControl,
  SegmentedControlItem,
} from '@astryxdesign/core/SegmentedControl';

import {
  DocumentTextIcon,
  PaperClipIcon,
  XMarkIcon,
  ChevronRightIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';

import {StreamingAnswer} from '@/components/StreamingAnswer';
import {SourceCitations} from '@/components/SourceCitations';
import {
  parsePassagesFromRetrieve,
  summarizeRetrieveForToolUi,
  type PassageSource,
} from '@/lib/citations';
import {
  chatStream,
  clearDocuments,
  fetchDocuments,
  fetchHealth,
  uploadDocument,
  type AgentStep,
  type ChatMode,
  type DocumentMeta,
} from '@/lib/api';

// Below this width the split-pane collapses to a single chat column.
const MOBILE_MAX_WIDTH = 767;

const root: CSSProperties = {
  height: '100dvh',
  width: '100%',
  containerType: 'inline-size',
  containerName: 'artifact',
};
const chatColumn: CSSProperties = {
  flex: 1,
  width: '100%',
  minWidth: 0,
  height: '100%',
};
const chatLayout: CSSProperties = {
  flex: 1,
  minHeight: 0,
};
const artifactCard: CSSProperties = {
  marginBlockStart: 'var(--spacing-2)',
};
const artifactScroll: CSSProperties = {
  flex: 1,
  overflowY: 'auto',
};
const articleBody: CSSProperties = {
  maxWidth: 720,
  marginInline: 'auto',
};

const artifactPanelWidthVar = (size: number | string): CSSProperties =>
  ({
    '--artifact-panel-width': typeof size === 'number' ? `${size}px` : size,
  }) as CSSProperties;

const AI_CHAT_CSS = `
.ai-chat-resize-handle {
  display: flex;
}
.ai-chat-artifact-panel {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  width: var(--artifact-panel-width);
  flex-shrink: 0;
}
@container artifact (max-width: ${MOBILE_MAX_WIDTH}px) {
  .ai-chat-resize-handle {
    display: none;
  }
  .ai-chat-artifact-panel {
    display: none;
    width: 100%;
    flex-shrink: 1;
  }
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
`;

const HOW_IT_WORKS = `## Agentic RAG

This chat is backed by a **LangGraph** agent and a **LlamaIndex** retriever.

### Mode: Direct RAG

1. **generate_query_or_respond** — model decides whether to call \`retrieve_documents\` or answer directly
2. **retrieve** — LlamaIndex hybrid search over your document chunks
3. **grade_documents** — structured yes/no relevance check
4. **rewrite_question** — improve the query if chunks look weak
5. **generate_answer** — final grounded answer

### Mode: Orchestrator

Multi-agent path over the same specialist:

\`\`\`
you → orchestrator → ask_docs → agentic RAG → answer
\`\`\`

The orchestrator does **not** retrieve itself. It calls \`ask_docs\` (same contract as \`POST /api/chat\`).

### Try it

- Upload a short PDF or Markdown file with the paperclip
- Switch **Direct** vs **Orchestrator** above the composer
- Ask something that needs the document
- Watch tool calls: \`retrieve_documents\` (direct) or \`ask_docs\` (orchestrator)
- Say *hello* — either path can reply without tools
`;

type ToolCallUi = {
  key: string;
  name: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  target?: string;
  resultDetail?: string;
};

type UiMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
  toolCalls?: ToolCallUi[];
  /** Passages from hybrid retrieve — shown as Sources under the answer */
  sources?: PassageSource[];
  graphPath?: string;
  /** Live agent phase while streaming */
  phaseLabel?: string | null;
  isStreaming?: boolean;
  /** Which path produced this assistant turn */
  mode?: ChatMode;
};

function nodeLabel(node: string): string {
  switch (node) {
    case 'generate_query_or_respond':
      return 'decide';
    case 'retrieve':
      return 'retrieve';
    case 'rewrite_question':
      return 'rewrite';
    case 'generate_answer':
      return 'answer';
    case 'orchestrator':
      return 'orchestrator';
    case 'tools':
      return 'ask_docs';
    default:
      return node;
  }
}

function previewToolResult(name: string, content: string): string {
  if (name.includes('retrieve')) {
    return summarizeRetrieveForToolUi(content);
  }
  // ask_docs (and similar) return prose, not passage dumps
  return previewText(content, 280);
}

function graphPathFromSteps(steps: AgentStep[]): string {
  return steps
    .map(s => nodeLabel(s.node))
    .filter((n, i, arr) => arr.indexOf(n) === i)
    .join(' → ');
}

function previewText(content: string, max = 320): string {
  const t = content.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max).trimEnd()}…`;
}

/** Apply one streamed agent step onto the live assistant tool-call list. */
function applyStepToToolCalls(
  prev: ToolCallUi[] | undefined,
  step: AgentStep,
): ToolCallUi[] {
  const calls = [...(prev ?? [])];

  if (step.tool_calls?.length) {
    for (const tc of step.tool_calls) {
      const key = tc.id || `${step.node}-${tc.name}-${calls.length}`;
      const query =
        typeof tc.args?.query === 'string'
          ? tc.args.query
          : JSON.stringify(tc.args ?? {});
      const existing = calls.findIndex(c => c.key === key);
      const next: ToolCallUi = {
        key,
        name: tc.name || 'tool',
        status: 'running',
        target: query,
      };
      if (existing >= 0) calls[existing] = {...calls[existing], ...next};
      else calls.push(next);
    }
  }

  if (step.type === 'tool' || step.node === 'retrieve' || step.node === 'tools') {
    const toolName = step.tool_name || 'tool';
    const preview = previewToolResult(toolName, step.content || '');
    const last = [...calls]
      .reverse()
      .find(
        c =>
          (c.name === toolName ||
            c.name.includes('retrieve') ||
            c.name === 'ask_docs' ||
            c.name === step.tool_name) &&
          c.status !== 'complete',
      );
    if (last) {
      last.resultDetail = preview;
      last.status = 'complete';
    } else {
      calls.push({
        key: `tool-${calls.length}-${Date.now()}`,
        name: toolName || 'retrieve_documents',
        status: 'complete',
        target: toolName === 'ask_docs' ? 'document specialist' : 'retrieval result',
        resultDetail: preview,
      });
    }
  }

  if (step.node === 'rewrite_question' && step.content) {
    // Mark any still-running retrieve as complete before rewrite
    for (const c of calls) {
      if (c.status === 'running') c.status = 'complete';
    }
    calls.push({
      key: `rewrite-${calls.length}-${Date.now()}`,
      name: 'rewrite_question',
      status: 'complete',
      target: previewText(step.content, 160),
    });
  }

  if (step.node === 'generate_answer' || step.node === 'orchestrator') {
    for (const c of calls) {
      if (c.status === 'running' || c.status === 'pending') {
        // Don't force-complete ask_docs until its tool result lands
        if (step.node === 'orchestrator' && c.name === 'ask_docs' && !c.resultDetail) {
          continue;
        }
        c.status = 'complete';
      }
    }
  }

  return calls;
}

function ArtifactActions({
  onClose,
  onClear,
  hasDocs,
}: {
  onClose?: () => void;
  onClear?: () => void;
  hasDocs?: boolean;
}) {
  return (
    <>
      {hasDocs && onClear != null && (
        <Button
          label="Clear documents"
          variant="ghost"
          size="sm"
          icon={<Icon icon={TrashIcon} size="sm" />}
          isIconOnly
          onClick={onClear}
        />
      )}
      {onClose != null && (
        <Button
          label="Close panel"
          variant="ghost"
          size="sm"
          icon={<Icon icon={XMarkIcon} size="sm" />}
          isIconOnly
          onClick={onClose}
        />
      )}
    </>
  );
}

function ArtifactBody({
  docs,
  keySet,
}: {
  docs: DocumentMeta[];
  keySet: boolean | null;
}) {
  return (
    <Section variant="transparent" style={artifactScroll}>
      <VStack gap={3} style={articleBody} padding={4}>
        <Heading level={1}>Documents & graph</Heading>
        <Text type="supporting" color="secondary">
          {keySet === false
            ? 'Set OPENAI_API_KEY in .env and restart the backend.'
            : docs.length
              ? `${docs.length} document${docs.length === 1 ? '' : 's'} indexed in LlamaIndex (in-memory).`
              : 'No documents yet — attach one from the composer.'}
        </Text>
        {docs.length > 0 ? (
          <VStack gap={2}>
            {docs.map(d => (
              <Card key={d.filename} variant="muted" padding={3}>
                <HStack gap={2} vAlign="center">
                  <Icon icon={DocumentTextIcon} size="sm" color="secondary" />
                  <VStack gap={0}>
                    <Text type="label" weight="semibold">
                      {d.filename}
                    </Text>
                    <Text type="supporting" color="secondary">
                      {d.file_type === 'pdf'
                        ? `${d.pages ?? 0} page${d.pages === 1 ? '' : 's'}`
                        : `${d.sections ?? 0} section${d.sections === 1 ? '' : 's'}`}
                    </Text>
                  </VStack>
                </HStack>
              </Card>
            ))}
          </VStack>
        ) : null}
        <Markdown density="compact">{HOW_IT_WORKS}</Markdown>
      </VStack>
    </Section>
  );
}

function DocsCard({onOpen, docs}: {onOpen: () => void; docs: DocumentMeta[]}) {
  const title =
    docs.length === 0
      ? 'No documents indexed'
      : docs.length === 1
        ? docs[0].filename
        : `${docs.length} documents`;
  return (
    <ClickableCard
      label="Open documents panel"
      onClick={onOpen}
      variant="muted"
      padding={3}
      maxWidth={360}
      style={artifactCard}>
      <HStack gap={3} vAlign="center" width="100%">
        <Icon icon={DocumentTextIcon} size="md" color="secondary" />
        <StackItem size="fill">
          <VStack gap={0}>
            <Text type="label" weight="semibold">
              {title}
            </Text>
            <Text type="supporting" color="secondary">
              LlamaIndex · in-memory
            </Text>
          </VStack>
        </StackItem>
        <Icon icon={ChevronRightIcon} size="sm" color="secondary" />
      </HStack>
    </ClickableCard>
  );
}

export default function AIChatConversationTemplate() {
  const [docs, setDocs] = useState<DocumentMeta[]>([]);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [chatMode, setChatMode] = useState<ChatMode>('direct');
  const [isChatting, setIsChatting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keySet, setKeySet] = useState<boolean | null>(null);
  const [isArtifactDialogOpen, setIsArtifactDialogOpen] = useState(false);
  const [isArtifactOpen, setIsArtifactOpen] = useState(true);
  const rootRef = useRef<HTMLElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Don't pass autoSaveId into useResizable: it reads localStorage during the
  // first client render (SSR always uses defaultSize) → hydration mismatch.
  // Restore + persist ourselves after mount so server/client first paint match.
  const ARTIFACT_WIDTH_KEY = 'astryx-resizable:ai-chat-artifact-panel';
  const [artifactWidthHydrated, setArtifactWidthHydrated] = useState(false);

  const artifactResize = useResizable({
    defaultSize: 420,
    minSizePx: 320,
    maxSizePx: 720,
  });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(ARTIFACT_WIDTH_KEY);
      if (raw != null) {
        const parsed = JSON.parse(raw) as unknown;
        if (typeof parsed === 'number' && Number.isFinite(parsed)) {
          artifactResize.resize(parsed);
        }
      }
    } catch {
      /* ignore corrupt storage */
    }
    setArtifactWidthHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- restore once on mount
  }, []);

  useEffect(() => {
    if (!artifactWidthHydrated) return;
    try {
      localStorage.setItem(
        ARTIFACT_WIDTH_KEY,
        JSON.stringify(artifactResize.size),
      );
    } catch {
      /* ignore quota / private mode */
    }
  }, [artifactResize.size, artifactWidthHydrated]);

  const refresh = useCallback(async () => {
    try {
      const [health, documents] = await Promise.all([
        fetchHealth(),
        fetchDocuments(),
      ]);
      setKeySet(health.openai_key_set);
      setDocs(documents);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Backend unreachable. Is the API running on :8000?',
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openArtifact = () => {
    const width = rootRef.current?.offsetWidth ?? Infinity;
    if (width <= MOBILE_MAX_WIDTH) {
      setIsArtifactDialogOpen(true);
    } else {
      setIsArtifactOpen(true);
    }
  };

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setError(null);
    try {
      const documents = await uploadDocument(file);
      setDocs(documents);
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'system',
          content: `Indexed “${file.name}”. Ask a question about it.`,
          createdAt: new Date().toISOString(),
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, []);

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleUpload(file);
  };

  const handleClear = useCallback(async () => {
    setError(null);
    try {
      await clearDocuments();
      setDocs([]);
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'system',
          content: 'Cleared all documents from the index.',
          createdAt: new Date().toISOString(),
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Clear failed');
    }
  }, []);

  const handleSubmit = useCallback(
    async (value: string) => {
      const text = value.trim();
      if (!text || isChatting) return;

      setDraft('');
      setError(null);
      setIsChatting(true);

      const now = new Date().toISOString();
      const assistantId = crypto.randomUUID();
      const collectedSteps: AgentStep[] = [];
      const mode = chatMode;

      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: text,
          createdAt: now,
        },
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          createdAt: now,
          phaseLabel:
            mode === 'orchestrator'
              ? 'Starting orchestrator…'
              : 'Starting agent…',
          isStreaming: true,
          toolCalls: [],
          mode,
        },
      ]);

      const patchAssistant = (patch: Partial<UiMessage>) => {
        setMessages(prev =>
          prev.map(m => (m.id === assistantId ? {...m, ...patch} : m)),
        );
      };

      try {
        await chatStream(
          text,
          event => {
            if (event.type === 'phase') {
              patchAssistant({phaseLabel: event.label});
              // When entering tool/retrieve, flip any pending tool to running
              if (event.node === 'retrieve' || event.node === 'tools') {
                setMessages(prev =>
                  prev.map(m => {
                    if (m.id !== assistantId) return m;
                    const toolCalls = (m.toolCalls ?? []).map(c =>
                      c.status === 'pending'
                        ? {...c, status: 'running' as const}
                        : c,
                    );
                    return {...m, toolCalls, phaseLabel: event.label};
                  }),
                );
              }
              return;
            }

            if (event.type === 'step') {
              collectedSteps.push(event.step);
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m;
                  const toolCalls = applyStepToToolCalls(
                    m.toolCalls,
                    event.step,
                  );
                  // Final AI content mid-stream (no open tool calls)
                  let content = m.content;
                  if (
                    event.step.type === 'ai' &&
                    event.step.content &&
                    !event.step.tool_calls?.length &&
                    (event.step.node === 'generate_answer' ||
                      event.step.node === 'generate_query_or_respond' ||
                      event.step.node === 'orchestrator')
                  ) {
                    content = event.step.content;
                  }
                  let sources = m.sources;
                  if (
                    (event.step.type === 'tool' ||
                      event.step.node === 'retrieve') &&
                    event.step.content &&
                    (event.step.tool_name || '').includes('retrieve')
                  ) {
                    const parsed = parsePassagesFromRetrieve(event.step.content);
                    if (parsed.length) sources = parsed;
                  }
                  return {
                    ...m,
                    toolCalls,
                    content,
                    sources,
                    graphPath: graphPathFromSteps(collectedSteps) || m.graphPath,
                  };
                }),
              );
              return;
            }

            if (event.type === 'error') {
              throw new Error(event.message);
            }

            if (event.type === 'done') {
              let sources: PassageSource[] | undefined;
              let calls: ToolCallUi[] = [];
              for (const s of event.steps) {
                calls = applyStepToToolCalls(calls, s);
                if (
                  (s.type === 'tool' || s.node === 'retrieve') &&
                  s.content &&
                  (s.tool_name || '').includes('retrieve')
                ) {
                  const parsed = parsePassagesFromRetrieve(s.content);
                  if (parsed.length) sources = parsed;
                }
              }
              for (const c of calls) {
                if (c.status !== 'complete' && c.status !== 'error') {
                  c.status = 'complete';
                }
              }
              patchAssistant({
                content: event.answer,
                phaseLabel: null,
                isStreaming: false,
                graphPath: graphPathFromSteps(event.steps) || undefined,
                sources,
                toolCalls: calls.length ? calls : undefined,
              });
            }
          },
          undefined,
          mode,
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Chat failed';
        setError(msg);
        patchAssistant({
          content:
            'Something went wrong running the agent. Check the error banner and backend logs.',
          phaseLabel: null,
          isStreaming: false,
        });
      } finally {
        setIsChatting(false);
        // Ensure streaming flag clears even if stream ended without done
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId && m.isStreaming
              ? {...m, isStreaming: false, phaseLabel: null}
              : m,
          ),
        );
      }
    },
    [isChatting, chatMode],
  );

  return (
    <VStack ref={rootRef} style={root}>
      <style>{AI_CHAT_CSS}</style>
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,text/markdown,.pdf,.md,.markdown"
        className="sr-only"
        onChange={onFileChange}
      />

      {error ? (
        <Banner
          status="error"
          title="Something went wrong"
          description={error}
          isDismissable
          onDismiss={() => setError(null)}
          container="section"
        />
      ) : keySet === false ? (
        <Banner
          status="warning"
          title="OPENAI_API_KEY missing"
          description="Copy .env.example to .env, set your key, then restart the backend."
          container="section"
        />
      ) : null}

      <Layout
        height="fill"
        content={
          <LayoutContent padding={0}>
            <HStack height="100%">
              <VStack style={chatColumn}>
                <ChatLayout
                  density="spacious"
                  style={chatLayout}
                  emptyState={
                    messages.length === 0 ? (
                      <EmptyState
                        title={
                          docs.length
                            ? 'Ask about your documents'
                            : 'Upload a document to start'
                        }
                        description={
                          chatMode === 'orchestrator'
                            ? 'Orchestrator mode: a LangGraph manager calls ask_docs → your agentic RAG specialist.'
                            : 'Direct mode: LangGraph decides when to retrieve; LlamaIndex indexes your document.'
                        }
                        actions={
                          <Button
                            label="Upload document"
                            variant="primary"
                            size="sm"
                            icon={<Icon icon={PaperClipIcon} size="sm" />}
                            isLoading={isUploading}
                            onClick={() => fileInputRef.current?.click()}
                          />
                        }
                      />
                    ) : undefined
                  }
                  composer={
                    <ChatComposer
                      value={draft}
                      onChange={setDraft}
                      onSubmit={v => void handleSubmit(v)}
                      placeholder={
                        docs.length
                          ? chatMode === 'orchestrator'
                            ? 'Orchestrator will call ask_docs…'
                            : 'Ask anything about your documents…'
                          : 'Upload a PDF or Markdown file, or say hello'
                      }
                      isDisabled={isChatting || isUploading}
                      isStopShown={isChatting}
                      input={<ChatComposerInput />}
                      drawer={
                        docs.length ? (
                          <ChatComposerDrawer
                            count={docs.length}
                            label="Documents">
                            <HStack gap={1} wrap="wrap">
                              {docs.map(d => (
                                <Token key={d.filename} label={d.filename} />
                              ))}
                            </HStack>
                          </ChatComposerDrawer>
                        ) : undefined
                      }
                      headerActions={
                        <>
                          <SegmentedControl
                            label="Chat mode"
                            size="sm"
                            value={chatMode}
                            onChange={v => setChatMode(v as ChatMode)}
                            isDisabled={isChatting}>
                            <SegmentedControlItem
                              value="direct"
                              label="Direct"
                            />
                            <SegmentedControlItem
                              value="orchestrator"
                              label="Orchestrator"
                            />
                          </SegmentedControl>
                          <Button
                            label="Attach document"
                            variant="ghost"
                            size="sm"
                            icon={<Icon icon={PaperClipIcon} size="sm" />}
                            isIconOnly
                            isLoading={isUploading}
                            onClick={() => fileInputRef.current?.click()}
                          />
                          <Button
                            label="Open documents panel"
                            variant="ghost"
                            size="sm"
                            icon={<Icon icon={DocumentTextIcon} size="sm" />}
                            isIconOnly
                            onClick={openArtifact}
                          />
                        </>
                      }
                      footerActions={
                        <Text type="supporting" color="secondary">
                          {chatMode === 'orchestrator'
                            ? 'Orchestrator → ask_docs → RAG'
                            : 'Direct RAG · LangGraph + LlamaIndex'}
                        </Text>
                      }
                    />
                  }>
                  {messages.length > 0 ? (
                    <ChatMessageList>
                      <ChatSystemMessage variant="divider">
                        Session
                      </ChatSystemMessage>

                      {messages.map(m => {
                        if (m.role === 'system') {
                          return (
                            <ChatSystemMessage key={m.id}>
                              {m.content}
                            </ChatSystemMessage>
                          );
                        }

                        if (m.role === 'user') {
                          return (
                            <ChatMessage key={m.id} sender="user">
                              {docs.length > 0 ? (
                                <HStack gap={1} wrap="wrap">
                                  {docs.map(d => (
                                    <Token
                                      key={`${m.id}-${d.filename}`}
                                      label={d.filename}
                                    />
                                  ))}
                                </HStack>
                              ) : null}
                              <ChatMessageBubble
                                metadata={
                                  <ChatMessageMetadata
                                    timestamp={
                                      <Timestamp
                                        value={m.createdAt}
                                        format="time"
                                      />
                                    }
                                    status="delivered"
                                  />
                                }>
                                {m.content}
                              </ChatMessageBubble>
                            </ChatMessage>
                          );
                        }

                        return (
                          <ChatMessage
                            key={m.id}
                            sender="assistant"
                            avatar={
                              <Avatar
                                name={
                                  m.mode === 'orchestrator'
                                    ? 'Orchestrator'
                                    : 'Agent'
                                }
                                size="small"
                              />
                            }>
                            {m.toolCalls && m.toolCalls.length > 0 ? (
                              <ChatToolCalls
                                defaultIsExpanded
                                calls={m.toolCalls.map(c => ({
                                  key: c.key,
                                  name: c.name,
                                  status: c.status,
                                  target: c.target,
                                  resultDetail: c.resultDetail,
                                }))}
                              />
                            ) : null}
                            <ChatMessageBubble variant="ghost">
                              <StreamingAnswer
                                text={m.content}
                                isStreaming={Boolean(m.isStreaming)}
                                phaseLabel={m.phaseLabel}
                              />
                              {!m.isStreaming && m.sources && m.sources.length > 0 ? (
                                <SourceCitations passages={m.sources} />
                              ) : null}
                            </ChatMessageBubble>
                            {m.graphPath && !m.isStreaming ? (
                              <ChatSystemMessage>
                                Graph path: {m.graphPath}
                              </ChatSystemMessage>
                            ) : null}
                            {!m.isStreaming ? (
                              <DocsCard onOpen={openArtifact} docs={docs} />
                            ) : null}
                            <ChatMessageMetadata
                              timestamp={
                                <Timestamp
                                  value={m.createdAt}
                                  format="time"
                                />
                              }
                              status={m.isStreaming ? 'sending' : undefined}
                              footer={
                                <Text type="supporting" color="secondary">
                                  {m.isStreaming
                                    ? m.phaseLabel ||
                                      (m.mode === 'orchestrator'
                                        ? 'Orchestrator working…'
                                        : 'Agent working…')
                                    : m.mode === 'orchestrator'
                                      ? 'Orchestrator'
                                      : 'Agent'}
                                </Text>
                              }
                            />
                          </ChatMessage>
                        );
                      })}
                    </ChatMessageList>
                  ) : null}
                </ChatLayout>
              </VStack>

              {isArtifactOpen && (
                <>
                  <ResizeHandle
                    direction="horizontal"
                    resizable={artifactResize.props}
                    isReversed
                    pillPlacement="start"
                    hasDivider
                    label="Resize artifact panel"
                    className="ai-chat-resize-handle"
                  />

                  <Card
                    variant="transparent"
                    height="100%"
                    className="ai-chat-artifact-panel"
                    style={artifactPanelWidthVar(artifactResize.size)}>
                    <Toolbar
                      label="Artifact actions"
                      dividers={['bottom']}
                      startContent={
                        <HStack gap={3} vAlign="center">
                          <Icon
                            icon={DocumentTextIcon}
                            size="sm"
                            color="secondary"
                          />
                          <VStack gap={0}>
                            <Text type="label" weight="semibold">
                              Documents & graph
                            </Text>
                            <Text type="supporting" color="secondary">
                              Agentic RAG · learning
                            </Text>
                          </VStack>
                        </HStack>
                      }
                      endContent={
                        <ArtifactActions
                          hasDocs={docs.length > 0}
                          onClear={() => void handleClear()}
                          onClose={() => setIsArtifactOpen(false)}
                        />
                      }
                    />
                    <ArtifactBody docs={docs} keySet={keySet} />
                  </Card>
                </>
              )}
            </HStack>
          </LayoutContent>
        }
      />

      <Dialog
        isOpen={isArtifactDialogOpen}
        onOpenChange={setIsArtifactDialogOpen}
        purpose="info"
        variant="fullscreen">
        <Layout
          header={
            <DialogHeader
              title="Documents & graph"
              subtitle="Agentic RAG · learning"
              hasDivider
              onOpenChange={setIsArtifactDialogOpen}
              endContent={
                docs.length > 0 ? (
                  <Button
                    label="Clear documents"
                    variant="ghost"
                    size="sm"
                    icon={<Icon icon={TrashIcon} size="sm" />}
                    isIconOnly
                    onClick={() => void handleClear()}
                  />
                ) : undefined
              }
            />
          }
          content={
            <LayoutContent padding={0}>
              <ArtifactBody docs={docs} keySet={keySet} />
            </LayoutContent>
          }
        />
      </Dialog>
    </VStack>
  );
}
