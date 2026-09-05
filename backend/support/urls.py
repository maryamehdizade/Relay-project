from django.urls import path
from .sse import event_stream

from .views import (
    ConversationListCreateView,
    OrderDetailView,
    OrderListView,
    MessageListCreateView,
)


urlpatterns = [
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/<str:order_number>/", OrderDetailView.as_view(),name="order-detail"),

    path("conversations/", ConversationListCreateView.as_view(), 
         name="conversation-list-create" ),

    path("conversations/<int:conversation_id>/messages/", MessageListCreateView.as_view(), 
         name="message-list-create"),

    path("conversations/<int:conversation_id>/events/stream/",event_stream,name="event-stream",),


    
]
