import { describe, expect, it } from "vitest";
import { parseEventStream } from "@/lib/sse";
import type { TurnStreamEvent } from "@/lib/types";

function chunkedStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index]));
      index += 1;
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<TurnStreamEvent[]> {
  const events: TurnStreamEvent[] = [];
  for await (const payload of parseEventStream(stream)) {
    events.push(JSON.parse(payload) as TurnStreamEvent);
  }
  return events;
}

describe("parseEventStream", () => {
  it("parses whole frames delivered in one chunk", async () => {
    const nodeEvent: TurnStreamEvent = { type: "node", node: "capture", mode: null, turn: null, detail: "" };
    const turnEvent: TurnStreamEvent = {
      type: "turn",
      node: "",
      mode: "capture",
      turn: { project_id: "p1", mode: "capture", message: "ok", question: "" },
      detail: "",
    };
    const raw = `data: ${JSON.stringify(nodeEvent)}\n\ndata: ${JSON.stringify(turnEvent)}\n\n`;

    const events = await collect(chunkedStream([raw]));

    expect(events).toEqual([nodeEvent, turnEvent]);
  });

  it("reassembles a frame split across multiple chunks", async () => {
    const event: TurnStreamEvent = { type: "node", node: "choose_mode", mode: "clarify", turn: null, detail: "" };
    const raw = `data: ${JSON.stringify(event)}\n\n`;
    const splitPoint = Math.floor(raw.length / 2);

    const events = await collect(chunkedStream([raw.slice(0, splitPoint), raw.slice(splitPoint)]));

    expect(events).toEqual([event]);
  });

  it("yields a trailing frame that has no terminating blank line", async () => {
    const event: TurnStreamEvent = { type: "error", node: "", mode: null, turn: null, detail: "graph blew up" };
    const raw = `data: ${JSON.stringify(event)}\n\n`.trimEnd();

    const events = await collect(chunkedStream([raw]));

    expect(events).toEqual([event]);
  });

  it("returns an empty sequence for an empty stream", async () => {
    const events = await collect(chunkedStream([]));

    expect(events).toEqual([]);
  });
});
