"""
FEBA - Examens et évaluations : système distinct du module de notes.

Un résultat reste ici. Il ne devient une note officielle que par un transfert
explicite (TransfertNote), une seule fois par élève et par épreuve.
Une version de question est immuable : modifier une question crée une nouvelle
version, et une épreuve commencée garde celle qu'elle a reçue.
"""
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Question(models.Model):
    QCM_UNIQUE, QCM_MULTIPLE, VRAI_FAUX, OUVERTE, COURTE = "qcm_unique", "qcm_multiple", "vrai_faux", "ouverte", "courte"
    NUMERIQUE, TROUS, ASSOCIATION, CLASSEMENT, FICHIER = "numerique", "trous", "association", "classement", "fichier"
    TYPES = [
        (QCM_UNIQUE, "QCM à réponse unique"), (QCM_MULTIPLE, "QCM à réponses multiples"), (VRAI_FAUX, "Vrai ou faux"),
        (OUVERTE, "Question ouverte"), (COURTE, "Réponse courte"), (NUMERIQUE, "Réponse numérique"),
        (TROUS, "Texte à trous"), (ASSOCIATION, "Associations"), (CLASSEMENT, "Classement"),
        (FICHIER, "Fichier à déposer"),
    ]
    DIFFICULTES = [(1, "Facile"), (2, "Moyenne"), (3, "Difficile")]

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="questions")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    level = models.ForeignKey("schools.Level", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    type = models.CharField(max_length=12, choices=TYPES)
    difficulte = models.PositiveSmallIntegerField(choices=DIFFICULTES, default=2)
    prive = models.BooleanField(default=False, help_text="Visible seulement par son auteur et l'administration.")
    archive = models.BooleanField(default=False)
    competences = models.ManyToManyField("suivi.Competence", blank=True, related_name="questions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["school", "subject", "difficulte", "archive"], name="eval_q_filtre_idx")]

    @property
    def version_courante(self):
        return self.versions.order_by("-numero").first()


class QuestionVersion(models.Model):
    MEDIAS = [("", "Aucun"), ("image", "Image"), ("document", "Document"), ("audio", "Audio"), ("video", "Vidéo")]

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="versions")
    numero = models.PositiveIntegerField()
    enonce = models.TextField()
    contenu = models.JSONField(default=dict, blank=True, help_text="Choix, paires ou éléments montrés à l'élève.")
    corrige = models.JSONField(default=dict, blank=True, help_text="Jamais envoyé à l'élève pendant l'épreuve.")
    criteres = models.TextField(blank=True)
    explication = models.TextField(blank=True)
    points = models.DecimalField(max_digits=6, decimal_places=2, default=1, validators=[MinValueValidator(0)])
    media = models.FileField(upload_to="evaluations/media/", null=True, blank=True)
    media_type = models.CharField(max_length=8, choices=MEDIAS, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question", "-numero"]
        constraints = [models.UniqueConstraint(fields=["question", "numero"], name="uniq_version_question")]


class Epreuve(models.Model):
    TYPES = [
        ("quiz", "Quiz d'entraînement"), ("interrogation", "Interrogation"), ("evaluation", "Évaluation"),
        ("examen", "Examen officiel"), ("blanc", "Examen blanc"), ("positionnement", "Évaluation de positionnement"),
        ("diagnostique", "Évaluation diagnostique"), ("competences", "Évaluation de compétences"),
        ("fin_formation", "Évaluation de fin de formation"),
    ]
    BROUILLON, PUBLIEE, CLOSE, ARCHIVEE = "brouillon", "publiee", "close", "archivee"
    STATUTS = [(BROUILLON, "Brouillon"), (PUBLIEE, "Publiée"), (CLOSE, "Close"), (ARCHIVEE, "Archivée")]
    POLITIQUES = [("meilleure", "Meilleure tentative"), ("derniere", "Dernière tentative"),
                  ("premiere", "Première tentative"), ("validee", "Tentative choisie par l'enseignant")]
    PERIODES = [("T1", "Trimestre 1"), ("T2", "Trimestre 2"), ("T3", "Trimestre 3")]

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="epreuves")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    consignes = models.TextField(blank=True)
    type = models.CharField(max_length=14, choices=TYPES, default="quiz")
    subject = models.ForeignKey("subjects.Subject", on_delete=models.PROTECT, related_name="+")
    class_obj = models.ForeignKey("classes.Class", on_delete=models.PROTECT, related_name="epreuves")
    eleves_cibles = models.ManyToManyField("students.Student", blank=True, related_name="+",
                                           help_text="Vide : toute la classe.")
    school_year = models.ForeignKey("schools.SchoolYear", on_delete=models.PROTECT, related_name="+")
    periode = models.CharField(max_length=2, choices=PERIODES, blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    ouverture = models.DateTimeField()
    fermeture = models.DateTimeField()
    duree_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    tentatives_max = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    note_max = models.DecimalField(max_digits=6, decimal_places=2, default=20, validators=[MinValueValidator(1)])
    seuil_reussite = models.DecimalField(max_digits=5, decimal_places=2, default=50,
                                         validators=[MinValueValidator(0), MaxValueValidator(100)])
    politique = models.CharField(max_length=9, choices=POLITIQUES, default="meilleure")
    melanger_questions = models.BooleanField(default=True)
    melanger_reponses = models.BooleanField(default=True)
    retour_autorise = models.BooleanField(default=True)
    reprise_autorisee = models.BooleanField(default=True)
    produit_note = models.BooleanField(default=False, help_text="Peut être transférée vers le module de notes, après validation.")
    note_type = models.CharField(max_length=20, default="examen")
    regles_tirage = models.JSONField(default=list, blank=True)
    statut = models.CharField(max_length=9, choices=STATUTS, default=BROUILLON)
    resultats_publies = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ouverture"]
        indexes = [models.Index(fields=["school", "class_obj", "statut"], name="eval_e_classe_idx")]
        constraints = [models.CheckConstraint(condition=Q(fermeture__gt=models.F("ouverture")), name="epreuve_dates_coherentes")]

    def __str__(self):
        return self.titre


class EpreuveQuestion(models.Model):
    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE, related_name="questions")
    version = models.ForeignKey(QuestionVersion, on_delete=models.PROTECT, related_name="+")
    ordre = models.PositiveIntegerField(default=0)
    points = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["ordre", "id"]
        constraints = [models.UniqueConstraint(fields=["epreuve", "version"], name="uniq_question_epreuve")]


class Amenagement(models.Model):
    """Temps et tentatives supplémentaires pour un élève."""

    epreuve = models.ForeignKey(Epreuve, on_delete=models.CASCADE, related_name="amenagements")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="+")
    minutes_sup = models.PositiveIntegerField(default=0)
    tentatives_sup = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["epreuve", "student"], name="uniq_amenagement")]


