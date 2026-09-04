import json
import os

import pika


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")

COMMAND_QUEUE = "ai.commands"


def process_command(command):
    print("Received command:")
    print(json.dumps(command, indent=2))

    print(
        "Processing:",
        command.get("type"),
        "correlation_id=",
        command.get("correlation_id"),
    )

    # Dummy processing for now.
    print("Command processed successfully.")


def on_command(channel, method, properties, body):
    try:
        command = json.loads(body)

        process_command(command)

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