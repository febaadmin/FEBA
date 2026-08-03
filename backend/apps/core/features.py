"""
apps/core/features.py — Matrice de fonctionnalités par entité (côté serveur)

PRINCIPE
--------
Chaque entité (`schools.School`) expose une matrice de drapeaux
(`School.features`). Certaines fonctionnalités n'ont aucun sens pour une
école présentielle : FEBA Cotonou n'a pas de salle virtuelle, pas de
visioconférence, pas de test de placement en ligne. FEBA French Heritage
Academy, académie 100 % en ligne, les a toutes.

RÈGLE DE SÉCURITÉ
-----------------
Masquer une entrée de menu dans React NE PROTÈGE RIEN : l'utilisateur peut
appeler l'API directement. Toute vue exposant une fonctionnalité
conditionnelle DOIT donc porter `required_feature = "<flag>"` et la
permission `HasEntityFeature`, qui renvoie 403 lorsque l'entité courante
n'a pas le droit.

Le Super Administrateur n'échappe PAS à la règle lorsqu'il a sélectionné
une entité : s'il consulte FEBA, il ne peut pas créer de salle virtuelle
FEBA. En revanche, sans entité sélectionnée (mode plateforme), la
vérification ne s'applique pas — il n'y a alors aucune entité à violer.
"""
from rest_framework import permissions

from apps.core.tenancy import get_request_school


def entity_features(school):
    """Matrice de fonctionnalités d'une entité (dict flag -> bool)."""
    if school is None:
        return {}
    return school.features


def entity_has_feature(school, flag):
    """True si l'entité peut utiliser `flag`. None (pas d'entité) => False."""
    if school is None:
        return False
    return school.has_feature(flag)


class HasEntityFeature(permissions.BasePermission):
    """
    Refuse l'accès à une vue dont la fonctionnalité n'est pas activée pour
    l'entité courante.

    Usage sur un ViewSet :

        class VirtualClassroomViewSet(TenantScopedQuerySetMixin, ModelViewSet):
            required_feature = "virtual_classrooms"
            permission_classes = [IsAuthenticated, HasEntityFeature, ...]

    Si la vue ne déclare pas `required_feature`, la permission laisse
    passer (aucune restriction n'est demandée).
    """
    message = "Cette fonctionnalité n'est pas activée pour votre entité."

    def has_permission(self, request, view):
        flag = getattr(view, "required_feature", None)
        if not flag:
            return True

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False

        school = get_request_school(request)
        if school is None:
            # Superadmin en mode plateforme (aucune entité sélectionnée) :
            # pas d'entité à protéger, le filtrage de queryset renvoie déjà
            # un ensemble vide pour les données métier.
            return bool(user.is_superadmin())

        return entity_has_feature(school, flag)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
