import json
import os

import aio_pika
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.authtoken.models import Token


EVENT_EXCHANGE = "ai.events"


async def get_user_from_request(request):
    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith("Token "):
        return None

    token_key = authorization.removeprefix("Token ").strip()

    if not token_key:
        return None

    try:
        token = await Token.objects.select_related("user").aget(
            key=token_key
        )
    except Token.DoesNotExist:
        return None

    return token.user


async def event_stream(request):
    user = await get_user_from_request(request)

    if user is None:
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )

    async def stream():
        connection = None

        try:
            rabbitmq_user = os.getenv(
                "RABBITMQ_DEFAULT_USER",
                "guest",
            )
            rabbitmq_password = os.getenv(
                "RABBITMQ_DEFAULT_PASS",
                "guest",
            )
            rabbitmq_host = os.getenv(
                "RABBITMQ_HOST",
                "rabbitmq",
            )
            rabbitmq_port = int(
                os.getenv("RABBITMQ_PORT", "5672")
            )

            connection = await aio_pika.connect_robust(
                host=rabbitmq_host,
                port=rabbitmq_port,
                login=rabbitmq_user,
                password=rabbitmq_password,
            )

            channel = await connection.channel()

            exchange = await channel.declare_exchange(
                EVENT_EXCHANGE,
                aio_pika.ExchangeType.FANOUT,
                durable=True,
            )

            queue = await channel.declare_queue(
                name="",
                exclusive=True,
                auto_delete=True,
            )

            await queue.bind(exchange)

            yield "event: connected\ndata: {}\n\n"

            async with queue.iterator() as queue_iterator:
                async for message in queue_iterator:
                    async with message.process():
                        event = json.loads(message.body)

                        payload = event.get("payload", {})

                        if payload.get("user_id") != user.id:
                            continue

                        yield (
                            "event: message\n"
                            f"data: {json.dumps(event)}\n\n"
                        )

        finally:
            if connection is not None:
                await connection.close()

    response = StreamingHttpResponse(
        stream(),
        content_type="text/event-stream",
    )

    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"

    return response
