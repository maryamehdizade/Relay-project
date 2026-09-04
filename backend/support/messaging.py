import json
import os
import uuid
from datetime import datetime, timezone

import pika


def build_message(message_type, payload, correlation_id=None):
    return {
        "version": "1.0",
        "event_id": str(uuid.uuid4()),
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def publish_command(message):
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
        os.getenv("RABBITMQ_DEFAULT_PASS", "guest"),
    )

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            credentials=credentials,
        )
    )

    channel = connection.channel()

    channel.queue_declare(
        queue="ai.commands",
        durable=True,
    )

    channel.basic_publish(
        exchange="",
        routing_key="ai.commands",
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    connection.close()

