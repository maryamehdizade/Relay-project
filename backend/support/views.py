from django.shortcuts import render, get_object_or_404
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
)
from rest_framework.permissions import IsAuthenticated

from .models import Order, Conversation, Message
from .serializers import (OrderSerializer, ConversationSerializer, MessageSerializer)
from .messaging import build_message, publish_command

import uuid


class OrderListView(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

class OrderDetailView(RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "order_number"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

class ConversationListCreateView(ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(
            user=self.request.user
        ).order_by("-updated_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class MessageListCreateView(ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_conversation(self):
        return get_object_or_404(
            Conversation,
            id=self.kwargs["conversation_id"],
            user=self.request.user,
        )

    def get_queryset(self):
        conversation = self.get_conversation()

        return Message.objects.filter(
            conversation=conversation
        ).order_by("created_at")

    def perform_create(self, serializer):
        conversation = self.get_conversation()
        correlation_id = uuid.uuid4()
        
        message = serializer.save(
            conversation=conversation,
            role=Message.Role.USER,
            correlation_id=correlation_id,
        )

        conversation.save()

        command = build_message(
            message_type="chat.generate_response",
            correlation_id=str(correlation_id),
            payload={
                "message_id": message.id,
                "conversation_id": conversation.id,
                "user_id": self.request.user.id,
            },
        )

        publish_command(command)