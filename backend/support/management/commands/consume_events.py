import json
import os

import pika

from django.core.management.base import BaseCommand
from django.db import transaction

from support.models import Conversation, Message


EVENT_EXCHANGE = "ai.events"
EVENT_QUEUE = "ai.events.persistence"


class Command(BaseCommand):
    help = "Consume AI events from RabbitMQ"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one event and exit.",
        )

    def handle(self, *args, **options):
        once = options["once"]

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

        channel.exchange_declare( 
            exchange=EVENT_EXCHANGE,
            exchange_type="fanout",
            durable=True,
        )


        channel.queue_declare(
            queue=EVENT_QUEUE,
            durable=True,
        )

        channel.queue_bind(
            exchange=EVENT_EXCHANGE,
            queue=EVENT_QUEUE,
            )

        channel.basic_qos(prefetch_count=1)

        def on_event(channel, method, properties, body):
            try:
                event = json.loads(body)

                self.stdout.write("Received event:")
                self.stdout.write(
                    json.dumps(event, indent=2)
                )

                event_type = event.get("type")

                if event_type == "chat.response.generated":
                    payload = event["payload"]

                    with transaction.atomic():
                        conversation = Conversation.objects.get(
                            id=payload["conversation_id"],
                            user_id=payload["user_id"],
                        )

                        Message.objects.create(
                            conversation=conversation,
                            correlation_id=event["correlation_id"],
                            role=Message.Role.ASSISTANT,
                            content=payload["content"],
                        )

                        conversation.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            "Assistant message saved."
                        )
                    )

                else:
                    self.stdout.write(
                        f"Ignoring unknown event type: {event_type}"
                    )

                channel.basic_ack(
                    delivery_tag=method.delivery_tag
                )

            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"Event processing failed: {exc}"
                    )
                )

                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True,
                )

            finally:
                if once:
                    channel.stop_consuming()

        channel.basic_consume(
            queue=EVENT_QUEUE,
            on_message_callback=on_event,
            auto_ack=False,
        )

        self.stdout.write(
            f"Waiting for events on '{EVENT_QUEUE}'..."
        )

        try:
            channel.start_consuming()
        finally:
            if connection.is_open:
                connection.close()
