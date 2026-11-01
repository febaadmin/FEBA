"""
Fermeture des connexions temps réel d'un compte dont la session prend fin.
Le groupe `sessions_<id>` reçoit l'ordre de fermeture ; chaque consommateur
revérifie aussi le compte avant toute opération.
"""
import logging

from asgiref.sync import async_to_sync

logger = logging.getLogger("apps")

CODE_SESSION_TERMINEE = 4401


def groupe_sessions(user_id):
    return f"sessions_{user_id}"


def fermer_connexions(user):
    try:
        from channels.layers import get_channel_layer

        couche = get_channel_layer()
        if couche:
            async_to_sync(couche.group_send)(groupe_sessions(user.pk), {"type": "session.terminee"})
    except Exception as exc:
        # Le temps réel n'est pas servi partout : le refus des jetons reste acquis.
        logger.warning("Fermeture des connexions temps réel impossible : %s", exc)


def session_toujours_valide(user_id, mot_de_passe):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.filter(pk=user_id, is_active=True, password=mot_de_passe).exists()
