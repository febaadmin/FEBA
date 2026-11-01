"""
FEBA - Suivi pédagogique : un système distinct des notes et des bulletins.

Ces tables n'écrivent jamais dans apps.grades. Une ancienne note reste une note :
elle s'affiche à côté du suivi, avec sa provenance, et n'est jamais convertie
en évaluation pédagogique (voir services.resultats_historiques).
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

NIVEAUX_PAR_DEFAUT = [
    ("a_travailler", "À travailler", "To work on", 1, "#b91c1c"),
    ("a_renforcer", "À renforcer", "To strengthen", 2, "#b45309"),
    ("en_progression", "En progression", "In progress", 3, "#1d4ed8"),
    ("acquis", "Acquis", "Acquired", 4, "#15803d"),
]


class NiveauMaitrise(models.Model):
    """Niveaux de maîtrise d'une académie : libellés modifiables, rang stable."""

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="niveaux_maitrise")
    code = models.SlugField(max_length=30)
    libelle = models.CharField(max_length=60)
    libelle_en = models.CharField(max_length=60, blank=True)
    rang = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    couleur = models.CharField(max_length=7, default="#475569")

    class Meta:
        ordering = ["rang"]
        constraints = [
            models.UniqueConstraint(fields=["school", "code"], name="uniq_niveau_code"),
            models.UniqueConstraint(fields=["school", "rang"], name="uniq_niveau_rang"),
        ]

    def __str__(self):
        return self.libelle


class Referentiel(models.Model):
    """Référentiel de compétences, rattachable à une matière, un niveau ou un programme."""

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="referentiels")
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    level = models.ForeignKey("schools.Level", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    programme = models.CharField(max_length=150, blank=True)
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        constraints = [models.UniqueConstraint(fields=["school", "nom"], name="uniq_referentiel_nom")]

    def __str__(self):
        return self.nom


class Competence(models.Model):
    referentiel = models.ForeignKey(Referentiel, on_delete=models.CASCADE, related_name="competences")
    domaine = models.CharField(max_length=120, blank=True)
    code = models.CharField(max_length=30, blank=True)
    nom = models.CharField(max_length=200)
    nom_en = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    criteres = models.TextField(blank=True, help_text="Critères de maîtrise.")
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    ordre = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["referentiel", "ordre", "nom"]
        constraints = [models.UniqueConstraint(fields=["referentiel", "nom"], name="uniq_competence_nom")]

    def __str__(self):
        return self.nom


class EvaluationCompetence(models.Model):
    """
    Une observation du niveau d'un élève sur une compétence, en ajout seul :
    une nouvelle évaluation s'ajoute, l'ancienne reste. Une proposition (issue
    d'un examen en ligne) ne compte qu'après validation par l'enseignant.
    """

    SOURCE_MANUELLE = "manuelle"
    SOURCE_EXAMEN = "examen"
    SOURCES = [(SOURCE_MANUELLE, "Évaluation de l'enseignant"), (SOURCE_EXAMEN, "Examen en ligne")]
    PROPOSEE, VALIDEE, REFUSEE = "proposee", "validee", "refusee"
    STATUTS = [(PROPOSEE, "Proposée"), (VALIDEE, "Validée"), (REFUSEE, "Refusée")]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="evaluations_competences")
    enrollment = models.ForeignKey("students.StudentEnrollment", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    competence = models.ForeignKey(Competence, on_delete=models.PROTECT, related_name="evaluations")
    niveau = models.ForeignKey(NiveauMaitrise, on_delete=models.PROTECT, related_name="+")
    date_evaluation = models.DateField()
    commentaire = models.TextField(blank=True)
    preuve = models.FileField(upload_to="suivi/preuves/", null=True, blank=True)
    source = models.CharField(max_length=10, choices=SOURCES, default=SOURCE_MANUELLE)
    reference_source = models.CharField(max_length=60, blank=True, help_text="Ex. : tentative d'examen n° 12.")
    statut = models.CharField(max_length=10, choices=STATUTS, default=VALIDEE)
    evalue_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    decide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decide_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_evaluation", "-id"]
        indexes = [models.Index(fields=["student", "competence", "statut", "date_evaluation"], name="suivi_ec_eleve_idx")]
        constraints = [
            models.UniqueConstraint(fields=["student", "competence", "reference_source"],
                                    condition=~models.Q(reference_source=""), name="uniq_ec_source"),
        ]


class EvaluationPedagogique(models.Model):
    """Évaluation propre au suivi (positionnement, bilan...), distincte d'une note officielle."""

    TYPES = [("initiale", "Évaluation initiale"), ("formative", "Évaluation formative"),
             ("bilan", "Bilan"), ("autre", "Autre")]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="evaluations_pedagogiques")
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    titre = models.CharField(max_length=150)
    type = models.CharField(max_length=10, choices=TYPES, default="formative")
    score_pourcent = models.DecimalField(max_digits=5, decimal_places=2,
                                         validators=[MinValueValidator(0), MaxValueValidator(100)])
    date_evaluation = models.DateField()
    commentaire = models.TextField(blank=True)
    evalue_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_evaluation", "-id"]
        indexes = [models.Index(fields=["student", "date_evaluation"], name="suivi_ep_eleve_idx")]


