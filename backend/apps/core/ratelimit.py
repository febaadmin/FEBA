"""
apps/core/ratelimit.py — Le limiteur de débit, et ce qu'il fait quand il
tombe.

LE DÉFAUT CORRIGÉ ICI
---------------------
`django_ratelimit` compte les tentatives dans le cache. Ce cache est
Redis. Redis indisponible, `cache.add()` lève une exception de connexion,
qui remonte jusqu'au gestionnaire d'exceptions de DRF et devient un
**500 « Une erreur interne est survenue »**.

Ce qui est faux dans cette réponse n'est pas le refus — refuser est la
bonne décision, on y revient — mais ce qu'elle raconte. Un 500 dit
« l'application a un défaut ». Ici l'application va bien : c'est une
dépendance d'infrastructure qui est absente. L'utilisateur qui lit ce
message rappelle son école ; l'école appelle l'éditeur ; l'éditeur
cherche un bug qui n'existe pas. Pendant ce temps, personne ne redémarre
Redis.

Constaté en montant les parcours navigateur : la connexion répondait 500
sans que rien n'indique la cause.

POURQUOI ON RESTE FERMÉ
-----------------------
La tentation, quand le compteur ne répond plus, est de laisser passer :
le service reste debout, personne ne se plaint. C'est exactement ce qu'il
ne faut pas faire. Le limiteur de débit de `/auth/login/` est ce qui
sépare une base de comptes d'une attaque par force brute. Le désactiver
parce qu'un cache est tombé revient à ouvrir la porte au moment précis où
l'on ne peut plus compter les visiteurs — et l'incident qui a fait tomber
Redis peut être celui-là même.

On refuse donc, mais on refuse **honnêtement** : 503, un message qui dit
ce qui se passe, un en-tête `Retry-After`, une trace technique dans les
journaux et un incident visible par le super administrateur.

CE QUI EST ENTOURÉ, ET CE QUI NE L'EST PAS
------------------------------------------
Seul l'appel au COMPTEUR est protégé. La vue, elle, s'exécute sans
filet : un défaut dans la connexion elle-même doit continuer de sortir en
500 avec son incident, comme avant. Entourer la vue entière
transformerait n'importe quel bug en « service temporairement
indisponible » — le genre de message rassurant derrière lequel un défaut
réel vit très longtemps.
"""
import logging

from django.utils.translation import get_language
from django_ratelimit.core import is_ratelimited
from django_ratelimit.exceptions import Ratelimited
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger("apps")

#: Combien de secondes avant de réessayer. Redémarrer un cache prend
#: quelques dizaines de secondes ; renvoyer 1 s ferait marteler le
#: service par tous les clients au même instant.
RETRY_AFTER_SECONDS = 30

#: Message rendu à l'utilisateur, par langue.
#:
#: Le projet est bilingue et négocie la langue par `Accept-Language`
#: (`LocaleMiddleware` est actif), mais il ne livre AUCUN catalogue de
#: traduction compilé : `gettext` rendrait donc la chaîne d'origine dans
#: les deux cas, ce qui n'est pas une localisation mais son apparence.
#: Une table explicite se lit, se teste, et n'ajoute pas une étape de
#: compilation à l'installation pour deux phrases.
MESSAGES = {
    "fr": (
        "Le service d'authentification est temporairement indisponible. "
        "Aucune tentative de connexion ne peut être vérifiée pour l'instant. "
        "Réessayez dans quelques instants ; si le problème persiste, "
        "signalez-le à l'administrateur de l'établissement."
    ),
    "en": (
        "The authentication service is temporarily unavailable. "
        "Sign-in attempts cannot be verified right now. "
        "Please try again shortly; if the problem persists, "
        "report it to your school administrator."
    ),
}


def message_indisponible(langue=None):
    """Message d'indisponibilité dans la langue négociée, français par défaut."""
    code = (langue or get_language() or "fr").split("-")[0].lower()
    return MESSAGES.get(code, MESSAGES["fr"])


def _refuser_service(request, exc, groupe):
    """
    Journalise, ouvre un incident, et refuse proprement.

    L'incident est créé même si personne ne le lit tout de suite : c'est
    la seule trace qui subsiste une fois les journaux tournés, et c'est
    elle qui permet au super administrateur de voir qu'un cache est tombé
    à trois heures du matin.
    """
    logger.exception(
        "Limiteur de débit indisponible sur %s (%s) : %s — la requête est "
        "REFUSÉE, le compteur ne peut pas être tenu.",
        getattr(request, "path", "?"), groupe, exc,
    )

    incident = None
    try:
        from apps.incidents.services import report_incident

        incident = report_incident(
            exc,
            request=request,
            module="ratelimit",
            attempted_action=(
                f"{getattr(request, 'method', '')} "
                f"{getattr(request, 'path', '')}".strip()
            ),
            severity="high",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:  # pragma: no cover — l'enregistrement lui-même échoue
        # On ne laisse PAS l'échec du signalement masquer le refus : le
        # client doit recevoir son 503 même si la base d'incidents est,
        # elle aussi, en difficulté.
        logger.exception("L'incident n'a pas pu être enregistré.")

    corps = {
        "detail": message_indisponible(),
        # Nomme la dépendance, sans donner ni adresse ni version : celui
        # qui exploite le serveur sait immédiatement quoi redémarrer.
        "service": "cache",
        "retry_after": RETRY_AFTER_SECONDS,
    }
    if incident is not None:
        corps["incident_reference"] = incident.reference

    reponse = Response(corps, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    reponse["Retry-After"] = str(RETRY_AFTER_SECONDS)
    return reponse


def ratelimit_or_503(*, key, rate, method, group=None):
    """
    Comme `django_ratelimit.decorators.ratelimit(block=True)`, mais un
    compteur injoignable donne 503 et non 500.

    S'applique à une méthode de vue DRF (`self, request, …`), là où le
    décorateur d'origine s'applique à une fonction (`request, …`) et
    demandait `method_decorator`.
    """
    def decorateur(vue):
        groupe = group or f"{vue.__module__}.{vue.__qualname__}"

        def enveloppe(self, request, *args, **kwargs):
            try:
                atteinte = is_ratelimited(
                    request=request, group=groupe, fn=vue, key=key,
                    rate=rate, method=method, increment=True,
                )
            except Ratelimited:
                # Ne peut pas venir d'ici, mais si une version future de
                # la bibliothèque la levait, elle ne doit pas être prise
                # pour une panne de cache.
                raise
            except Exception as exc:
                return _refuser_service(request, exc, groupe)

            request.limited = atteinte or getattr(request, "limited", False)
            if atteinte:
                raise Ratelimited()

            # La vue s'exécute SANS filet : un défaut dedans doit
            # continuer de sortir en 500 avec son incident.
            return vue(self, request, *args, **kwargs)

        enveloppe.__name__ = vue.__name__
        enveloppe.__doc__ = vue.__doc__
        enveloppe.__wrapped__ = vue
        return enveloppe

    return decorateur
