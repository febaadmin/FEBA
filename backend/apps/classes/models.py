from django.db import models
from apps.schools.models import SchoolYear, Level


class Class(models.Model):
    # ── Parcours linguistique de la classe ───────────────────────────────
    #
    # POURQUOI UN CHAMP DÉCLARÉ PLUTÔT QU'UNE DÉDUCTION
    #
    # Le parcours était jusqu'ici DEVINÉ à partir des matières présentes :
    # une classe avec des matières FR et EN était « bilingue », les autres
    # étaient en défaut. Cette déduction se trompe dans les deux sens. Une
    # classe bilingue dont on vient de retirer la dernière matière anglaise
    # devient « francophone » sans que personne ne l'ait décidé ; et une
    # classe volontairement anglophone est signalée comme incomplète pour
    # toujours, parce qu'il lui « manque » une langue qu'elle n'a jamais
    # voulue.
    #
    # FEBA French Heritage Academy a besoin des trois parcours : ses
    # groupes s'adressent à des enfants de la diaspora dont certains ne
    # suivent que le français. Faith & Excellence Bilingual Academy, elle,
    # est bilingue par construction — d'où la valeur par défaut, qui laisse
    # TOUTES les classes existantes exactement dans leur comportement
    # actuel.
    TRACK_BILINGUAL = "BILINGUAL"
    TRACK_FRANCOPHONE = "FRANCOPHONE"
    TRACK_ANGLOPHONE = "ANGLOPHONE"
    LANGUAGE_TRACKS = [
        (TRACK_BILINGUAL, "Bilingue (français et anglais)"),
        (TRACK_FRANCOPHONE, "Francophone"),
        (TRACK_ANGLOPHONE, "Anglophone"),
    ]

    #: Langues de matières attendues pour chaque parcours.
    TRACK_LANGUAGES = {
        TRACK_BILINGUAL: ("fr", "en"),
        TRACK_FRANCOPHONE: ("fr",),
        TRACK_ANGLOPHONE: ("en",),
    }

    name = models.CharField(max_length=50)
    language_track = models.CharField(
        max_length=20, choices=LANGUAGE_TRACKS, default=TRACK_BILINGUAL,
        verbose_name="Parcours linguistique",
        help_text=(
            "Détermine les matières attendues et la forme du bulletin. "
            "« Bilingue » est la valeur par défaut : c'est le fonctionnement "
            "historique de FEBA, et il reste inchangé."
        ),
    )
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="classes")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name="classes")
    max_students = models.PositiveIntegerField(default=30)
    # M2M: matières assignées à cette classe (FR + EN)
    subjects = models.ManyToManyField(
        "subjects.Subject",
        blank=True,
        related_name="classes",
        verbose_name="Matières",
        help_text="Matières françaises ET anglaises assignées à cette classe",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Classe"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_fr_subjects(self):
        """Retourne les matières françaises de cette classe."""
        return self.subjects.filter(language="fr")

    def get_en_subjects(self):
        """Retourne les matières anglaises de cette classe."""
        return self.subjects.filter(language="en")

    def expected_subject_languages(self):
        """Langues de matières attendues, d'après le parcours DÉCLARÉ."""
        return self.TRACK_LANGUAGES.get(
            self.language_track, self.TRACK_LANGUAGES[self.TRACK_BILINGUAL])

    def missing_subject_languages(self):
        """
        Langues attendues pour lesquelles la classe n'a aucune matière.

        C'est ce qui remplace « au moins une matière française ET une
        anglaise sont obligatoires » : la phrase était fausse pour une
        classe anglophone, à laquelle on reprochait sans fin l'absence
        d'une langue qu'elle n'enseigne pas.
        """
        present = set(self.subjects.values_list("language", flat=True))
        return [lang for lang in self.expected_subject_languages()
                if lang not in present]

    def is_language_configuration_complete(self):
        """Vrai si la classe a au moins une matière dans chaque langue attendue."""
        return not self.missing_subject_languages()

    def has_bilingual_subjects(self):
        """Vérifie que la classe a au moins une matière FR et une EN."""
        return self.get_fr_subjects().exists() and self.get_en_subjects().exists()