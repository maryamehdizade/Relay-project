import { useEffect, useState } from "react";

import { useEventStream } from "../hooks/useEventStream";


const API_URL = "http://localhost:8000";


interface Message {
  role: "user" | "assistant";
  content: string;
}


function Chat() {
  const token =
    localStorage.getItem("token") || "";

  const conversationId = 1;

  const {
    connectionState,
    latestEvent,
    connect,
  } = useEventStream();


  const [messages, setMessages] =
    useState<Message[]>([]);

  const [input, setInput] =
    useState("");

  const [cost, setCost] =
    useState<number | null>(null);


  useEffect(() => {
    if (token) {
      connect(
        token,
        conversationId,
      );
    }
  }, []);


  useEffect(() => {
    if (!latestEvent) {
      return;
    }


    if (
      latestEvent.type ===
      "chat.response.generated"
    ) {
      const content =
        latestEvent.payload.content;


      if (content) {
        setMessages((previous) => [
          ...previous,
          {
            role: "assistant",
            content,
          },
        ]);
      }


      const usage =
        latestEvent.payload.usage as
        {
          total_cost?: number;
        };


      if (usage?.total_cost) {
        setCost(
          usage.total_cost,
        );
      }
    }

  }, [latestEvent]);



  async function sendMessage() {
    if (!input.trim()) {
      return;
    }


    const message = input;

    setInput("");


    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        content: message,
      },
    ]);


    await fetch(
      `${API_URL}/api/conversations/${conversationId}/messages/`,
      {
        method: "POST",
        headers: {
          Authorization:
            `Token ${token}`,

          "Content-Type":
            "application/json",
        },

        body: JSON.stringify({
          content: message,
        }),
      },
    );
  }



  return (
    <main>

      <h1>
        Relay Chat
      </h1>


      <p>
        Connection:
        {" "}
        <strong>
          {connectionState}
        </strong>
      </p>


      <section>
        {
          messages.map(
            (message, index) => (
              <div key={index}>
                <strong>
                  {message.role}
                </strong>

                <p>
                  {message.content}
                </p>
              </div>
            ),
          )
        }
      </section>


      <section>
        <h3>
          AI Activity
        </h3>

        <p>
          Generating answer...
        </p>
      </section>


      <section>
        Cost:
        {" "}
        {cost
          ? `$${cost}`
          : "waiting"}
      </section>


      <input
        value={input}
        onChange={(event) =>
          setInput(event.target.value)
        }
        placeholder="Ask something..."
      />


      <button
        onClick={sendMessage}
      >
        Send
      </button>


    </main>
  );
}


export default Chat;