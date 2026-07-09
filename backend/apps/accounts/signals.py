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
