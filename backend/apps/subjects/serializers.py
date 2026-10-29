from apps.core.tenancy import TenantRelationsMixin
from rest_framework import serializers
from .models import Subject
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class SubjectSerializer(TenantRelationsMixin, AcademyMetadataMixin, serializers.ModelSerializer):
    #: Isolation des relations écrites (voir apps.core.tenancy.TenantRelationsMixin).
    tenant_relations = {"level": "school", "school": ""}
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    level_name = serializers.SerializerMethodField()
    language_display = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'school', 'level', 'level_name', 'name', 'code',
                  'coefficient', 'language', 'language_display', 'order'] + ACADEMY_FIELDS

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
        # Programme linguistique de l'académie : vérifié ICI, côté serveur,
        # pour tout chemin d'écriture (écran, import, requête manuelle).
        from apps.classes.subject_rules import allowed_languages, subject_language_error

        refus = subject_language_error(school, language)
        if refus:
            raise serializers.ValidationError({"language": refus})
        # Changer la langue d'une matière déjà portée par des classes dont
        # le parcours ne l'admet pas casserait ces classes (et leurs
        # bulletins) sans que rien ne le signale.
        if self.instance is not None and "language" in attrs \
                and attrs["language"] != self.instance.language:
            bloquantes = sorted(c.name for c in self.instance.classes.all()
                                if attrs["language"] not in allowed_languages(c))
            if bloquantes:
                raise serializers.ValidationError({"language": (
                    "Cette matière est enseignée dans des classes dont le parcours "
                    "n'admet pas cette langue : " + ", ".join(bloquantes) + ". Retirez-la "
                    "d'abord de ces classes.")})
        if name and school is not None:
            dup = Subject.objects.filter(school=school, name__iexact=name, language=language)
            if self.instance:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise serializers.ValidationError({
                    "name": f"Une matière « {name} » ({language}) existe déjà dans cet établissement.",
                })
        return attrs
