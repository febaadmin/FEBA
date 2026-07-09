from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    has_attachment = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = "__all__"

    def get_has_attachment(self, obj):
        return bool(obj.attachment)