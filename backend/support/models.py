from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_number

class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation {self.id}"


class Message(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "conversation",
                    "correlation_id",
                    "role",
                ],
                name="unique_message_correlation_role",
            ),
        ]
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    correlation_id = models.UUIDField(
    null=True,
    blank=True,
    db_index=True,
    )
    
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:40]}" 


class Document(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    indexed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    correlation_id = models.UUIDField(null=True,blank=True,unique=True,)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject


class ConversationCost(models.Model):

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="costs",
    )

    correlation_id = models.UUIDField(
        null=True,
        blank=True,
    )

    input_tokens = models.IntegerField(
        default=0,
    )

    output_tokens = models.IntegerField(
        default=0,
    )

    total_tokens = models.IntegerField(
        default=0,
    )

    llm_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
    )

    web_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
    )

    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"Cost for conversation {self.conversation_id}"



