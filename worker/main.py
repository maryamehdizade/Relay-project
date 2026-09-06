import json
import os
import uuid
from datetime import datetime, timezone
import pika

from langchain_core.messages import AIMessage, HumanMessage

from agent_graph import build_agent_graph
from db_tools import (get_conversation_history,get_user_message,)


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")

COMMAND_QUEUE = "ai.commands"
EVENT_EXCHANGE = "ai.events"

def build_event(event_type, payload, correlation_id):
    return {
        "version": "1.0",
        "event_id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }

def process_command(channel, command):
    print("Received command:")
    print(json.dumps(command, indent=2))

    correlation_id = command["correlation_id"]
    command_type = command["type"]
    payload = command["payload"]

    print(
        f"Processing type={command_type} "
        f"correlation_id={correlation_id}"
    )

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
    )

    result = graph.invoke(
        {
            "messages": graph_messages,
            "order_number": "",
        },
        config={
            "recursion_limit": 8,
        },
    )

    assistant_message = result["messages"][-1]

    response_content = assistant_message.content

    if not isinstance(response_content, str):
        response_content = str(response_content)

    event = build_event(
        "chat.response.generated",
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "content": response_content,
        },
        correlation_id=correlation_id,
    )

    routing_key = f"conversation.{conversation_id}"

    channel.basic_publish(
        exchange=EVENT_EXCHANGE,
        routing_key=routing_key,
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    print("Published event:")
    print(json.dumps(event, indent=2))



def on_command(channel, method, properties, body):
    try:
        command = json.loads(body)

        process_command(channel, command)

        channel.basic_ack(
            delivery_tag=method.delivery_tag,
        )

    except Exception as exc:
        print(f"Command processing failed: {exc}")

        channel.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )


def main():
    credentials = pika.PlainCredentials(
        RABBITMQ_USER,
        RABBITMQ_PASSWORD,
    )

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
        )
    )

    channel = connection.channel()

    channel.queue_declare(
        queue=COMMAND_QUEUE,
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

    print("AI worker connected to RabbitMQ.")
    print(f"Waiting for commands on '{COMMAND_QUEUE}'...")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Worker stopped.")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()