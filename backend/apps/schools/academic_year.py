"""
apps/schools/academic_year.py — quelle est l'année de travail d'une académie.

POURQUOI CE MODULE EXISTE
-------------------------
Trois écrans posaient la même question — « quelles classes puis-je
utiliser ? » — et deux d'entre eux recevaient une réponse vide alors que
les classes existaient :

    GET /api/classes/                 →  0 classe   (listes déroulantes)
    GET /api/classes/?all_years=1     →  3 classes  (page Classes)

Même utilisateur, même académie, même instant. La liste déroulante
« Classe » d'une nouvelle salle virtuelle ne proposait que « Toute
l'école », et « Classes assignées » d'un enseignant affichait « Aucun
résultat » — pendant que la page Classes affichait French Ambassadors,
French Explorers et Junior Roots.

LA CAUSE
--------
Le filtre par défaut des listes est `school_year__is_current=True`. Il est
justifié : sans lui, une académie de trois années affiche « CP1-A » trois
fois dans chaque menu. Mais il suppose un invariant que RIEN ne garantit —
« chaque académie a exactement une année active ». Une académie dont
l'année existe sans avoir été activée (le bouton « Activer » de l'écran
Paramètres n'a jamais été cliqué) tombe donc à zéro classe, en silence.

Silence est le mot important. L'utilisateur ne voit pas « aucune année
active » : il voit un menu vide, et conclut que ses classes ont disparu.

CE QUE FAIT CE MODULE
---------------------
Il donne UNE réponse à la question, utilisée partout :

  1. l'année marquée active, si elle existe ;
  2. sinon, l'année la plus récente — celle que l'utilisateur voit et
     manipule sur la page Classes ;
  3. sinon rien, parce que l'académie n'a réellement aucune année.

Le repli (2) n'est pas une commodité : c'est ce qui distingue « aucune
année active » de « aucune classe ». Les deux situations méritent des
comportements différents, et une seule d'entre elles justifie un menu vide.

L'invariant est par ailleurs réparé à la source — voir `SchoolYear.save()`,
qui active la première année d'une académie, et la migration
`schools.0016`.
"""
from __future__ import annotations


def active_year(school):
    """
    Année de travail de `school`, ou None si l'académie n'en a aucune.

    Ne lève jamais : l'appelant décide quoi faire d'une académie sans
    année, et cette décision n'est pas la même partout.
    """
    if school is None:
        return None
    years = school.years.all()
    return (
        years.filter(is_current=True).first()
        or years.order_by("-start_date", "-id").first()
    )


def active_year_id(school):
    """Identifiant de l'année de travail, ou None."""
    year = active_year(school)
    return year.pk if year is not None else None


def has_explicit_active_year(school) -> bool:
    """
    Vrai si l'académie a une année EXPLICITEMENT activée.

    Sert à signaler l'anomalie à l'écran plutôt qu'à la corriger en
    douce : un repli silencieux qui dure devient une seconde vérité.
    """
    return school is not None and school.years.filter(is_current=True).exists()


def scope_to_active_year(queryset, school, field="school_year"):
    """
    Restreint `queryset` à l'année de travail de `school`.

    Renvoie le queryset inchangé si l'académie n'a aucune année : il n'y a
    alors rien à restreindre, et vider le résultat masquerait la vraie
    cause.
    """
    year = active_year(school)
    if year is None:
        return queryset
    return queryset.filter(**{field: year})
