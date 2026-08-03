"""
apps/core/academy_serializers.py — Métadonnées d'académie sur les objets

PROBLÈME RÉSOLU (P3)
--------------------
En mode « Toutes les Académies », les listes renvoyaient bien l'union des
deux académies, mais chaque objet n'exposait qu'un identifiant brut
(`school: 3`). L'interface ne pouvait donc PAS indiquer à quelle académie
une ligne appartenait : classes, années scolaires, matières et
utilisateurs apparaissaient mélangés sans aucun moyen de les distinguer.

Ce mixin ajoute trois champs en lecture seule à tout serializer d'un
modèle rattaché à une académie :

    academy_id    identifiant technique
    academy_code  code interne STABLE (FEBA / FEBA_FHA)
    academy_name  nom affichable ("Faith & Excellence…", "FEBA French…")

`academy_code` est la valeur sur laquelle le frontend s'appuie pour
choisir un badge : il ne change pas si l'administration renomme
l'académie.

CHEMIN D'ACCÈS
--------------
Tous les modèles n'ont pas un champ `school` direct. `academy_source`
déclare le chemin ORM à suivre :

    academy_source = "school"                       # Student, Class…
    academy_source = "user.school"                  # Teacher, Parent
    academy_source = "school_year.school"           # Class
    academy_source = "entity"                       # ContactMessage…

La résolution est tolérante : un maillon nul renvoie simplement `None`
plutôt que de faire échouer toute la sérialisation.
"""
from rest_framework import serializers


def resolve_academy(instance, path):
    """
    Suit `path` (ex. « school_year.school ») depuis `instance`.
    Retourne l'académie ou None si un maillon manque.
    """
    current = instance
    for part in path.split("."):
        if current is None:
            return None
        current = getattr(current, part, None)
    return current


class AcademyMetadataMixin(serializers.Serializer):
    """
    Ajoute `academy_id`, `academy_code` et `academy_name` en lecture seule.

    À combiner avec un ModelSerializer :

        class StudentSerializer(AcademyMetadataMixin, ModelSerializer):
            academy_source = "school"

    Pensez à ajouter les trois champs à `Meta.fields` si celui-ci est une
    liste explicite (inutile avec `fields = "__all__"`).
    """
    #: Chemin ORM vers l'académie. Surchargeable par serializer.
    academy_source = "school"

    academy_id = serializers.SerializerMethodField()
    academy_code = serializers.SerializerMethodField()
    academy_name = serializers.SerializerMethodField()
    academy_short_name = serializers.SerializerMethodField()

    def _academy(self, obj):
        return resolve_academy(obj, getattr(self, "academy_source", "school"))

    def get_academy_id(self, obj):
        academy = self._academy(obj)
        return academy.id if academy is not None else None

    def get_academy_code(self, obj):
        academy = self._academy(obj)
        return academy.code if academy is not None else None

    def get_academy_name(self, obj):
        academy = self._academy(obj)
        if academy is None:
            return None
        return academy.name

    def get_academy_short_name(self, obj):
        """
        Étiquette courte pour les tableaux et les exports.

        « FEBA French Heritage Academy » ne tient pas dans une colonne :
        sans version courte, l'interface tronquait le nom au point de
        rendre les deux académies indiscernables (« FEBA Fren… » contre
        « FEBA »).
        """
        academy = self._academy(obj)
        return academy.short_name if academy is not None else None


#: Champs à ajouter à un `Meta.fields` explicite.
ACADEMY_FIELDS = ["academy_id", "academy_code", "academy_name", "academy_short_name"]
