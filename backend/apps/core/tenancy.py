"""
apps/core/tenancy.py — Isolation multi-établissements (multi-tenant SaaS)

STRATÉGIE RETENUE
------------------
Base de données partagée, schéma partagé : chaque enregistrement métier
est rattaché — directement ou par relation — à un établissement
(`schools.School`, qui joue le rôle de "tenant").

L'isolation est appliquée explicitement au niveau de la couche API
(ViewSets DRF), via un filtrage de queryset + une vérification
d'object-permission, plutôt que via un état global "thread-local"
implicite. C'est un choix volontaire : cette application utilise Celery
(tâches asynchrones) et Channels (WebSocket), deux contextes où une
variable thread-locale posée par un middleware HTTP classique n'existe
plus — elle donnerait une fausse impression de sécurité. Le filtrage
explicite, lui, fonctionne partout car il dépend uniquement de l'objet
`request.user` (HTTP) ou d'un argument explicite (tâches Celery).

RÈGLES
------
- Un utilisateur non-superadmin DOIT appartenir à un établissement
  (`CustomUser.school`). Toutes les requêtes API sont filtrées par cet
  établissement : un administrateur, enseignant, parent ou élève d'un
  établissement ne peut jamais voir ni modifier les données d'un autre
  établissement, quel que soit l'endpoint utilisé.
- Le rôle `superadmin` est un rôle "plateforme" : il gère les
  établissements eux-mêmes (création, activation, abonnement) et peut,
  ponctuellement, consulter les données d'un établissement précis via
  `?school_id=<id>` (utile pour le support client) — mais voit une liste
  vide tant qu'il ne précise pas d'établissement, plutôt que de
  recevoir par défaut toutes les données de tous les clients.
"""
from rest_framework import permissions, serializers


