import { useState } from "react";

import { useEventStream } from "./hooks/useEventStream";

import "./App.css";


function App() {
  const [token, setToken] = useState("");
  const [conversationId, setConversationId] = useState(1);

  const {
    connectionState,
    latestEvent,
    connect,
    disconnect,
  } = useEventStream();

  
  return (
    <main className="app">
      <h1>Relay</h1>

      <section>
        <h2>SSE Connection Test</h2>

        <label htmlFor="token">
          Authentication token
        </label>

        <input
          id="token"
          type="password"
          value={token}
          onChange={(event) => {
            setToken(event.target.value);
          }}
          placeholder="Paste token here"
        />
        <label htmlFor="conversation">
          Conversation ID
        </label>
        <input
          id="conversation"
          type="number"
          min="1"
          value={conversationId}
          onChange={(event) => {
            setConversationId(Number(event.target.value));
          }}
        />
        <div className="buttons">
          <button
            type="button"
            onClick={() => connect(token, conversationId)}
          >
            Connect
          </button>

          <button
            type="button"
            onClick={disconnect}
          >
            Disconnect
          </button>
        </div>

        <p>
          Connection: <strong>{connectionState}</strong>
        </p>
      </section>

      <section>
        <h2>Latest Server Event</h2>

        {latestEvent ? (
          <pre>
            {JSON.stringify(latestEvent, null, 2)}
          </pre>
        ) : (
          <p>No event received yet.</p>
        )}
      </section>
    </main>
  );
}

export default App;