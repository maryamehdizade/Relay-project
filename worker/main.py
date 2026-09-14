import json
import os
import uuid
from datetime import datetime, timezone
import pika
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_graph import build_agent_graph
from db_tools import (get_conversation_history,get_user_message,get_document_for_indexing)
from rag import index_uploaded_document

from logger import logger
from langfuse import Langfuse


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")

COMMAND_QUEUE = "ai.commands"
EVENT_EXCHANGE = "ai.events"

langfuse = Langfuse(
    public_key=os.getenv(
        "LANGFUSE_PUBLIC_KEY"
    ),
    secret_key=os.getenv(
        "LANGFUSE_SECRET_KEY"
    ),
    host=os.getenv(
        "LANGFUSE_HOST"
    ),
)

DEAD_LETTER_QUEUE = "ai.commands.dead"

RETRY_QUEUES = [
    ("ai.commands.retry.5s", 5_000),
    ("ai.commands.retry.10s", 10_000),
    ("ai.commands.retry.20s", 20_000),
]

def build_event(event_type, payload, correlation_id):
    return {
        "version": "1.0",
        "event_id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }

def publish_activity(
    channel,
    conversation_id,
    correlation_id,
    user_id,
    message,
):
    event = build_event(
        "agent.activity",
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "message": message,
        },
        correlation_id,
    )
    try:

        channel.basic_publish(
            exchange=EVENT_EXCHANGE,
            routing_key=f"conversation.{conversation_id}",
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,
            ),
        )
    except Exception as exc:
        logger.warning(
            f"activity_publish_failed error={exc}",
            extra={
                "correlation_id": correlation_id,
            },
        )

def process_document_index_command(
    channel,
    command,
):
    payload = command["payload"]

    user_id = payload["user_id"]
    document_id = payload["document_id"]

    document = get_document_for_indexing(
        user_id=user_id,
        document_id=document_id,
    )

    if not document["found"]:
        raise ValueError(
            "Document could not be found "
            "for the authenticated user."
        )

    relative_path = Path(document["file"])

    media_root = Path("/media").resolve()

    file_path = (
        media_root / relative_path
    ).resolve()

    if media_root not in file_path.parents:
        raise ValueError(
            "Invalid document path."
        )

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(
            "Only PDF documents are currently supported."
        )

    if not file_path.exists():
        raise FileNotFoundError(
            f"Document file does not exist: {file_path}"
        )

    chunk_count = index_uploaded_document(
        document_id=document_id,
        user_id=user_id,
        file_path=file_path,
        source_name=document["name"],
    )

    event = build_event(
        "documents.indexed",
        {
            "document_id": document_id,
            "user_id": user_id,
            "chunk_count": chunk_count,
        },
        correlation_id=command["correlation_id"],
    )

    channel.basic_publish(
        exchange=EVENT_EXCHANGE,
        routing_key=f"document.{document_id}",
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    print("Published document indexed event:")
    print(json.dumps(event, indent=2))

def get_response_content(graph_result: dict) -> str:
    messages = graph_result["messages"]

    # Map tool-call IDs to their actual tool names.
    tool_names_by_id = {}

    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in getattr(message, "tool_calls", []) or []:
                tool_call_id = tool_call.get("id")
                tool_name = tool_call.get("name")

                if tool_call_id and tool_name:
                    tool_names_by_id[tool_call_id] = tool_name

    # If a real action tool ran successfully, construct the
    # customer-facing response directly from its result.
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            continue

        tool_name = getattr(message, "name", None)

        if not tool_name:
            tool_name = tool_names_by_id.get(
                getattr(message, "tool_call_id", None)
            )

        if tool_name != "create_support_ticket":
            continue

        tool_result = message.content

        if isinstance(tool_result, str):
            tool_result = json.loads(tool_result)

        if tool_result.get("success") is True:
            status = str(
                tool_result["status"]
            ).capitalize()

            return (
                "Your support ticket has been created successfully.\n\n"
                f"- **Ticket ID:** {tool_result['ticket_id']}\n"
                f"- **Subject:** {tool_result['subject']}\n"
                f"- **Status:** {status}"
            )

    final_message = messages[-1]

    if not isinstance(final_message, AIMessage):
        raise ValueError(
            "Agent did not produce a final assistant message."
        )

    return str(final_message.content)

def process_command(channel, command):

    correlation_id = command["correlation_id"]
    command_type = command["type"]
    payload = command["payload"]

    logger.info(
        "command_received",
        extra={
            "correlation_id": correlation_id,
        },
    )

    logger.info(
        f"processing_command type={command_type}",
        extra={
            "correlation_id": correlation_id,
        },
    )

    if command_type == "documents.index":
        process_document_index_command(channel,command,)
        return

    if command_type != "chat.generate_response":
        raise ValueError(
            f"Unsupported command type: {command_type}"
        )

    user_id = payload["user_id"]
    conversation_id = payload["conversation_id"]
    message_id = payload["message_id"]

    user_message = get_user_message(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    if not user_message["found"]:
        raise ValueError(
            "User message could not be found "
            "for the authenticated user."
        )

    history = get_conversation_history(
    user_id=user_id,
    conversation_id=conversation_id,
    up_to_message_id=message_id,
    limit=20,
    )
    graph_messages = []
    for item in history:
        if item["role"] == "user":
            graph_messages.append(
                HumanMessage(content=item["content"])
            )
        elif item["role"] == "assistant":
            graph_messages.append(
                AIMessage(content=item["content"])
            )
    
    graph = build_agent_graph(
        user_id=user_id,
        correlation_id=correlation_id,
        langfuse = langfuse,
        channel=channel,
        conversation_id=conversation_id,
    )
    publish_activity(
        channel,
        conversation_id,
        correlation_id,
        user_id,
        "Generating answer...",
    )

    logger.info(
        "agent_execution_started",
        extra={
            "correlation_id": correlation_id,
        },
    )
    
    
    with langfuse.start_as_current_span(
        name="relay_agent_run",
        metadata={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
        },
    ):
    
        result = graph.invoke(
            {
                "messages": graph_messages,
                "order_number": "",
                "usage": {},
                "web_searches": 0,
            },
            config={
                "recursion_limit": 8,
                "metadata": {
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                },
            },
        )
        print("FINAL USAGE:",result.get("usage"))
    
    
    langfuse.flush()

    logger.info(
        "agent_execution_finished",
        extra={
            "correlation_id": correlation_id,
        },
    )
    response_content = get_response_content(result)

    if not isinstance(response_content, str):
        response_content = str(
            response_content
        )

    usage = result.get(
        "usage",
        {},
    )
    web_searches = result.get(
        "web_searches",
        0,
        )

    event = build_event(
        "chat.response.generated",
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "content": response_content,
            "usage": usage,
            "web_searches": web_searches,
        },
        correlation_id=correlation_id,
    )

    routing_key = f"conversation.{conversation_id}"

    print(json.dumps(event, indent=2))

    channel.basic_publish(
        exchange=EVENT_EXCHANGE,
        routing_key=routing_key,
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    logger.info(
        "response_event_published",
        extra={
            "correlation_id": correlation_id,
        },
    )

def retry_or_dead_letter(
    channel,
    method,
    properties,
    body,
):
    headers = dict(
        (properties.headers or {})
    )

    try:
        command = json.loads(body)
    
        headers["correlation_id"] = (
            command["correlation_id"]
        )
    
    except Exception:
        pass

    retry_count = int(
        headers.get("x-retry-count", 0)
    )

    if retry_count < len(RETRY_QUEUES):
        retry_queue, delay_ms = RETRY_QUEUES[
            retry_count
        ]

        headers["x-retry-count"] = (
            retry_count + 1
        )

        channel.basic_publish(
            exchange="",
            routing_key=retry_queue,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers=headers,
            ),
        )

        logger.warning(
            f"command_retry_scheduled retry={retry_count + 1}/{len(RETRY_QUEUES)} delay={delay_ms // 1000}s",
            extra={
                "correlation_id": headers.get(
                    "correlation_id",
                    "unknown",
                ),
            },
        )

    else:
        headers["x-retry-count"] = retry_count

        channel.basic_publish(
            exchange="",
            routing_key=DEAD_LETTER_QUEUE,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers=headers,
            ),
        )

        logger.error(
            "command_moved_to_dead_letter",
            extra={
                "correlation_id": headers.get(
                    "correlation_id",
                    "unknown",
                ),
            },
        )

    # ACK the original message because we have safely
    # republished it either to a retry queue or dead queue.
    channel.basic_ack(
        delivery_tag=method.delivery_tag,
    )


