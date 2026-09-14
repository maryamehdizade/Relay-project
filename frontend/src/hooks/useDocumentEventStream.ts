import { useRef, useState } from "react";


const API_URL = "http://localhost:8000";


export function useDocumentEventStream() {

  const [latestEvent, setLatestEvent] =
    useState<any>(null);

  const controller =
    useRef<AbortController | null>(null);


  async function connect() {

    const token =
      localStorage.getItem("token") || "";


    controller.current =
      new AbortController();


    const response =
      await fetch(
        `${API_URL}/api/documents/events/stream/`,
        {
          headers: {
            Authorization:
              `Token ${token}`,
          },

          signal:
            controller.current.signal,
        },
      );


    if (!response.body) {
      return;
    }


    const reader =
      response.body.getReader();


    const decoder =
      new TextDecoder();


    let buffer = "";


    while (true) {

      const {
        value,
        done,
      } = await reader.read();


      if (done) {
        break;
      }


      buffer += decoder.decode(
        value,
        {
          stream: true,
        },
      );


      let boundary =
        buffer.indexOf("\n\n");


      while (boundary !== -1) {

        const block =
          buffer.slice(
            0,
            boundary,
          );


        buffer =
          buffer.slice(
            boundary + 2,
          );


        const dataLine =
          block
            .split("\n")
            .find(
              (line) =>
                line.startsWith("data:")
            );


        if (dataLine) {

          const data =
            dataLine.replace(
              "data:",
              "",
            ).trim();


          if (data) {
            setLatestEvent(
              JSON.parse(data),
            );
          }
        }


        boundary =
          buffer.indexOf("\n\n");
      }
    }
  }


  return {
    latestEvent,
    connect,
  };
}