import { useEffect, useRef, useState } from "react";

import {
  connectToEventStream,
  type ConnectionState,
  type ServerEvent,
} from "../api/sse";


export function useEventStream() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");

  const [latestEvent, setLatestEvent] =
    useState<ServerEvent | null>(null);

  const abortControllerRef =
    useRef<AbortController | null>(null);


  function connect(token: string) {
    if (!token.trim()) {
      return;
    }

    abortControllerRef.current?.abort();

    const controller = new AbortController();

    abortControllerRef.current = controller;

    void connectToEventStream({
      token: token.trim(),
      signal: controller.signal,

      onEvent: (event) => {
        setLatestEvent(event);
      },

      onStateChange: (state) => {
        setConnectionState(state);
      },
    });
  }


  function disconnect() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    setConnectionState("disconnected");
  }


  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);


  return {
    connectionState,
    latestEvent,
    connect,
    disconnect,
  };
}
