from rest_framework import serializers

from .models import Order, Conversation, Message


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "tracking_number",
            "created_at",
        ]

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "correlation_id",
            "role",
            "content",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "correlation_id",
            "role",
            "created_at",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "created_at",
            "updated_at",
            "messages",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "messages",
        ]