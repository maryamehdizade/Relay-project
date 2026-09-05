import json
import os
import uuid
from datetime import datetime, timezone
import pika


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

    print(
        "Processing:",
        command.get("type"),
        "correlation_id=",
        command.get("correlation_id"),
    )

    payload = command["payload"]

    event = build_event(
        event_type="chat.response.generated",
        correlation_id=command["correlation_id"],
        payload={
            "conversation_id": payload["conversation_id"],
            "user_id": payload["user_id"],
            "content": "Hello from the AI worker.",
        },
    )

    routing_key = f"conversation.{payload['conversation_id']}" 

    channel.basic_publish(
        exchange= EVENT_EXCHANGE,
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