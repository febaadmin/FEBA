"""
Signals — synchronisation automatique CustomUser -> entites liees

BUG FIX #1 SYSTEMIC: Propagation is_active
  Quand un CustomUser est desactive (is_active=False), le Student lie doit
  aussi etre desactive. Sans ca, l'eleve desactive reste visible et utilisable
  dans toutes les listes filtrees par Student.is_active.

BUG FIX #5: Sync noms/prenoms
  Quand un utilisateur modifie first_name/last_name, le Student lie est mis a jour.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser
import logging

logger = logging.getLogger("apps")

_SYNCING = set()  # guard against recursion by user pk


@receiver(post_save, sender=CustomUser)
def sync_user_to_entities(sender, instance, created, **kwargs):
    """
    Apres chaque sauvegarde d'un CustomUser :
    - Propage is_active -> Student.is_active (BUG FIX CRITIQUE)
    - Sync first_name / last_name -> Student
    """
    if instance.pk in _SYNCING:
        return

    try:
        if instance.role == "student":
            student = getattr(instance, "student_profile", None)
            if student is None:
                return

            updates = {}

            # FIX CRITIQUE: propager le statut actif/inactif
            if student.is_active != instance.is_active:
                updates["is_active"] = instance.is_active

            # Sync noms
            if instance.first_name and student.first_name != instance.first_name:
                updates["first_name"] = instance.first_name
            if instance.last_name and student.last_name != instance.last_name:
                updates["last_name"] = instance.last_name

            if updates:
                _SYNCING.add(instance.pk)
                try:
                    for k, v in updates.items():
                        setattr(student, k, v)
                    student.save(update_fields=list(updates.keys()))
                    logger.info(
                        f"sync_user_to_entities: user {instance.email} -> "
                        f"Student updated: {updates}"
                    )
                finally:
                    _SYNCING.discard(instance.pk)

    except Exception as e:
        logger.warning(f"sync_user_to_entities error for {instance.email}: {e}")


@receiver(post_save, sender=CustomUser)
def sync_primary_membership(sender, instance, created, **kwargs):
    """
    Maintient `OrganizationMembership` cohérent avec `CustomUser.school`.

    `user.school` reste la source de vérité du rattachement principal (c'est
    ce champ que lit le filtrage de queryset). Ce signal se contente d'en
    refléter l'état dans une appartenance principale, pour que
    l'historique et le statut soient disponibles sans dupliquer la règle
    d'isolation.

    Le superadmin est traité à part : rôle plateforme, il reçoit une
    appartenance NON principale à chaque entité afin de pouvoir basculer.
    """
    from apps.schools.models import OrganizationMembership, School

    try:
        if instance.role == "superadmin":
            for org in School.objects.filter(is_active=True):
                OrganizationMembership.objects.get_or_create(
                    user=instance, organization=org,
                    defaults={"role": "superadmin", "status": "active", "is_primary": False},
                )
            return

        if instance.school_id is None:
            return

        membership, created_m = OrganizationMembership.objects.get_or_create(
            user=instance, organization_id=instance.school_id,
            defaults={"role": instance.role, "status": "active", "is_primary": True},
        )

        updates = {}
        if membership.role != instance.role:
            updates["role"] = instance.role
        if not membership.is_primary:
            # Une seule appartenance principale par utilisateur : on
            # rétrograde les autres avant de promouvoir celle-ci.
            OrganizationMembership.objects.filter(
                user=instance, is_primary=True,
            ).exclude(pk=membership.pk).update(is_primary=False)
            updates["is_primary"] = True

        if updates:
            for key, value in updates.items():
                setattr(membership, key, value)
            membership.save(update_fields=list(updates.keys()) + ["updated_at"])

    except Exception as exc:  # pragma: no cover - ne bloque jamais la sauvegarde
        logger.warning(f"sync_primary_membership error for {instance.email}: {exc}")