class ObservationParticipation(models.Model):
    """Observation saisie par l'enseignant. Jamais déduite d'une caméra ni d'un micro."""

    NIVEAUX = [(1, "Faible"), (2, "Moyenne"), (3, "Bonne"), (4, "Très bonne")]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="observations_participation")
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    niveau = models.PositiveSmallIntegerField(choices=NIVEAUX)
    date_observation = models.DateField()
    note = models.TextField(blank=True)
    observe_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_observation", "-id"]
        indexes = [models.Index(fields=["student", "date_observation"], name="suivi_op_eleve_idx")]


class Objectif(models.Model):
    """Objectif individuel (student) ou collectif (class_obj)."""

    STATUTS = [("a_commencer", "À commencer"), ("en_cours", "En cours"), ("atteint", "Atteint"),
               ("non_atteint", "Non atteint"), ("reporte", "Reporté")]
    PRIORITES = [("basse", "Basse"), ("normale", "Normale"), ("haute", "Haute")]

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="objectifs")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, null=True, blank=True, related_name="objectifs")
    class_obj = models.ForeignKey("classes.Class", on_delete=models.CASCADE, null=True, blank=True, related_name="objectifs")
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    competence = models.ForeignKey(Competence, on_delete=models.SET_NULL, null=True, blank=True, related_name="objectifs")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    criteres_reussite = models.TextField(blank=True)
    date_cible = models.DateField(null=True, blank=True)
    priorite = models.CharField(max_length=7, choices=PRIORITES, default="normale")
    statut = models.CharField(max_length=11, choices=STATUTS, default="a_commencer")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(student__isnull=False, class_obj__isnull=True)
                           | models.Q(student__isnull=True, class_obj__isnull=False)),
                name="objectif_individuel_ou_collectif",
            ),
        ]

    def __str__(self):
        return self.titre


class ObjectifHistorique(models.Model):
    objectif = models.ForeignKey(Objectif, on_delete=models.CASCADE, related_name="historique")
    ancien_statut = models.CharField(max_length=11, blank=True)
    nouveau_statut = models.CharField(max_length=11)
    note = models.TextField(blank=True)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class PlanAccompagnement(models.Model):
    STATUTS = [("actif", "Actif"), ("termine", "Terminé"), ("abandonne", "Abandonné")]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="plans_accompagnement")
    titre = models.CharField(max_length=200)
    motif = models.TextField(blank=True)
    statut = models.CharField(max_length=9, choices=STATUTS, default="actif")
    debut = models.DateField()
    fin = models.DateField(null=True, blank=True)
    partage_famille = models.BooleanField(default=False)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-debut", "-id"]


class ActionPedagogique(models.Model):
    """Action d'un objectif ou d'un plan : ce qui est proposé, réalisé, et son résultat."""

    TYPES = [("exercices", "Exercices supplémentaires"), ("revision", "Révision ciblée"),
             ("soutien", "Séance de soutien"), ("activite", "Activité complémentaire"),
             ("individuel", "Accompagnement individuel"), ("hebdomadaire", "Objectif hebdomadaire"),
             ("reevaluation", "Réévaluation"), ("autre", "Autre")]

    objectif = models.ForeignKey(Objectif, on_delete=models.CASCADE, null=True, blank=True, related_name="actions")
    plan = models.ForeignKey(PlanAccompagnement, on_delete=models.CASCADE, null=True, blank=True, related_name="actions")
    type = models.CharField(max_length=12, choices=TYPES, default="autre")
    description = models.TextField()
    echeance = models.DateField(null=True, blank=True)
    realisee_le = models.DateField(null=True, blank=True)
    resultat = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["echeance", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(objectif__isnull=False, plan__isnull=True)
                           | models.Q(objectif__isnull=True, plan__isnull=False)),
                name="action_objectif_ou_plan",
            ),
        ]


