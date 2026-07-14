"use client";

import {useStreamingText} from "@astryxdesign/core/hooks";
import {Markdown} from "@astryxdesign/core/Markdown";
import {Spinner} from "@astryxdesign/core/Spinner";
import {HStack} from "@astryxdesign/core/HStack";
import {Text} from "@astryxdesign/core/Text";
import {cleanAnswerCitations} from "@/lib/citations";

type Props = {
  text: string;
  isStreaming: boolean;
  phaseLabel?: string | null;
};

/**
 * Smooth reveal for the final answer + optional phase spinner while waiting.
 * Strips leftover "Chunk N" labels so users see page-based citations instead.
 */
export function StreamingAnswer({text, isStreaming, phaseLabel}: Props) {
  const cleaned = cleanAnswerCitations(text);
  const displayed = useStreamingText(cleaned, isStreaming, {speed: "fast"});

  if (!text && isStreaming) {
    return (
      <HStack gap={2} vAlign="center">
        <Spinner size="sm" aria-label={phaseLabel || "Thinking"} />
        <Text type="supporting" color="secondary">
          {phaseLabel || "Thinking…"}
        </Text>
      </HStack>
    );
  }

  return (
    <Markdown density="compact" isStreaming={isStreaming} headingLevelStart={3}>
      {displayed || cleaned}
    </Markdown>
  );
}
