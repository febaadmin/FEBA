from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, MessageViewSet

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("", MessageViewSet, basename="message")

urlpatterns = router.urls + [
    # Frontend calls /messages/unread-count/ (hyphen); router generates unread_count/ (underscore)
    path("unread-count/", MessageViewSet.as_view({"get": "unread_count"}), name="message-unread-count"),
    # Explicit path to ensure inbox is accessible
    path("inbox/",  MessageViewSet.as_view({"get": "inbox"}),  name="message-inbox"),
    path("sent/",   MessageViewSet.as_view({"get": "sent"}),   name="message-sent"),
]