class ParametresSuivi(models.Model):
    """Règles de calcul par académie, modifiables par l'administration."""

    POIDS_DEFAUT = {"competences": 50, "evaluations": 30, "objectifs": 20}

    school = models.OneToOneField("schools.School", on_delete=models.CASCADE, related_name="parametres_suivi")
    poids = models.JSONField(default=dict, blank=True)
    min_notes_comparaison = models.PositiveSmallIntegerField(default=2)
    min_observations = models.PositiveSmallIntegerField(default=2)
    updated_at = models.DateTimeField(auto_now=True)

    def poids_effectifs(self):
        return {**self.POIDS_DEFAUT, **(self.poids or {})}


class RapportPedagogique(models.Model):
    """
    Rapport individuel. Les chiffres (`donnees`) viennent des services et ne s'éditent
    pas ; l'enseignant rédige `contenu`. Toute validation ou publication laisse une
    version figée : rien ne change en silence après publication.
    """

    TYPES = [("hebdomadaire", "Hebdomadaire"), ("mensuel", "Mensuel"), ("trimestriel", "Trimestriel"),
             ("annuel", "Annuel"), ("demande", "À la demande")]
    BROUILLON, VALIDE, PUBLIE = "brouillon", "valide", "publie"
    STATUTS = [(BROUILLON, "Brouillon"), (VALIDE, "Validé"), (PUBLIE, "Publié")]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="rapports_pedagogiques")
    type = models.CharField(max_length=12, choices=TYPES, default="mensuel")
    du = models.DateField()
    au = models.DateField()
    statut = models.CharField(max_length=9, choices=STATUTS, default=BROUILLON)
    numero_version = models.PositiveIntegerField(default=1)
    donnees = models.JSONField(default=dict)
    contenu = models.JSONField(default=dict, blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-au", "-id"]
        indexes = [models.Index(fields=["student", "statut"], name="suivi_rp_eleve_idx")]


class RapportVersion(models.Model):
    rapport = models.ForeignKey(RapportPedagogique, on_delete=models.CASCADE, related_name="versions")
    numero = models.PositiveIntegerField()
    statut = models.CharField(max_length=9)
    donnees = models.JSONField(default=dict)
    contenu = models.JSONField(default=dict)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["rapport", "numero", "statut"], name="uniq_version_rapport")]


class RegleAlerte(models.Model):
    """Règle explicite, réglable par académie."""

    CODES = [
        ("baisse_resultats", "Résultats en baisse"), ("progression_positive", "Résultats en hausse"),
        ("stagnation", "Compétence qui stagne"), ("absences", "Absences répétées"),
        ("difficultes", "Plusieurs compétences en difficulté"), ("objectif_atteint", "Objectif atteint"),
    ]
    DEFAUTS = {"baisse_resultats": 10, "progression_positive": 10, "stagnation": 3, "absences": 3, "difficultes": 3, "objectif_atteint": 1}

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="regles_alerte")
    code = models.CharField(max_length=24, choices=CODES)
    seuil = models.PositiveSmallIntegerField()
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="uniq_regle_alerte")]


class AlertePedagogique(models.Model):
    """Signal à examiner : jamais un diagnostic, jamais une décision automatique."""

    CATEGORIES = [("positif", "Progression positive"), ("attention", "Attention"),
                  ("surveiller", "À surveiller"), ("objectif", "Objectif atteint")]
    STATUTS = [("nouvelle", "Nouvelle"), ("acceptee", "Acceptée"), ("modifiee", "Modifiée"), ("refusee", "Refusée")]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="alertes_pedagogiques")
    code = models.CharField(max_length=24)
    categorie = models.CharField(max_length=10, choices=CATEGORIES)
    cle = models.CharField(max_length=60, help_text="Évite de répéter le même signal.")
    message = models.TextField()
    donnees = models.JSONField(default=dict)
    recommandation = models.TextField(blank=True)
    statut = models.CharField(max_length=8, choices=STATUTS, default="nouvelle")
    decide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decide_le = models.DateTimeField(null=True, blank=True)
    note_decision = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["student", "code", "cle"], name="uniq_alerte")]