def on_command(channel, method, properties, body):
    try:
        command = json.loads(body)

        process_command(channel, command)

        channel.basic_ack(
            delivery_tag=method.delivery_tag,
        )

    except Exception as exc:
        logger.error(
            f"command_processing_failed error={exc}",
            extra={
                "correlation_id": (
                    command.get("correlation_id")
                    if "command" in locals()
                    else "unknown"
                ),
            },
        )
        retry_or_dead_letter(
            channel=channel,
            method=method,
            properties=properties,
            body=body,
        )


def main():
    credentials = pika.PlainCredentials(
        RABBITMQ_USER,
        RABBITMQ_PASSWORD,
    )

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv(
                "RABBITMQ_HOST",
                "rabbitmq",
            ),
            port=int(
                os.getenv(
                    "RABBITMQ_PORT",
                    "5672",
                )
            ),
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
        )
    )

    channel = connection.channel()

    channel.queue_declare(
        queue=COMMAND_QUEUE,
        durable=True,
    )

    for retry_queue, delay_ms in RETRY_QUEUES:
        channel.queue_declare(
            queue=retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": delay_ms,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": COMMAND_QUEUE,
            },
        )

    channel.queue_declare(
        queue=DEAD_LETTER_QUEUE,
        durable=True,
    )

    channel.exchange_declare(
        exchange=EVENT_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=COMMAND_QUEUE,
        on_message_callback=on_command,
        auto_ack=False,
    )

    logger.info(
        "worker_connected_to_rabbitmq",
        extra={
            "correlation_id": "system",
        },
    )
    
    logger.info(
        f"waiting_for_commands queue={COMMAND_QUEUE}",
        extra={
            "correlation_id": "system",
        },
    )

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Worker stopped.")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()