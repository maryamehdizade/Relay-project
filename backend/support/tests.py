from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Conversation, Message, Order


User = get_user_model()


class AuthorizationTests(APITestCase):
    def setUp(self):
        self.customer1 = User.objects.create_user(
            username="customer1",
            password="TestPass123!",
        )
        self.customer2 = User.objects.create_user(
            username="customer2",
            password="TestPass123!",
        )

        self.token1 = Token.objects.create(user=self.customer1)
        self.token2 = Token.objects.create(user=self.customer2)

        self.order1 = Order.objects.create(
            user=self.customer1,
            order_number="ORD-1001",
            status=Order.Status.SHIPPED,
        )

        self.order2 = Order.objects.create(
            user=self.customer2,
            order_number="ORD-2001",
            status=Order.Status.DELIVERED,
        )

        self.conversation1 = Conversation.objects.create(
            user=self.customer1,
            title="Customer 1 conversation",
        )

    def authenticate_as_customer1(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.token1.key}"
        )

    def authenticate_as_customer2(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.token2.key}"
        )

    def test_unauthenticated_user_cannot_list_orders(self):
        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 401)

    def test_user_only_sees_own_orders(self):
        self.authenticate_as_customer1()

        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["order_number"],
            "ORD-1001",
        )

    def test_user_cannot_access_another_users_order(self):
        self.authenticate_as_customer1()

        response = self.client.get("/api/orders/ORD-2001/")

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_read_another_users_conversation(self):
        self.authenticate_as_customer2()

        response = self.client.get(
            f"/api/conversations/{self.conversation1.id}/messages/"
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_post_to_another_users_conversation(self):
        self.authenticate_as_customer2()

        response = self.client.post(
            f"/api/conversations/{self.conversation1.id}/messages/",
            {"content": "Unauthorized message"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_created_message_role_is_forced_to_user(self):
        self.authenticate_as_customer1()

        response = self.client.post(
            f"/api/conversations/{self.conversation1.id}/messages/",
            {
                "content": "Hello",
                "role": "assistant",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], Message.Role.USER)