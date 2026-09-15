Maryam Mehdizade

## Architecture

Relay uses an event-driven architecture.

The frontend communicates with the Django backend through REST APIs. When a user sends a message, the backend stores the message and publishes a command to RabbitMQ. The AI worker consumes this command, runs the LangGraph agent, executes any required tools, and publishes the result as an event.

The backend consumes these events, stores the final response, and streams updates to the frontend using Server-Sent Events (SSE).

The general flow looks like this:

User message -> react frontend ->django REST API -> RabbitMq Command* -> AI worker -> langGraph agent ->
-> RabbitMQ Event* -> Django event consumer -> postgreSQL -> SSE stream -> react frontend


The project is separated into several services:

### Frontend

A React application responsible for:
- user authentication flow
- chat interface
- document upload
- displaying AI activity updates
- showing conversation history and costs

### Backend

A Django REST API responsible for:
- authentication
- conversations and messages
- document management
- publishing commands
- consuming AI events
- streaming updates through SSE

### AI Worker

It uses LangGraph to manage the agent workflow and decides when to use:
- database tools
- internal document search
- web search
- support actions

### RabbitMQ

RabbitMQ acts as the communication layer between services.

Commands are used to request work from the AI worker, while events are used to publish completed work and intermediate activity updates.

### PostgreSQL

PostgreSQL is the source of truth for application data:

- users
- conversations
- messages
- orders
- documents
- costs
- support tickets

### ChromaDB

ChromaDB stores document embeddings and is used for retrieval-augmented generation (RAG).

Uploaded documents are processed, split into chunks, indexed, and later retrieved when users ask questions about their documents.

## Commands vs Events

A command represents something that should happen. Commands are sent to a specific service that is responsible for handling them.

Examples:

- `chat.generate_response`
- `documents.index`

When a user sends a message, Django does not directly run the AI agent. Instead, it creates a command and publishes it to RabbitMQ. The AI worker consumes the command and processes it asynchronously.

Events represent something that already happened. They are published after a successful action and can be consumed by different parts of the system.

Examples:

- `chat.response.generated`
- `documents.indexed`
- `agent.activity`

This separation allows the AI worker, backend, and frontend to evolve independently while keeping communication reliable.

## Message schema

All commands and events follow a common message structure.

Example:

```json
{
  "version": "1.0",
  "event_id": "unique-event-id",
  "correlation_id": "request-id",
  "type": "event-or-command-name",
  "timestamp": "timestamp",
  "payload": {}
}

## Reliability

Relay is designed to handle temporary failures without losing user requests or creating duplicate side effects.

### Retry

If a worker fails while processing a command, the message is not immediately lost.

Failed commands are moved through retry queues with increasing delays:
ai.commands -> processing failed -> retry queue (5 seconds) ->retry queue (10 seconds) -> retry queue (20 seconds) -> dead letter queue


After the retry attempts are exhausted, the message is moved to a dead-letter queue.

This prevents temporary failures from permanently losing user operations.

### ACK

RabbitMQ messages use manual acknowledgement.

The worker does not acknowledge a command immediately after receiving it.

The flow is:
Receive command -> process command -> publish result event -> ACK message
 
If the worker crashes before the ACK happens, RabbitMQ keeps the message available and delivers it again when another worker is available.

This was tested by stopping the worker during processing and verifying that the command was successfully redelivered.

### Idempotency

Some operations create external side effects, such as creating a support ticket.

To prevent duplicate actions, Relay uses `correlation_id` as an idempotency key.

Support tickets have a unique constraint on `correlation_id`.

If the same command is processed twice:
First attempt:
Create ticket
Return success

Second attempt:
Detect existing correlation_id
Return existing ticket
Do not create duplicate

This allows the system to safely retry failed operations.

## Authentication / Authorization

Relay uses token-based authentication for API access.

Every request is associated with an authenticated user, and all user-owned resources are filtered by that user.

Protected resources include:

- Conversations
- Messages
- Orders
- Documents
- Support tickets

Examples:

- A user can only retrieve their own orders.
- Uploaded documents are indexed with user metadata.
- RAG searches only return global documents or documents belonging to the authenticated user.

Authorization checks are applied at the API layer and inside backend tools to prevent users from accessing data they do not own.

###AI-specific architecture

## RAG

we use Retrieval-Augmented Generation (RAG) to answer questions from internal documents.

Uploaded documents are processed asynchronously:


User uploads document -> Django stores document metadata ->RabbitMQ document indexing command -> AI worker extracts and chunks PDF content -> Embeddings stored in ChromaDB -> Document becomes available for retrieval


When a user asks a question about internal information:

User question-> AI agent -> Internal document search tool -> ChromaDB similarity search -> Relevant document chunks -> LLM generates answer

ChromaDB metadata is used to enforce access control.

Documents are separated into:

- Global documents available to all users.
- User documents available only to the owner.

The retrieval layer filters results using the authenticated user's ID before providing context to the AI agent.
## Tool routing

Relay uses a LangGraph agent that can decide which tool should handle a user request.

The agent has access to several tools:
Order status tool, Internal document search tool, Public web search tool and Support ticket tool.

Tool execution is traced through Langfuse, allowing inspection of agent decisions and tool performance.

## SSE architecture

Relay uses Server-Sent Events (SSE) to provide real-time updates from the backend to the frontend.

The AI worker does not communicate directly with the browser.

When the AI agent performs actions, activity events are published:

Examples:

- Generating answer
- Searching orders
- Reading internal documents
- Searching the web
- Tool execution completed

The frontend subscribes to the conversation event stream and displays these updates while the final response is being generated.

SSE was chosen because the communication pattern is mainly server-to-client updates. The client sends normal HTTP requests, while the server streams events back.

The connection can be interrupted and recreated. Since conversation data is persisted separately, reconnecting does not lose previous messages.

## Design decisions

### Source of truth

PostgreSQL is the primary source of truth for application data.

Persistent data includes:

- Users
- Conversations
- Messages
- Documents
- Orders
- Support tickets

The frontend does not permanently store conversation state. It loads data from the backend API.

RabbitMQ is used for communication between services, not as permanent storage.

ChromaDB is used only for semantic document retrieval. The original document metadata and ownership information remain managed by the application database.

This separation keeps each component responsible for the type of data it manages best.

Relay separates temporary event streams from persistent system state.

RabbitMQ events and SSE streams are delivery mechanisms. They provide real-time updates while processing is happening, but they are not the final source of truth.

The system of record is PostgreSQL.

The user experience is designed around this separation.

During processing:
AI Worker-> RabbitMQ event -> SSE stream ->Frontend activity update

These events are temporary execution updates.

After completion:
AI Worker-> chat.response.generated event -> Event consumer -> PostgreSQL -> Stored assistant message

The persisted message in PostgreSQL becomes the source of truth.

If the SSE connection is interrupted, the frontend does not attempt to reconstruct state from missed events. Instead, it reconnects and reloads the conversation history from the backend API, which reads from PostgreSQL.

Therefore:

- SSE provides live visibility.
- RabbitMQ provides reliable service communication.
- PostgreSQL provides durable application state.

This design ensures that a temporary stream failure does not change what the user ultimately sees.


## Known limitations

The current version of Relay has several limitations:

- The frontend currently supports conversation-based chat but does not include advanced conversation management features such as renaming or deleting conversations.

- The AI worker currently processes commands sequentially using a single worker instance. Multiple workers can be added for higher throughput.

- Document processing currently focuses on PDF files.
