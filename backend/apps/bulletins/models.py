from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.students.models import Student
from apps.schools.models import School, SchoolYear

#: Longueur maximale du commentaire du directeur. Au-delà, le bloc de
#: signatures ne tient plus avec le cachet sur le bulletin : le serveur
#: refuse plutôt que de tronquer en silence.
GENERAL_COMMENT_MAX_LENGTH = 1200


class Bulletin(models.Model):
    PERIOD_CHOICES = [("T1","Trimestre 1"),("T2","Trimestre 2"),("T3","Trimestre 3"),("annual","Annuel")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="bulletins")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE)
    enrollment = models.ForeignKey(
        "students.StudentEnrollment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bulletins",
        help_text="Inscription annuelle de l'élève correspondant à ce bulletin.",
    )
    period = models.CharField(max_length=7, choices=PERIOD_CHOICES)
    pdf_file = models.FileField(upload_to="bulletins/", null=True, blank=True)
    # Date de la DERNIÈRE génération réussie du PDF. C'était `auto_now_add` :
    # une régénération gardait la date de la toute première génération.
    generated_at = models.DateTimeField(default=timezone.now)
    #: Commentaire du Directeur / Principal's Comment, imprimé sur le PDF.
    #: Distinct du commentaire d'une note (Grade.comment).
    general_comment = models.TextField(blank=True)
    comment_updated_at = models.DateTimeField(null=True, blank=True)
    comment_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank_in_class = models.PositiveIntegerField(null=True, blank=True)
    appreciation = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Bulletin"
        unique_together = ("student","school_year","period")
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.student} - {self.period} - {self.school_year}"

    @property
    def pdf_outdated(self):
        """Vrai si le PDF manque ou précède la dernière modification du commentaire."""
        if not self.pdf_file:
            return True
        return bool(self.comment_updated_at and self.comment_updated_at > self.generated_at)


class BulletinOperation(models.Model):
    """
    Opération sur un ensemble de bulletins (commentaire du directeur ou
    génération), exécutée par le worker Celery.

    Sert à la fois de suivi (le frontend interroge son statut) et de
    journal d'audit : qui, quelle académie, quelle portée, quelle période,
    combien de bulletins, quel résultat. Le projet n'a pas de journal
    d'audit générique ; une opération de masse doit pourtant rester
    traçable.
    """
    SCOPE_STUDENT, SCOPE_CLASS, SCOPE_ACADEMY = "student", "class", "academy"
    SCOPES = [(SCOPE_STUDENT, "Un élève"), (SCOPE_CLASS, "Une classe"),
              (SCOPE_ACADEMY, "Tous les élèves de l'académie")]
    ACTION_SET, ACTION_CLEAR, ACTION_GENERATE = "set_comment", "clear_comment", "generate"
    ACTIONS = [(ACTION_SET, "Ajouter / remplacer le commentaire"),
               (ACTION_CLEAR, "Supprimer le commentaire"),
               (ACTION_GENERATE, "Générer / régénérer les bulletins")]
    STATUSES = [("queued", "En file d'attente"), ("running", "En cours"),
                ("done", "Terminée"), ("partial", "Terminée avec des échecs"),
                ("failed", "Échouée")]
    ACTIVE_STATUSES = ("queued", "running")

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="bulletin_operations")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name="+")
    period = models.CharField(max_length=7, choices=Bulletin.PERIOD_CHOICES)
    scope = models.CharField(max_length=10, choices=SCOPES)
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    class_obj = models.ForeignKey("classes.Class", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+")
    action = models.CharField(max_length=15, choices=ACTIONS)
    comment = models.TextField(blank=True)
    regenerate = models.BooleanField(default=True)
    create_missing = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUSES, default="queued")
    #: Bilan détaillé (compteurs, échecs, élèves ignorés) — voir operations.py.
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.get_scope_display()} ({self.status})"
