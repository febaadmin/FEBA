"""
apps/core/academy_scope.py — Portée d'académie transportée par en-tête HTTP

PROBLÈME RÉSOLU (P0)
--------------------
Au changement d'académie, le libellé du sélecteur changeait tout de suite
mais les tableaux continuaient d'afficher les données de l'académie
quittée pendant plusieurs secondes. Deux causes distinctes :

1. les requêtes déjà EN VOL au moment de la bascule se terminaient après
   celle-ci et réécrivaient le cache avec des données périmées ;
2. rien ne permettait de savoir, en regardant une réponse, à quelle
   académie elle correspondait — donc rien ne permettait de la rejeter.

Ce module traite le point 2 côté serveur : **chaque réponse API annonce
la portée qui a réellement servi à la calculer**, dans l'en-tête
`X-Academy-Scope`. Le frontend compare cette valeur à sa portée courante
et jette toute réponse qui ne correspond pas.

SÉCURITÉ — CE QUE CET EN-TÊTE N'EST PAS
---------------------------------------
`X-Academy-Scope` envoyé par le NAVIGATEUR n'a AUCUNE autorité : il n'est
jamais utilisé pour choisir les données renvoyées. La portée effective
reste déterminée exclusivement par `get_request_school()` (rattachement
en base, ou entité active persistée du superadmin). L'en-tête client sert
uniquement à journaliser les désynchronisations. Le faire mentir ne donne
accès à rien.

VALEURS
-------
    ``ALL``       superadmin en mode « Toutes les Académies »
    ``FEBA`` …    code interne stable de l'académie résolue
    ``NONE``      requête anonyme, ou compte sans rattachement
"""
import logging

logger = logging.getLogger("apps")

HEADER = "X-Academy-Scope"
CLIENT_HEADER = "HTTP_X_ACADEMY_SCOPE"

SCOPE_ALL = "ALL"
SCOPE_NONE = "NONE"


def resolve_scope_value(request):
    """
    Portée effective de la requête, sous forme de chaîne comparable.

    Volontairement tolérant : cette fonction s'exécute pour TOUTES les
    réponses, y compris les erreurs 500. Elle ne doit jamais être la
    cause d'un échec — d'où le repli sur ``NONE``.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return SCOPE_NONE

    try:
        from apps.core.tenancy import get_request_school

        school = get_request_school(request)
    except Exception:  # pragma: no cover — filet de sécurité
        return SCOPE_NONE

    if school is None:
        # Un superadmin sans entité active est en mode consolidé ; un
        # utilisateur normal sans école est un compte mal configuré.
        return SCOPE_ALL if getattr(user, "is_superadmin", lambda: False)() else SCOPE_NONE
    return school.code or f"id:{school.pk}"


class AcademyScopeMiddleware:
    """
    Ajoute `X-Academy-Scope` à chaque réponse.

    Le middleware calcule la portée APRÈS la vue : l'authentification JWT
    de DRF n'a lieu qu'à ce moment-là (DRF recopie l'utilisateur
    authentifié sur la requête Django sous-jacente). La calculer avant
    donnerait systématiquement ``NONE``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        scope = resolve_scope_value(request)
        response[HEADER] = scope

        announced = request.META.get(CLIENT_HEADER)
        if announced and announced != scope and not _is_switch_endpoint(request):
            # Désynchronisation : le navigateur croyait encore être sur une
            # autre académie. La réponse reste correcte (elle a été calculée
            # avec la portée serveur) ; c'est au frontend de la jeter.
            logger.info(
                "Portée d'académie désynchronisée sur %s : le client annonçait "
                "« %s », le serveur a servi « %s ».",
                request.path, announced, scope,
            )

        return response


def _is_switch_endpoint(request):
    """
    La requête de bascule elle-même change la portée en cours de route :
    le client annonce forcément l'ancienne valeur. Ce n'est pas une
    anomalie, on ne la journalise pas.
    """
    return request.path.endswith("/entity-context/switch/")
