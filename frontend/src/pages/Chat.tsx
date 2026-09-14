import { useEffect, useState } from "react";

import { useEventStream } from "../hooks/useEventStream";
import ActivityPanel from "../components/ActivityPanel";

import Navbar from "../components/Navbar";
import { getMessages } from "../api/client";
import {
  getConversations,
  createConversation,
} from "../api/client";

const API_URL = "http://localhost:8000";


interface Message {
  role: "user" | "assistant";
  content: string;
}
interface Activity {
  message: string;
  status?: string;
}

function Chat() {
  const token =
    localStorage.getItem("token") || "";

  const [conversationId, setConversationId] =
    useState<number | null>(null);

  const {
    connectionState,
    latestEvent,
    connect,
  } = useEventStream();

  
  const [messages, setMessages] =
    useState<Message[]>([]);

  

  const [activities, setActivities] = useState<Activity[]>([]);

  const [input, setInput] =
    useState("");

  const [cost, setCost] =
    useState<number | null>(null);

  async function loadConversation() {
    try {
      const conversations =
        await getConversations(token);
  
  
      if (conversations.length > 0) {
        console.log(
          "LOADED CONVERSATION:",
          conversations[0],
        );

        setConversationId(
          conversations[0].id,
        );
  
        return;
      }
  
  
      const conversation =
        await createConversation(token);
  
  
      setConversationId(
        conversation.id,
      );
  
    } catch (error) {
      console.error(
        "Failed loading conversation:",
        error,
      );
    }
  }
  useEffect(() => {
    
      async function startChat() {
  
      if (!token) {
        return;
      }
  
  
      await loadConversation();
  
    }
  
  
    startChat();
  }, []);
  useEffect(() => {

    if (!conversationId) {
      return;
    }
  
    console.log(
      "USING CONVERSATION:",
      conversationId,
    );
    
    loadMessages();
  
  
    connect(
      token,
      conversationId,
    );
  
  }, [conversationId]);

  useEffect(() => {
    if (!latestEvent) {
      return;
    }
    if (
      latestEvent.type ===
      "agent.activity"
    ) {

      const message =
        latestEvent.payload.message;
      const status =
        latestEvent.payload.status;

  
      if (typeof message === "string") {
        setActivities((previous) => [
          ...previous,
          {
            message,
            status:
              typeof status === "string"
                ? status
                : undefined,
          },
        ]);
      }
  
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
      loadCost();

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

  async function loadMessages() {
    if (!conversationId) {
      return;
    }
    try {
      const data = await getMessages(
        conversationId,
        token,
      );
  
      setMessages(
        data.map((message: any) => ({
          role:
            message.role === "assistant"
              ? "assistant"
              : "user",
          content: message.content,
        }))
      );
  
    } catch (error) {
      console.error(
        "Failed loading messages:",
        error,
      );
    }
  }
  async function loadCost() {
    const response = await fetch(
      `${API_URL}/api/conversations/${conversationId}/cost/`,
      {
        headers: {
          Authorization:
            `Token ${token}`,
        },
      },
    );
  
    if (!response.ok) {
      return;
    }
  
    const data = await response.json();
  
    setCost(
      data.total_cost,
    );
  }

  async function sendMessage() {
    if (!conversationId) {
      return;
    }
    if (!input.trim()) {
      return;
    }


    const message = input;

    setInput("");
    setActivities([]);


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

      <Navbar />

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


      <ActivityPanel
        activities={activities}
      />


      <section>
        Cost:
        {" "}
        {cost !== null
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