class Tentative(models.Model):
    EN_COURS, REMISE, CORRIGEE, VALIDEE = "en_cours", "remise", "corrigee", "validee"
    STATUTS = [(EN_COURS, "En cours"), (REMISE, "Remise, à corriger"), (CORRIGEE, "Corrigée"), (VALIDEE, "Validée")]

    epreuve = models.ForeignKey(Epreuve, on_delete=models.PROTECT, related_name="tentatives")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="tentatives_epreuves")
    numero = models.PositiveSmallIntegerField()
    seed = models.BigIntegerField()
    sujet = models.JSONField(default=list, help_text="Questions figées de cette tentative : version, points, ordre des choix.")
    debut = models.DateTimeField()
    echeance = models.DateTimeField()
    remise_le = models.DateTimeField(null=True, blank=True)
    mode_remise = models.CharField(max_length=5, blank=True, help_text="eleve ou auto.")
    statut = models.CharField(max_length=8, choices=STATUTS, default=EN_COURS)
    jeton = models.UUIDField(default=uuid.uuid4)
    recu = models.UUIDField(default=uuid.uuid4, unique=True)
    total_points = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    score_brut = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    score_corrige = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    score_valide = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    pourcentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    note_echelle = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    reussie = models.BooleanField(null=True)
    choisie = models.BooleanField(default=False, help_text="Choisie par l'enseignant (politique « validee »).")
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    valide_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-debut"]
        indexes = [models.Index(fields=["statut", "echeance"], name="eval_t_echeance_idx")]
        constraints = [
            models.UniqueConstraint(fields=["epreuve", "student", "numero"], name="uniq_tentative_numero"),
            models.UniqueConstraint(fields=["epreuve", "student"], condition=Q(statut="en_cours"), name="uniq_tentative_en_cours"),
        ]


class Reponse(models.Model):
    tentative = models.ForeignKey(Tentative, on_delete=models.CASCADE, related_name="reponses")
    version = models.ForeignKey(QuestionVersion, on_delete=models.PROTECT, related_name="+")
    valeur = models.JSONField(null=True, blank=True)
    fichier = models.FileField(upload_to="evaluations/reponses/", null=True, blank=True)
    sauvegardee_le = models.DateTimeField(auto_now=True)
    points_auto = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    points_manuel = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    commentaire = models.TextField(blank=True)
    corrige_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    corrige_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tentative", "version"], name="uniq_reponse_question")]

    @property
    def points(self):
        return self.points_manuel if self.points_manuel is not None else self.points_auto


class HistoriqueCorrection(models.Model):
    reponse = models.ForeignKey(Reponse, on_delete=models.CASCADE, related_name="historique")
    points_avant = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    points_apres = models.DecimalField(max_digits=6, decimal_places=2)
    commentaire = models.TextField(blank=True)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class EvenementTentative(models.Model):
    """Journal en ajout seul. Un événement signale ; il ne sanctionne jamais."""

    tentative = models.ForeignKey(Tentative, on_delete=models.CASCADE, related_name="evenements")
    type = models.CharField(max_length=24)
    donnees = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class TransfertNote(models.Model):
    """Passage vers le module de notes. Une seule note par élève et par épreuve, garanti en base."""

    epreuve = models.ForeignKey(Epreuve, on_delete=models.PROTECT, related_name="transferts")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="+")
    tentative = models.ForeignKey(Tentative, on_delete=models.PROTECT, related_name="transferts")
    grade = models.OneToOneField("grades.Grade", on_delete=models.PROTECT, related_name="transfert_epreuve")
    valeur = models.DecimalField(max_digits=4, decimal_places=2)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["epreuve", "student"], name="uniq_transfert_eleve")]
