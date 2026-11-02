from rest_framework import serializers


from .models import (
    ActionPedagogique,
    AlertePedagogique,
    Competence,
    EvaluationCompetence,
    EvaluationPedagogique,
    NiveauMaitrise,
    Objectif,
    ObjectifHistorique,
    ObservationParticipation,
    ParametresSuivi,
    PlanAccompagnement,
    RapportPedagogique,
    RapportVersion,
    Referentiel,
    RegleAlerte,
)


class NiveauSerializer(serializers.ModelSerializer):
    class Meta:
        model = NiveauMaitrise
        fields = ["id", "code", "libelle", "libelle_en", "rang", "couleur"]
        read_only_fields = ["id", "code", "rang"]


class ReferentielSerializer(serializers.ModelSerializer):
    nombre_competences = serializers.IntegerField(source="competences.count", read_only=True)

    class Meta:
        model = Referentiel
        fields = ["id", "nom", "description", "subject", "level", "programme", "actif", "nombre_competences", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        school = self.context["school"]
        for champ in ("subject", "level"):
            if attrs.get(champ) and attrs[champ].school_id != school.pk:
                raise serializers.ValidationError({champ: "Hors de votre académie."})
        return attrs


class CompetenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competence
        fields = ["id", "referentiel", "domaine", "code", "nom", "nom_en", "description", "criteres", "subject", "ordre", "actif"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        school = self.context["school"]
        referentiel = attrs.get("referentiel") or getattr(self.instance, "referentiel", None)
        if referentiel and referentiel.school_id != school.pk:
            raise serializers.ValidationError({"referentiel": "Hors de votre académie."})
        if attrs.get("subject") and attrs["subject"].school_id != school.pk:
            raise serializers.ValidationError({"subject": "Hors de votre académie."})
        return attrs


class EvaluationCompetenceSerializer(serializers.ModelSerializer):
    competence_nom = serializers.CharField(source="competence.nom", read_only=True)
    niveau_libelle = serializers.CharField(source="niveau.libelle", read_only=True)
    niveau_rang = serializers.IntegerField(source="niveau.rang", read_only=True)
    evalue_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationCompetence
        fields = ["id", "student", "competence", "competence_nom", "niveau", "niveau_libelle", "niveau_rang",
                  "date_evaluation", "commentaire", "preuve", "source", "reference_source", "statut",
                  "evalue_par_nom", "decide_le", "created_at"]
        read_only_fields = ["id", "source", "reference_source", "statut", "decide_le", "created_at"]

    def get_evalue_par_nom(self, obj):
        return obj.evalue_par.get_full_name() if obj.evalue_par else None

    def validate(self, attrs):
        school = self.context["school"]
        if attrs["student"].school_id != school.pk:
            raise serializers.ValidationError({"student": "Hors de votre académie."})
        if attrs["competence"].referentiel.school_id != school.pk or not attrs["competence"].actif:
            raise serializers.ValidationError({"competence": "Compétence indisponible."})
        if attrs["niveau"].school_id != school.pk:
            raise serializers.ValidationError({"niveau": "Hors de votre académie."})
        return attrs


class _AvecEleve(serializers.ModelSerializer):
    def _controler(self, attrs):
        school = self.context["school"]
        student = attrs.get("student") or getattr(self.instance, "student", None)
        if student and student.school_id != school.pk:
            raise serializers.ValidationError({"student": "Hors de votre académie."})
        subject = attrs.get("subject")
        if subject and subject.school_id != school.pk:
            raise serializers.ValidationError({"subject": "Hors de votre académie."})
        return attrs

    def validate(self, attrs):
        return self._controler(attrs)


class EvaluationPedagogiqueSerializer(_AvecEleve):
    class Meta:
        model = EvaluationPedagogique
        fields = ["id", "student", "subject", "titre", "type", "score_pourcent", "date_evaluation", "commentaire", "created_at"]
        read_only_fields = ["id", "created_at"]


class ObservationSerializer(_AvecEleve):
    class Meta:
        model = ObservationParticipation
        fields = ["id", "student", "subject", "niveau", "date_observation", "note", "created_at"]
        read_only_fields = ["id", "created_at"]


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionPedagogique
        fields = ["id", "objectif", "plan", "type", "description", "echeance", "realisee_le", "resultat", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        objectif = attrs.get("objectif", getattr(self.instance, "objectif", None))
        plan = attrs.get("plan", getattr(self.instance, "plan", None))
        if bool(objectif) == bool(plan):
            raise serializers.ValidationError("Une action se rattache à un objectif ou à un plan.")
        return attrs


class HistoriqueObjectifSerializer(serializers.ModelSerializer):
    par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ObjectifHistorique
        fields = ["ancien_statut", "nouveau_statut", "note", "par_nom", "created_at"]

    def get_par_nom(self, obj):
        return obj.par.get_full_name() if obj.par else None


class ObjectifSerializer(_AvecEleve):
    actions = ActionSerializer(many=True, read_only=True)
    historique = HistoriqueObjectifSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    competence_nom = serializers.CharField(source="competence.nom", read_only=True, default=None)

    class Meta:
        model = Objectif
        fields = ["id", "student", "class_obj", "subject", "subject_name", "competence", "competence_nom", "titre",
                  "description", "criteres_reussite", "date_cible", "priorite", "statut", "responsable",
                  "actions", "historique", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        attrs = self._controler(attrs)
        student = attrs.get("student", getattr(self.instance, "student", None))
        classe = attrs.get("class_obj", getattr(self.instance, "class_obj", None))
        if bool(student) == bool(classe):
            raise serializers.ValidationError("Un objectif vise un élève ou une classe.")
        school = self.context["school"]
        if classe and classe.school_year.school_id != school.pk:
            raise serializers.ValidationError({"class_obj": "Hors de votre académie."})
        competence = attrs.get("competence")
        if competence and competence.referentiel.school_id != school.pk:
            raise serializers.ValidationError({"competence": "Hors de votre académie."})
        responsable = attrs.get("responsable")
        if responsable and responsable.school_id != school.pk:
            raise serializers.ValidationError({"responsable": "Hors de votre académie."})
        return attrs


class PlanSerializer(_AvecEleve):
    actions = ActionSerializer(many=True, read_only=True)

    class Meta:
        model = PlanAccompagnement
        fields = ["id", "student", "titre", "motif", "statut", "debut", "fin", "partage_famille", "responsable", "actions", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        attrs = self._controler(attrs)
        responsable = attrs.get("responsable")
        if responsable and responsable.school_id != self.context["school"].pk:
            raise serializers.ValidationError({"responsable": "Hors de votre académie."})
        return attrs


class ParametresSerializer(serializers.ModelSerializer):
    poids_effectifs = serializers.SerializerMethodField()

    class Meta:
        model = ParametresSuivi
        fields = ["poids", "poids_effectifs", "min_notes_comparaison", "min_observations", "updated_at"]
        read_only_fields = ["updated_at"]

    def get_poids_effectifs(self, obj):
        return obj.poids_effectifs()

    def validate_poids(self, value):
        if not isinstance(value, dict) or set(value) - set(ParametresSuivi.POIDS_DEFAUT):
            raise serializers.ValidationError("Composante inconnue.")
        for poids in value.values():
            if isinstance(poids, bool) or not isinstance(poids, int) or not 0 <= poids <= 100:
                raise serializers.ValidationError("Un poids est un entier de 0 à 100.")
        return value


class RapportVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapportVersion
        fields = ["numero", "statut", "contenu", "created_at"]


class RapportSerializer(serializers.ModelSerializer):
    versions = RapportVersionSerializer(many=True, read_only=True)

    class Meta:
        model = RapportPedagogique
        fields = ["id", "student", "type", "du", "au", "statut", "numero_version", "donnees", "contenu", "versions", "created_at", "updated_at"]


class AlerteSerializer(serializers.ModelSerializer):
    eleve = serializers.CharField(source="student.get_full_name", read_only=True)

    class Meta:
        model = AlertePedagogique
        fields = ["id", "student", "eleve", "code", "categorie", "message", "donnees", "recommandation", "statut", "note_decision", "decide_le", "created_at"]


class RegleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegleAlerte
        fields = ["code", "seuil", "actif"]
        read_only_fields = ["code"]

    def validate_seuil(self, value):
        if value < 1:
            raise serializers.ValidationError("Valeur minimale : 1.")
        return value
