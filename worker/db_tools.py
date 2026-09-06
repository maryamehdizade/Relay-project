import os

import psycopg
from psycopg.rows import dict_row


def get_database_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "relay"),
        user=os.getenv("POSTGRES_USER", "relay"),
        password=os.getenv("POSTGRES_PASSWORD"),
        row_factory=dict_row,
    )


def get_order_status(user_id: int, order_number: str) -> dict:
    order_number = order_number.strip().upper()

    if not order_number:
        return {
            "found": False,
            "error": "Order number is required.",
        }

    if len(order_number) > 50:
        return {
            "found": False,
            "error": "Invalid order number.",
        }

    query = """
        SELECT
            order_number,
            status,
            tracking_number,
            created_at
        FROM support_order
        WHERE user_id = %s
          AND order_number = %s
        LIMIT 1
    """

    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (user_id, order_number),
            )

            order = cursor.fetchone()

    if order is None:
        return {
            "found": False,
            "order_number": order_number,
        }

    return {
        "found": True,
        "order_number": order["order_number"],
        "status": order["status"],
        "tracking_number": order["tracking_number"],
        "created_at": order["created_at"].isoformat(),
    }
