"""
Filtrage portable des annonces par rôle destinataire.

`target_roles` est un JSONField contenant une liste de rôles
(ex. ["student", "parent"] ou ["all"]). Le lookup `__contains` sur JSONField
n'est supporté que par PostgreSQL ; sur SQLite (suite de tests, CI légère),
il lève NotSupportedError. Ce helper choisit la stratégie selon le backend :

 - PostgreSQL : `target_roles__contains=[role]` (index GIN possible).
 - Autres     : cast texte + recherche de la valeur JSON exacte `"role"`.
   Les rôles étant des identifiants simples sans guillemets internes, la
   présence des guillemets dans le motif exclut tout faux positif
   (« "admin" » ne matche pas « "superadmin" »).
"""
from django.db import connection
from django.db.models import Q, TextField
from django.db.models.functions import Cast


def filter_targets_role(qs, role):
    """Restreint `qs` aux annonces ciblant `role` ou « all »."""
    if connection.vendor == "postgresql":
        return qs.filter(
            Q(target_roles__contains=[role]) | Q(target_roles__contains=["all"])
        )
    return qs.annotate(
        _roles_text=Cast("target_roles", TextField())
    ).filter(
        Q(_roles_text__contains=f'"{role}"') | Q(_roles_text__contains='"all"')
    )
