/**
 * Parses a `text/event-stream` body into the raw `data:` payload of each
 * frame. `POST /turns/stream` (see `_encode_server_sent_events` in
 * `src/mythinking/api.py`) emits exactly `data: <json>\n\n` frames — one
 * field, no `event:`/`id:` lines, no comments — so this only needs to handle
 * that shape plus chunk boundaries that split a frame across two reads.
 *
 * Browser `EventSource` isn't usable here: it only issues GET requests and
 * this endpoint requires a POST body, so the stream is read by hand off
 * `fetch`'s `ReadableStream<Uint8Array>`.
 */
export async function* parseEventStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        yield extractDataPayload(frame);
        boundary = buffer.indexOf("\n\n");
      }

      if (done) {
        const trailing = buffer.trim();
        if (trailing) {
          yield extractDataPayload(trailing);
        }
        return;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function extractDataPayload(frame: string): string {
  return frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trimStart())
    .join("\n");
}
