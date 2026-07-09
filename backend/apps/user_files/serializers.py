from rest_framework import serializers
from .models import UserFile


class UserFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploader_name = serializers.CharField(source="user.get_full_name", read_only=True)
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = UserFile
        fields = [
            "id", "user", "uploader_name", "name", "description",
            "file", "file_url", "file_size", "file_size_display",
            "mime_type", "original_filename", "uploaded_at", "updated_at",
        ]
        read_only_fields = ["user", "file_size", "mime_type", "original_filename"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return obj.file.url
        return None

    def get_file_size_display(self, obj):
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
