from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from .models import Announcement
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class AnnouncementSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "school_year.school"

    author = UserSerializer(read_only=True)
    has_attachment = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = "__all__"

    def get_has_attachment(self, obj):
        return bool(obj.attachment)