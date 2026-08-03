"""
apps/payments/fee_models.py — Grille tarifaire : l'autorité sur les montants

POURQUOI CE MODÈLE EXISTE
-------------------------
Le paiement par carte a une règle non négociable : **le serveur décide
combien**. Tant que le montant arrivait dans le corps de la requête, cette
règle n'était qu'une phrase — il suffisait d'ouvrir les outils de
développement et de remplacer 1250 par 1 pour régler une année de
scolarité au prix d'un café.

Pour que le serveur puisse décider, il faut qu'il sache. C'est le rôle de
cette grille : elle associe une académie, une année, un niveau et une
nature de frais à un montant, en unité mineure et dans la devise de
l'académie.

CE QUE CE MODÈLE N'EST PAS
--------------------------
Ce n'est pas un module de facturation. Il n'y a ici ni échéancier, ni
solde, ni relance, ni avoir. Une facture — au sens comptable — suppose une
numérotation légale, un séquencement inaltérable et des règles fiscales
propres au Bénin comme aux États-Unis ; l'inventer à moitié serait pire
que de ne pas l'avoir. La grille répond à une question précise et unique :
« combien coûte ceci, ici, cette année ». C'est ce qu'il faut pour qu'un
paiement en ligne ne soit pas falsifiable.

RÉSOLUTION DU TARIF
-------------------
Du plus précis au plus général : un tarif défini pour un niveau l'emporte
sur un tarif d'année, lui-même prioritaire sur un tarif permanent. Cette
gradation permet à une académie de publier un prix unique et de ne
détailler que les exceptions, plutôt que de saisir une ligne par classe.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.currency import DEFAULT_CURRENCY, Money


class FeeSchedule(models.Model):
    """Un tarif publié par une académie pour une nature de frais."""

    academy = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="fee_schedules",
        help_text="Académie qui publie ce tarif — impose la devise.",
    )
    school_year = models.ForeignKey(
        "schools.SchoolYear", on_delete=models.CASCADE, null=True, blank=True,
        related_name="fee_schedules",
        help_text="Année concernée. Vide = tarif permanent, toutes années.",
    )
    level = models.ForeignKey(
        "schools.Level", on_delete=models.CASCADE, null=True, blank=True,
        related_name="fee_schedules",
        help_text="Niveau concerné. Vide = tous niveaux.",
    )
    payment_type = models.CharField(
        max_length=15,
        help_text="Nature des frais (mensualite, inscription, cantine…).",
    )
    label = models.CharField(
        max_length=120, blank=True,
        help_text="Libellé affiché au payeur. À défaut, le type est utilisé.",
    )

    # Le montant est stocké en unité mineure, comme partout ailleurs : un
    # `float` sur une somme d'argent finit toujours par produire un centime
    # fantôme, et un centime fantôme sur un reçu est une réclamation.
    amount_minor = models.BigIntegerField(
        help_text="Montant en unité mineure (cents pour USD, franc pour XOF).",
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY, editable=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tarif"
        verbose_name_plural = "Grille tarifaire"
        ordering = ["academy", "payment_type", "level"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_minor__gt=0), name="fee_amount_positive",
            ),
            # Deux tarifs identiques pour le même périmètre rendraient la
            # résolution dépendante de l'ordre d'insertion, donc instable.
            #
            # Quatre contraintes et non une seule : en SQL, deux NULL ne
            # sont pas égaux, donc une contrainte unique portant sur des
            # colonnes nullables laisserait passer autant de doublons
            # « toutes années, tous niveaux » qu'on voudrait. Chaque
            # combinaison de portée est donc verrouillée explicitement.
            # (`nulls_distinct=False` existe, mais seulement sur
            # PostgreSQL 15+ ; le projet doit aussi tourner sur SQLite.)
            models.UniqueConstraint(
                fields=["academy", "payment_type", "school_year", "level"],
                name="uniq_fee_year_level",
                condition=models.Q(school_year__isnull=False, level__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["academy", "payment_type", "school_year"],
                name="uniq_fee_year_any_level",
                condition=models.Q(school_year__isnull=False, level__isnull=True),
            ),
            models.UniqueConstraint(
                fields=["academy", "payment_type", "level"],
                name="uniq_fee_any_year_level",
                condition=models.Q(school_year__isnull=True, level__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["academy", "payment_type"],
                name="uniq_fee_permanent",
                condition=models.Q(school_year__isnull=True, level__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.academy.code} · {self.payment_type} · {self.money.formatted()}"

    @property
    def money(self):
        return Money(self.amount_minor, self.currency or DEFAULT_CURRENCY)

    @property
    def display_label(self):
        return self.label or self.payment_type

    def clean(self):
        super().clean()
        # Un tarif ne peut pas être rattaché à l'année ou au niveau d'une
        # AUTRE académie : ce serait une fuite de périmètre, et le montant
        # résolu ne correspondrait à rien.
        for field in ("school_year", "level"):
            related = getattr(self, field, None)
            if related is not None and related.school_id != self.academy_id:
                raise ValidationError({
                    field: (
                        "Cet élément appartient à une autre académie : un "
                        "tarif ne peut pas franchir la frontière entre "
                        "FEBA et FEBA French Heritage Academy."
                    )
                })

    def save(self, *args, **kwargs):
        # La devise vient de l'académie, jamais d'une saisie.
        self.currency = getattr(self.academy, "currency_code", None) or DEFAULT_CURRENCY
        # Validation complète, contraintes comprises : un tarif nul ou
        # négatif doit produire une erreur lisible, pas une IntegrityError
        # de la base remontée telle quelle à l'utilisateur.
        self.full_clean()
        super().save(*args, **kwargs)

    # ── Résolution ────────────────────────────────────────────────────

    @classmethod
    def resolve(cls, student, payment_type, school_year=None):
        """
        Tarif applicable à cet élève, ou None si l'académie n'en publie pas.

        Renvoyer None n'est pas un échec : une académie peut encaisser des
        sommes hors grille (un rattrapage, un livre). C'est l'appelant qui
        décide si l'absence de tarif autorise une saisie manuelle — et,
        pour un paiement en ligne par un parent, la réponse est non.
        """
        academy = getattr(student, "school", None)
        if academy is None:
            return None

        level = getattr(getattr(student, "current_class", None), "level", None)
        candidates = cls.objects.filter(
            academy=academy, payment_type=payment_type, is_active=True,
        ).filter(
            models.Q(school_year=school_year) | models.Q(school_year__isnull=True),
        ).filter(
            models.Q(level=level) | models.Q(level__isnull=True),
        )

        # Le plus spécifique gagne : niveau ET année, puis année, puis
        # niveau, puis le tarif permanent tous niveaux.
        def specificity(fee):
            return (fee.school_year_id is not None) * 2 + (fee.level_id is not None)

        ranked = sorted(candidates, key=specificity, reverse=True)
        return ranked[0] if ranked else None
