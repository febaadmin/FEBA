from rest_framework import serializers
from .models import Subject


class SubjectSerializer(serializers.ModelSerializer):
    level_name = serializers.SerializerMethodField()
    language_display = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'school', 'level', 'level_name', 'name', 'code',
                  'coefficient', 'language', 'language_display', 'order']

    def get_level_name(self, obj):
        return obj.level.name if obj.level else None

    def get_language_display(self, obj):
        return obj.get_language_display()

    def validate(self, attrs):
        # FIX v44 : empêche la création de matières en double (même nom + même
        # langue dans un établissement), à l'origine des doublons « test / test »
        # dans le sélecteur de note. La modification d'une matière existante
        # reste permise.
        name = attrs.get("name") or getattr(self.instance, "name", None)
        language = attrs.get("language") or getattr(self.instance, "language", None)
        school = attrs.get("school") or getattr(self.instance, "school", None)
        if school is None:
            request = self.context.get("request")
            if request is not None:
                from apps.core.tenancy import get_request_school
                school = get_request_school(request)
        if name and school is not None:
            dup = Subject.objects.filter(school=school, name__iexact=name, language=language)
            if self.instance:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise serializers.ValidationError({
                    "name": f"Une matière « {name} » ({language}) existe déjà dans cet établissement.",
                })
        return attrs
