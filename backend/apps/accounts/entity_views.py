"""
apps/accounts/entity_views.py — Contexte d'entité et bascule Super Admin

Le contexte d'entité est déterminé EXCLUSIVEMENT par le serveur :
  - utilisateur normal → son entité de rattachement (`user.school`) ;
  - superadmin → son entité active persistée (`user.active_organization`).

Le frontend ne fait que LIRE ce contexte (`GET /entity-context/`) et
demander une bascule (`POST /entity-context/switch/`). Aucune valeur
transmise par le navigateur — localStorage, entity_id de payload, en-tête
— n'est utilisée comme source d'autorité.
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.tenancy import get_request_school
from apps.schools.models import EntitySwitchLog, OrganizationMembership, School

logger = logging.getLogger("apps")


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def serialize_entity(school):
    """Représentation publique d'une entité pour le frontend connecté."""
    if school is None:
        return None
    return {
        "id": school.id,
        "code": school.code,
        "name": school.name,
        # Étiquette courte des badges et des boutons : « FEBA French
        # Heritage Academy » ne tient ni dans une colonne de tableau ni sur
        # un bouton d'action.
        "short_name": school.short_name,
        "legal_name": school.legal_name or school.name,
        "slug": school.slug,
        "entity_type": school.entity_type,
        "timezone": school.timezone,
        "currency": school.currency_code,
        "currency_symbol": school.currency_symbol,
        "currency_decimal_places": school.currency_decimal_places,
        "default_language": school.default_language,
        "whatsapp": school.whatsapp,
        "is_active": school.is_active,
        "features": school.features,
    }


def accessible_entities(user):
    """
    Entités auxquelles l'utilisateur a réellement accès, d'après la BASE.

    - superadmin : toutes les entités actives (rôle plateforme) ;
    - autre rôle : uniquement son entité de rattachement.

    Ne jamais dériver cette liste d'une information fournie par le client.
    """
    if user.is_superadmin():
        return School.objects.filter(is_active=True).order_by("name")
    if user.school_id:
        return School.objects.filter(pk=user.school_id)
    return School.objects.none()


class EntityContextView(APIView):
    """
    GET /api/accounts/entity-context/

    Renvoie l'entité active, les entités accessibles et la matrice de
    fonctionnalités correspondante. C'est cette réponse — et elle seule —
    qui pilote l'affichage des menus conditionnels côté React.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        active = get_request_school(request)
        entities = accessible_entities(user)

        return Response({
            "active_entity": serialize_entity(active),
            "entities": [serialize_entity(s) for s in entities],
            "can_switch": bool(user.is_superadmin()),
            # Le mode « toutes les entités » n'est proposé qu'au superadmin :
            # il n'expose que les vues explicitement conçues pour être
            # consolidées (les données métier restent filtrées).
            "all_entities_mode": bool(user.is_superadmin() and active is None),
            "features": active.features if active is not None else {},
        })


class EntitySwitchView(APIView):
    """
    POST /api/accounts/entity-context/switch/  {"entity_id": <id|null>}

    Bascule l'entité active du Super Administrateur. Réservé au rôle
    superadmin : tout autre rôle reçoit 403, y compris s'il forge le
    payload. Chaque bascule est journalisée (EntitySwitchLog).

    `entity_id: null` bascule en mode « toutes les entités ».
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if not user.is_superadmin():
            # Un admin ne peut jamais changer son propre rattachement :
            # c'est précisément le vecteur d'évasion qu'on interdit.
            return Response(
                {"detail": "Seul un Super Administrateur peut changer d'entité active."},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw = request.data.get("entity_id", None)
        previous = user.active_organization

        if raw in (None, "", "all"):
            target = None
        else:
            target = School.objects.filter(pk=raw).first()
            if target is None:
                return Response(
                    {"entity_id": "Entité inconnue."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not target.is_active:
                return Response(
                    {"entity_id": "Cette entité est désactivée."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user.active_organization = target
        user.save(update_fields=["active_organization"])

        # Traçabilité : qui a basculé, depuis quelle entité, vers laquelle.
        EntitySwitchLog.objects.create(
            user=user,
            from_organization=previous,
            to_organization=target,
            ip_address=_client_ip(request),
        )
        logger.info(
            "Bascule d'entité : %s → %s (utilisateur %s)",
            previous.code if previous else "toutes",
            target.code if target else "toutes",
            user.email,
        )

        return Response({
            "active_entity": serialize_entity(target),
            "features": target.features if target is not None else {},
            # Signal explicite au frontend : purger les caches liés à
            # l'entité précédente avant de réafficher quoi que ce soit.
            "cache_invalidated": True,
        })


class EntitySwitchLogView(APIView):
    """
    GET /api/accounts/entity-context/log/ — journal des bascules.
    Réservé au superadmin.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superadmin():
            return Response(
                {"detail": "Réservé au Super Administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )
        logs = EntitySwitchLog.objects.select_related(
            "user", "from_organization", "to_organization",
        )[:200]
        return Response([
            {
                "id": entry.id,
                "user_email": entry.user.email,
                "from_entity": entry.from_organization.code if entry.from_organization else None,
                "to_entity": entry.to_organization.code if entry.to_organization else None,
                "ip_address": entry.ip_address,
                "created_at": entry.created_at,
            }
            for entry in logs
        ])


class MyMembershipsView(APIView):
    """
    GET /api/accounts/entity-context/memberships/ — appartenances de
    l'utilisateur courant (historique inclus, statut visible).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            OrganizationMembership.objects
            .filter(user=request.user)
            .select_related("organization")
        )
        return Response([
            {
                "id": m.id,
                "entity": serialize_entity(m.organization),
                "role": m.role,
                "status": m.status,
                "is_primary": m.is_primary,
                "created_at": m.created_at,
            }
            for m in memberships
        ])
