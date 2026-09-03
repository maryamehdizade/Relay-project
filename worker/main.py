import os
import time

import pika


rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
rabbitmq_user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
rabbitmq_password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")


credentials = pika.PlainCredentials(
    rabbitmq_user,
    rabbitmq_password,
)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        credentials=credentials,
    )
)

print("AI worker connected to RabbitMQ successfully.")

try:
    while True:
        connection.process_data_events(time_limit=1)
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    if connection.is_open:
        connection.close()