def get_request_school(request):
    """
    Retourne l'établissement (tenant) courant pour cette requête, ou None.

    - Utilisateur normal (admin/teacher/parent/student) : son `school` assigné.
    - Superadmin : `school_id` explicite en query param, sinon None (vue
      plateforme globale, non filtrée — utilisée uniquement par les vues
      de gestion des tenants elles-mêmes).
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    if user.is_superadmin():
        # Ordre de priorité pour un superadmin :
        #   1. `?school_id=` explicite (consultation ponctuelle, support) ;
        #   2. entité active PERSISTÉE EN BASE (bascule via l'endpoint dédié) ;
        #   3. None → mode plateforme « toutes les entités ».
        #
        # Le frontend n'a AUCUN moyen d'imposer une entité autrement : il
        # n'existe pas de lecture d'un `entity_id` de payload ni de
        # localStorage ici. La bascule passe obligatoirement par
        # /api/accounts/entity-context/switch/ qui vérifie l'appartenance
        # et journalise l'opération.
        school_id = None
        if hasattr(request, "query_params"):
            school_id = request.query_params.get("school_id")
        if school_id:
            from apps.schools.models import School
            return School.objects.filter(pk=school_id).first()
        return getattr(user, "active_organization", None)

    # Utilisateur normal : son entité de rattachement, toujours. Un
    # `?school_id=` ou un `entity_id` envoyé par le client est simplement
    # IGNORÉ — il ne peut pas élargir la portée de ses droits.
    return getattr(user, "school", None)


def current_school_years(school):
    """
    Années scolaires actives correspondant à la portée courante.

    PROBLÈME RÉSOLU (P2)
    --------------------
    Le filtre « année courante » s'écrivait partout
    `SchoolYear.objects.filter(school=school, is_current=True).first()`.
    En mode « Toutes les Académies », `school` vaut None : le filtre
    retournait `None` et était donc SILENCIEUSEMENT ABANDONNÉ. Résultat,
    la vue consolidée mélangeait les trois années d'historique alors que
    chaque académie n'affichait que l'année en cours — d'où des totaux qui
    ne correspondaient à rien (270 paiements « toutes académies » pour 90
    à FEBA et 0 à FEBA FHA).

    Renvoyer un QUERYSET plutôt qu'un seul objet règle le cas : en mode
    consolidé, on filtre sur l'année courante de CHAQUE académie.

    Usage :

        annees = current_school_years(school)
        if annees.exists():
            qs = qs.filter(school_year__in=annees)

    Le garde `exists()` conserve le comportement historique : sans année
    courante déclarée, on n'applique aucun filtre plutôt que de masquer
    toutes les données.
    """
    from apps.schools.models import SchoolYear

    years = SchoolYear.objects.filter(is_current=True)
    if school is not None:
        years = years.filter(school=school)
    return years


class TenantScopedQuerySetMixin:
    """
    Mixin pour ViewSet / generic view DRF : filtre automatiquement le
    queryset par établissement courant.

    Attribut `tenant_lookup` : chemin ORM depuis le modèle de la vue
    jusqu'au champ `school` d'un établissement.
    Exemples : "school", "student__school", "cls__school_year__school".

    `tenant_optional = True` permet à un superadmin sans `school_id`
    précisé de voir toutes les données (utilisé par les vues plateforme
    qui doivent lister des objets cross-tenant, ex: gestion des écoles).
    Par défaut (`False`) : un superadmin sans `school_id` voit un
    queryset vide pour les données métier d'un établissement — évite
    qu'une vue élève/note/paiement etc. expose accidentellement toutes
    les écoles par défaut.
    """
    tenant_lookup = "school"
    tenant_optional = False

    def get_tenant_school(self):
        return get_request_school(self.request)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        school = self.get_tenant_school()

        if school is None:
            if user.is_superadmin() and self.tenant_optional:
                return qs
            if user.is_superadmin():
                return qs.none()
            # Utilisateur non-superadmin sans établissement assigné :
            # compte mal configuré, on ne lui montre rien plutôt que
            # de planter ou de fuiter des données d'un autre tenant.
            return qs.none()

        lookup = {self.tenant_lookup: school}
        return qs.filter(**lookup)


class IsSameTenant(permissions.BasePermission):
    """
    Permission objet : bloque toute opération (lecture détail, update,
    delete) sur un objet n'appartenant pas à l'établissement courant.
    Complète `TenantScopedQuerySetMixin` (qui protège les listes) pour
    les accès directs par identifiant (`/api/xxx/<id>/`).
    """
    message = "Cette ressource appartient à un autre établissement."

    def has_object_permission(self, request, view, obj):
        school = get_request_school(request)
        if school is None:
            return bool(request.user.is_authenticated and request.user.is_superadmin())

        lookup = getattr(view, "tenant_lookup", "school")
        obj_school = obj
        try:
            for part in lookup.split("__"):
                obj_school = getattr(obj_school, part)
                if obj_school is None:
                    break
        except AttributeError:
            obj_school = None

        return obj_school == school


def assert_same_tenant(value_school, request, field_name="ressource"):
    """
    Helper pour les serializers : à appeler dans `validate_<field>()`
    quand on reçoit l'ID d'une ressource liée (classe, matière, année
    scolaire, élève...) pour empêcher un utilisateur de rattacher une
    donnée à une ressource d'un autre établissement.
    """
    school = get_request_school(request)
    if school is not None and value_school is not None and value_school != school:
        raise serializers.ValidationError(
            f"Ce(tte) {field_name} appartient à un autre établissement."
        )


def require_school_or_403(user):
    """
    À utiliser dans les vues non basées sur le mixin (APIView simples).
    Lève une erreur explicite si un utilisateur non-superadmin n'a pas
    d'établissement assigné, plutôt que de planter plus loin avec une
    AttributeError peu compréhensible.
    """
    from rest_framework.exceptions import PermissionDenied
    if not user.is_superadmin() and getattr(user, "school", None) is None:
        raise PermissionDenied(
            "Votre compte n'est rattaché à aucun établissement. "
            "Contactez votre administrateur."
        )
