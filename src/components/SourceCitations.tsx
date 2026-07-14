"use client";

import {HStack} from "@astryxdesign/core/HStack";
import {VStack} from "@astryxdesign/core/VStack";
import {Text} from "@astryxdesign/core/Text";
import {Token} from "@astryxdesign/core/Token";
import type {PassageSource} from "@/lib/citations";
import {uniqueSourceKeys} from "@/lib/citations";

type Props = {
  passages: PassageSource[];
};

/**
 * Compact "where this came from" strip under the assistant answer.
 */
export function SourceCitations({passages}: Props) {
  const keys = uniqueSourceKeys(passages);
  if (keys.length === 0) return null;

  return (
    <VStack gap={2} style={{marginBlockStart: "var(--spacing-2)"}}>
      <Text type="supporting" color="secondary">
        Sources in this answer
      </Text>
      <HStack gap={2} wrap="wrap">
        {keys.map(k => (
          <Token
            key={`${k.document}-${k.page}`}
            size="sm"
            color="gray"
            label={`p.${k.page} · ${shortName(k.document)}`}
            description={`${k.document} — page ${k.page}`}
          />
        ))}
      </HStack>
    </VStack>
  );
}

function shortName(name: string, max = 28): string {
  const base = name.replace(/\.pdf$/i, "");
  if (base.length <= max) return base;
  return `${base.slice(0, max - 1)}…`;
}
