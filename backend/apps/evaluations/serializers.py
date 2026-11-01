from rest_framework import serializers

from .correction import valider_question
from .models import Amenagement, Epreuve, EpreuveQuestion, Question, Tentative


class QuestionSerializer(serializers.ModelSerializer):
    """Réservé au personnel : contient le corrigé."""

    enonce = serializers.CharField(write_only=True)
    contenu = serializers.JSONField(write_only=True, required=False, default=dict)
    corrige = serializers.JSONField(write_only=True, required=False, default=dict)
    criteres = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    explication = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    points = serializers.DecimalField(write_only=True, required=False, max_digits=6, decimal_places=2, min_value=0, default=1)
    media = serializers.FileField(write_only=True, required=False, allow_null=True)
    media_type = serializers.ChoiceField(write_only=True, required=False, choices=["", "image", "document", "audio", "video"], default="")
    version = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)

    class Meta:
        model = Question
        fields = ["id", "type", "subject", "subject_name", "level", "difficulte", "prive", "archive", "competences",
                  "created_at", "version", "enonce", "contenu", "corrige", "criteres", "explication", "points", "media", "media_type"]
        read_only_fields = ["id", "archive", "created_at"]

    def get_version(self, obj):
        v = obj.version_courante
        if v is None:
            return None
        return {"id": v.pk, "numero": v.numero, "enonce": v.enonce, "contenu": v.contenu, "corrige": v.corrige,
                "criteres": v.criteres, "explication": v.explication, "points": str(v.points),
                "media": v.media.url if v.media else None, "media_type": v.media_type}

    def validate(self, attrs):
        school = self.context["school"]
        for champ in ("subject", "level"):
            if attrs.get(champ) and attrs[champ].school_id != school.pk:
                raise serializers.ValidationError({champ: "Hors de votre académie."})
        for competence in attrs.get("competences", []):
            if competence.referentiel.school_id != school.pk:
                raise serializers.ValidationError({"competences": "Hors de votre académie."})
        type_question = attrs.get("type", getattr(self.instance, "type", None))
        if self.instance is None or {"contenu", "corrige"} & set(self.initial_data):
            for nom in ("contenu", "corrige"):
                if not isinstance(attrs.get(nom, {}), dict):
                    raise serializers.ValidationError({nom: "Objet attendu."})
            erreurs = valider_question(type_question, attrs.get("contenu", {}), attrs.get("corrige", {}))
            if erreurs:
                raise serializers.ValidationError({"corrige": erreurs})
        return attrs


class EpreuveQuestionSerializer(serializers.ModelSerializer):
    enonce = serializers.CharField(source="version.enonce", read_only=True)
    type = serializers.CharField(source="version.question.type", read_only=True)
    numero_version = serializers.IntegerField(source="version.numero", read_only=True)

    class Meta:
        model = EpreuveQuestion
        fields = ["id", "version", "ordre", "points", "enonce", "type", "numero_version"]


class EpreuveSerializer(serializers.ModelSerializer):
    questions = EpreuveQuestionSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_name = serializers.CharField(source="class_obj.name", read_only=True)

    class Meta:
        model = Epreuve
        fields = ["id", "titre", "description", "consignes", "type", "subject", "subject_name", "class_obj", "class_name",
                  "eleves_cibles", "school_year", "periode", "ouverture", "fermeture", "duree_minutes", "tentatives_max",
                  "note_max", "seuil_reussite", "politique", "melanger_questions", "melanger_reponses", "retour_autorise",
                  "reprise_autorisee", "produit_note", "note_type", "regles_tirage", "statut", "resultats_publies",
                  "questions", "created_at"]
        read_only_fields = ["id", "statut", "resultats_publies", "created_at"]
        extra_kwargs = {"school_year": {"required": False}, "politique": {"required": False}}

    def validate(self, attrs):
        school = self.context["school"]
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        classe = attrs.get("class_obj", getattr(self.instance, "class_obj", None))
        if subject and subject.school_id != school.pk:
            raise serializers.ValidationError({"subject": "Hors de votre académie."})
        if classe and classe.school_year.school_id != school.pk:
            raise serializers.ValidationError({"class_obj": "Hors de votre académie."})
        ouverture = attrs.get("ouverture", getattr(self.instance, "ouverture", None))
        fermeture = attrs.get("fermeture", getattr(self.instance, "fermeture", None))
        if ouverture and fermeture and fermeture <= ouverture:
            raise serializers.ValidationError({"fermeture": "La fermeture doit suivre l'ouverture."})
        for eleve in attrs.get("eleves_cibles", []):
            if eleve.school_id != school.pk or (classe and eleve.current_class_id != classe.pk):
                raise serializers.ValidationError({"eleves_cibles": "Élève hors de cette classe."})
        if classe and "school_year" not in attrs and self.instance is None:
            attrs["school_year"] = classe.school_year
        if "politique" not in attrs and self.instance is None:
            attrs["politique"] = "derniere" if attrs.get("type") == "examen" else "meilleure"
        return attrs


class AmenagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenagement
        fields = ["id", "student", "minutes_sup", "tentatives_sup"]


class CopieSerializer(serializers.ModelSerializer):
    eleve = serializers.CharField(source="student.get_full_name", read_only=True)
    a_transfert = serializers.SerializerMethodField()

    class Meta:
        model = Tentative
        fields = ["id", "student", "eleve", "numero", "debut", "echeance", "remise_le", "mode_remise", "statut",
                  "total_points", "score_brut", "score_corrige", "score_valide", "pourcentage", "note_echelle",
                  "reussie", "choisie", "a_transfert"]

    def get_a_transfert(self, obj):
        return obj.transferts.exists()
