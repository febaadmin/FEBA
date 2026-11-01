from rest_framework import serializers
from apps.core.textes import sans_tiret
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for champ in ("title", "message"):
            data[champ] = sans_tiret(data.get(champ))
        return data
