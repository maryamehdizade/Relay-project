import json
import os

import pika

from django.core.management.base import BaseCommand
from django.db import transaction

from support.models import Conversation, Message, Document


EVENT_EXCHANGE = "ai.events"
EVENT_QUEUE = "ai.events.persistence"

EVENT_DEAD_LETTER_QUEUE = "ai.events.persistence.dead"

EVENT_RETRY_QUEUES = [
    ("ai.events.persistence.retry.5s", 5_000),
    ("ai.events.persistence.retry.10s", 10_000),
    ("ai.events.persistence.retry.20s", 20_000),
]

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
            os.getenv(
                "RABBITMQ_DEFAULT_USER",
                "guest",
            ),
            os.getenv(
                "RABBITMQ_DEFAULT_PASS",
                "guest",
            ),
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
            )
        )

        channel = connection.channel()

        channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )

        channel.queue_declare(
            queue=EVENT_QUEUE,
            durable=True,
        )

        for retry_queue, delay_ms in EVENT_RETRY_QUEUES:
            channel.queue_declare(
        queue=retry_queue,
        durable=True,
        arguments={
            "x-message-ttl": delay_ms,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": EVENT_QUEUE,
        },
    )
        
        channel.queue_declare(
            queue=EVENT_DEAD_LETTER_QUEUE,
            durable=True,
        )


        channel.queue_bind(
            exchange=EVENT_EXCHANGE,
            queue=EVENT_QUEUE,
            routing_key="conversation.*",
        )

        channel.queue_bind(
            exchange=EVENT_EXCHANGE,
            queue=EVENT_QUEUE,
            routing_key="document.*",
        )

        channel.basic_qos(
            prefetch_count=1
        )
        def retry_or_dead_letter_event(
            channel,
            method,
            properties,
            body,
        ):
            headers = dict(
                properties.headers or {}
            )
        
            retry_count = int(
                headers.get(
                    "x-event-retry-count",
                    0,
                )
            )
        
            if retry_count < len(
                EVENT_RETRY_QUEUES
            ):
                retry_queue, delay_ms = (
                    EVENT_RETRY_QUEUES[
                        retry_count
                    ]
                )
        
                headers[
                    "x-event-retry-count"
                ] = retry_count + 1
        
                channel.basic_publish(
                    exchange="",
                    routing_key=retry_queue,
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        headers=headers,
                    ),
                )
        
                self.stdout.write(
                    self.style.WARNING(
                        "Event failed. "
                        f"Retry {retry_count + 1}/"
                        f"{len(EVENT_RETRY_QUEUES)} "
                        f"scheduled in "
                        f"{delay_ms // 1000}s."
                    )
                )
        
            else:
                channel.basic_publish(
                    exchange="",
                    routing_key=(
                        EVENT_DEAD_LETTER_QUEUE
                    ),
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        headers=headers,
                    ),
                )
        
                self.stderr.write(
                    self.style.ERROR(
                        "Event exhausted retries. "
                        f"Moved to "
                        f"'{EVENT_DEAD_LETTER_QUEUE}'."
                    )
                )
        
            channel.basic_ack(
                delivery_tag=(
                    method.delivery_tag
                )
            )
        def on_event(
            channel,
            method,
            properties,
            body,
        ):
            try:
                event = json.loads(body)

                self.stdout.write(
                    "Received event:"
                )

                self.stdout.write(
                    json.dumps(
                        event,
                        indent=2,
                    )
                )

                event_type = event.get("type")

                
                # Chat response event
                
                if (
                    event_type
                    == "chat.response.generated"
                ):
                    payload = event["payload"]

                    with transaction.atomic():
                        conversation = (
                            Conversation.objects.get(
                                id=payload[
                                    "conversation_id"
                                ],
                                user_id=payload[
                                    "user_id"
                                ],
                            )
                        )

                        message, created = (
                            Message.objects.get_or_create(
                                conversation=conversation,
                                correlation_id=event[
                                    "correlation_id"
                                ],
                                role=(
                                    Message.Role.ASSISTANT
                                ),
                                defaults={
                                    "content": payload[
                                        "content"
                                    ],
                                },
                            )
                        )

                        if created:
                            conversation.save()

                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "Assistant message saved."
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                "Duplicate assistant "
                                "event ignored for "
                                "correlation_id="
                                f"{event['correlation_id']}"
                            )
                        )

                
                # Document indexed event
                
                elif (
                    event_type
                    == "documents.indexed"
                ):
                    payload = event["payload"]

                    updated = (
                        Document.objects.filter(
                            id=payload[
                                "document_id"
                            ],
                            user_id=payload[
                                "user_id"
                            ],
                        ).update(
                            indexed=True
                        )
                    )

                    if updated == 0:
                        raise ValueError(
                            "Document could not be "
                            "found for the user."
                        )

                    self.stdout.write(
                        self.style.SUCCESS(
                            "Document marked as "
                            "indexed: "
                            f"{payload['document_id']}"
                        )
                    )

            
                # Unknown event
                
                else:
                    self.stdout.write(
                        f"Ignoring unknown event "
                        f"type: {event_type}"
                    )

                # ACK only after successful handling
                channel.basic_ack(
                    delivery_tag=(
                        method.delivery_tag
                    )
                )

            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        "Event processing failed: "
                        f"{exc}"
                    )
                )

                retry_or_dead_letter_event(
                    channel=channel,
                    method=method,
                    properties=properties,
                    body=body,
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
            f"Waiting for events on "
            f"'{EVENT_QUEUE}'..."
        )

        try:
            channel.start_consuming()

        finally:
            if connection.is_open:
                connection.close()