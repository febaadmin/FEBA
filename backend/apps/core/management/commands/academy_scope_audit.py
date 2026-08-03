"""
Audit global — quelles vues laissent passer une autre académie ?

CE QUE CETTE COMMANDE CHERCHE
-----------------------------
Un ViewSet qui expose un modèle rattaché à une académie et dont le
`get_queryset()` ne mentionne NI l'académie, NI l'utilisateur. Une telle
vue renvoie la table entière : les élèves de Cotonou apparaissent à
l'administrateur de l'académie en ligne, et l'identifiant d'un dossier
d'une autre académie devient exploitable à la main.

POURQUOI UNE COMMANDE PLUTÔT QU'UN TEST
---------------------------------------
Un test vérifie les vues qu'on a pensé à lui donner. Cette commande part
du ROUTEUR : elle voit toutes les vues, y compris celle qu'on ajoutera
la semaine prochaine sans écrire de test. Elle est appelée par un test
(`test_academy_scope_audit.py`) qui échoue dès qu'une vue non couverte
apparaît, et la liste des exemptions doit être MOTIVÉE.

Ce n'est pas une preuve de sécurité — c'est un filet. Une vue peut
mentionner « school » et filtrer de travers. Mais une vue qui ne le
mentionne pas du tout ne filtre certainement rien.
"""
import inspect

from django.core.management.base import BaseCommand

#: Vues volontairement non filtrées, avec la raison. Une entrée sans
#: raison écrite est une omission oubliée, pas un choix.
EXEMPTIONS = {
    "AdminSiteSettingsView":
        "Réglages du site vitrine : une seule instance pour le groupe.",
    "AdminHeroSlideViewSet":
        "Carrousel public du groupe, commun aux deux académies.",
    "AdminNewsViewSet":
        "Actualités publiques du groupe.",
    "AdminGalleryAlbumViewSet":
        "Galerie publique du groupe.",
    "AdminGalleryItemViewSet":
        "Galerie publique du groupe.",
    "PublicSettingsView":
        "Endpoint public en lecture seule.",
    "PublicHeroSlidesView":
        "Endpoint public en lecture seule.",
    "PublicNewsListView":
        "Endpoint public en lecture seule.",
    "PublicNewsDetailView":
        "Endpoint public en lecture seule.",
    "PublicGalleryView":
        "Endpoint public en lecture seule.",
    "TechnicalIncidentViewSet":
        "Réservé au super administrateur (`IsSuperAdmin`). Un incident "
        "technique décrit une panne d'infrastructure, pas le dossier d'un "
        "élève : le masquer selon l'académie affichée empêcherait de voir "
        "qu'un serveur tombe. Le filtre `school` reste disponible pour "
        "restreindre la vue à la demande.",
}

#: Marqueurs acceptés comme preuve qu'une portée est appliquée.
MARQUEURS = (
    "get_request_school", "request.user", "self.request.user",
    "school=", "school_id", "academy=", "academy_id", "entity=",
    "entity_id", "for_user", "scoped", "none()",
)


def _vues_du_routeur():
    """Toutes les classes de vues atteignables depuis la configuration."""
    from django.urls import get_resolver

    trouvees = {}

    def parcourir(resolver, prefixe=""):
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):
                parcourir(pattern, prefixe + str(pattern.pattern))
                continue
            callback = getattr(pattern, "callback", None)
            classe = getattr(callback, "cls", None) or getattr(
                callback, "view_class", None)
            if classe is not None:
                trouvees.setdefault(classe, prefixe + str(pattern.pattern))

    parcourir(get_resolver())
    return trouvees


def analyser():
    """Renvoie (problemes, examinees, exemptees)."""
    from django.db import models

    problemes = []
    examinees = 0
    exemptees = 0

    for classe, chemin in sorted(_vues_du_routeur().items(),
                                 key=lambda kv: kv[0].__name__):
        nom = classe.__name__
        if nom in EXEMPTIONS:
            exemptees += 1
            continue
        if not hasattr(classe, "get_queryset") and not hasattr(classe, "queryset"):
            continue

        # Le modèle exposé est-il rattaché à une académie ?
        modele = None
        queryset = getattr(classe, "queryset", None)
        if queryset is not None:
            modele = queryset.model
        else:
            serializer = getattr(classe, "serializer_class", None)
            meta = getattr(serializer, "Meta", None)
            modele = getattr(meta, "model", None)
        if modele is None:
            continue

        champs = {f.name for f in modele._meta.get_fields()
                  if isinstance(f, models.Field)}
        if not champs & {"school", "academy", "entity"}:
            continue

        examinees += 1
        try:
            source = inspect.getsource(classe)
        except (OSError, TypeError):  # pragma: no cover
            continue
        if not any(marqueur in source for marqueur in MARQUEURS):
            problemes.append({
                "vue": nom,
                "modele": modele.__name__,
                "chemin": chemin,
                "motif": ("expose un modèle rattaché à une académie sans "
                          "aucune restriction visible"),
            })

    return problemes, examinees, exemptees


class Command(BaseCommand):
    help = "Repère les vues qui exposent un modèle d'académie sans filtrage."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true",
                            help="Sort en erreur si un problème est trouvé.")

    def handle(self, *args, **options):
        problemes, examinees, exemptees = analyser()

        self.stdout.write(
            f"{examinees} vue(s) examinée(s), {exemptees} exemptée(s) avec "
            f"motif écrit.")
        for probleme in problemes:
            self.stdout.write(self.style.ERROR(
                f"  ✗ {probleme['vue']} ({probleme['modele']}) — "
                f"{probleme['motif']}\n     route : {probleme['chemin']}"))

        if not problemes:
            self.stdout.write(self.style.SUCCESS(
                "Aucune vue n'expose un modèle d'académie sans restriction."))
        elif options["strict"]:
            raise SystemExit(1)
