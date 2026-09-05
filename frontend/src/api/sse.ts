export type ConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting"
  | "failed";

export interface ServerEvent {
  version: string;
  event_id: string;
  correlation_id: string;
  type: string;
  timestamp: string;
  payload: {
    conversation_id?: number;
    user_id?: number;
    content?: string;
    [key: string]: unknown;
  };
}

interface ConnectOptions {
  token: string;
  signal: AbortSignal;
  onEvent: (event: ServerEvent) => void;
  onStateChange: (state: ConnectionState) => void;
}

const API_BASE_URL = "http://localhost:8000";


function sleep(milliseconds: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}


function parseSseBlock(block: string) {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  return {
    eventName,
    data: dataLines.join("\n"),
  };
}


export async function connectToEventStream({
  token,
  signal,
  onEvent,
  onStateChange,
}: ConnectOptions) {
  let retryCount = 0;

  while (!signal.aborted) {
    try {
      onStateChange(
        retryCount === 0 ? "connecting" : "reconnecting"
      );

      const response = await fetch(
        `${API_BASE_URL}/api/events/stream/`,
        {
          method: "GET",
          headers: {
            Authorization: `Token ${token}`,
          },
          signal,
        }
      );

      if (!response.ok) {
        throw new Error(
          `SSE request failed with status ${response.status}`
        );
      }

      if (!response.body) {
        throw new Error("SSE response has no body");
      }

      onStateChange("connected");
      retryCount = 0;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (!signal.aborted) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");

        while (boundary !== -1) {
          const block = buffer.slice(0, boundary).trim();

          buffer = buffer.slice(boundary + 2);

          if (block) {
            const { eventName, data } =
              parseSseBlock(block);

            if (eventName === "message" && data) {
              const event = JSON.parse(data) as ServerEvent;
              onEvent(event);
            }
          }

          boundary = buffer.indexOf("\n\n");
        }
      }

      if (!signal.aborted) {
        onStateChange("disconnected");
      }
    } catch (error) {
      if (signal.aborted) {
        return;
      }

      console.error("SSE connection error:", error);

      onStateChange("disconnected");
    }

    if (signal.aborted) {
      return;
    }

    retryCount += 1;

    if (retryCount > 5) {
      onStateChange("failed");
      return;
    }

    onStateChange("reconnecting");

    const delay = Math.min(
      1000 * 2 ** (retryCount - 1),
      10000
    );

    await sleep(delay);
  }
}
