import assert from "node:assert/strict";
import test from "node:test";
import {chatStream} from "./api.ts";

test("chat stream reports agent errors, consumer errors, and incomplete answers", async (t) => {
  const original = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = original;
  });

  globalThis.fetch = async () =>
    new Response('data: {"type":"error","message":"Backend failed"}\n\n');
  await assert.rejects(
    chatStream("question", () => {}),
    /Backend failed/,
  );
  await assert.rejects(
    chatStream("question", () => {
      throw new Error("Consumer failed");
    }),
    /Consumer failed/,
  );

  globalThis.fetch = async () =>
    new Response(
      'data: {"type":"phase","node":"retrieve","label":"Retrieving"}\n\n',
    );
  await assert.rejects(
    chatStream("question", () => {}),
    /ended before/,
  );

  const events = [];
  globalThis.fetch = async () =>
    new Response('data: {"type":"done","answer":"19 requests","steps":[]}\n\n');
  await chatStream("question", (event) => events.push(event));
  assert.equal(events[0].answer, "19 requests");
});
