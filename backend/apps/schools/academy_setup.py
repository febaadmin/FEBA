"""
Création et initialisation d'une académie (P0 du 26/10/2026).

Une nouvelle académie part de MODÈLES DE CONFIGURATION contrôlés, jamais
d'une copie d'une académie existante : aucun élève, parent, note, paiement,
dossier ni salle virtuelle n'est créé ou recopié. Ce qui est installé :

  * le type d'académie, dont découlent `entity_type` et la matrice des
    fonctionnalités (School.DEFAULT_FEATURES) ;
  * les niveaux du type (cycles et donc barèmes /10 ou /20 corrects) —
    sauf pour une académie en ligne, dont les groupes sont propres à chaque
    programme et restent à créer ;
  * une COPIE du barème d'appréciations par défaut, propre à l'académie ;
  * facultativement, une première année scolaire (dates fournies par le
    super administrateur — jamais inventées).

L'identité visuelle reste neutre (aucune image d'une autre académie) tant
qu'aucun logo n'est téléversé et activé pour elle.
"""
from django.db import transaction

#: Niveaux initiaux par type : (nom, cycle). Modifiables ensuite dans
#: « Niveaux ». Les noms suivent le système scolaire de l'établissement
#: d'origine du groupe (Bénin).
LEVEL_TEMPLATES = {
    "physical_primary": [
        ("Maternelle 1", "maternelle"), ("Maternelle 2", "maternelle"),
        ("CI", "primaire"), ("CP", "primaire"), ("CE1", "primaire"),
        ("CE2", "primaire"), ("CM1", "primaire"), ("CM2", "primaire"),
    ],
    "physical_secondary": [
        ("6ème", "college"), ("5ème", "college"), ("4ème", "college"), ("3ème", "college"),
        ("Seconde", "lycee"), ("Première", "lycee"), ("Terminale", "lycee"),
    ],
    "online": [],
}


@transaction.atomic
def create_academy(data, *, created_by=None):
    """
    Crée l'académie décrite par `data` (validé par AcademyCreateSerializer)
    et l'initialise. Atomique : un échec ne laisse aucune académie à demi
    configurée.
    """
    from apps.grades.appreciations import install_default_rules

    from .models import Level, School, SchoolYear

    data = dict(data)
    year = {k: data.pop(k, None) for k in ("school_year_name", "school_year_start", "school_year_end")}
    academy_type = data["academy_type"]
    data.setdefault("legal_name", data["name"])
    if not data.get("matricule_prefix"):
        data["matricule_prefix"] = "".join(ch for ch in data["code"] if ch.isalnum())[:8]

    academy = School.objects.create(**data)

    levels = [
        Level(school=academy, name=name, cycle=cycle, order=order)
        for order, (name, cycle) in enumerate(LEVEL_TEMPLATES[academy_type], start=1)
    ]
    Level.objects.bulk_create(levels)
    install_default_rules(academy, user=created_by)

    if year["school_year_name"]:
        SchoolYear.objects.create(
            school=academy, name=year["school_year_name"],
            start_date=year["school_year_start"], end_date=year["school_year_end"],
            is_current=True,
        )
    return academy


def setup_status(academy):
    """
    Ce qui reste à faire pour que l'académie soit utilisable, d'après la
    BASE (jamais d'après un état d'interface).
    """
    from apps.accounts.models import CustomUser
    from apps.classes.models import Class
    from apps.grades.appreciations import validate_scale
    from apps.subjects.models import Subject

    from .models import SchoolBranding, SchoolYear

    rules = list(academy.appreciation_rules.filter(cycle="").values(
        "min_percent", "label_fr", "label_en", "is_active"))
    checks = [
        ("academy_type", "Type d'académie défini", bool(academy.academy_type),
         "Choisir le type dans « Académies »."),
        ("school_year", "Année scolaire active",
         SchoolYear.objects.filter(school=academy, is_current=True).exists(),
         "Créer l'année dans « Paramètres »."),
        ("levels", "Niveaux", academy.levels.exists(), "Créer les niveaux dans « Niveaux »."),
        ("subjects", "Matières", Subject.objects.filter(school=academy).exists(),
         "Créer les matières dans « Matières »."),
        ("classes", "Classes",
         Class.objects.filter(school_year__school=academy).exists(),
         "Créer les classes dans « Classes »."),
        ("admin", "Administrateur de l'académie",
         CustomUser.objects.filter(school=academy, role="admin", is_active=True).exists(),
         "Créer un administrateur dans « Administrateurs »."),
        ("appreciations", "Barème d'appréciations valide",
         bool(rules) and not validate_scale(rules),
         "Vérifier le barème dans « Appréciations »."),
        ("logo", "Logo activé",
         SchoolBranding.objects.filter(school=academy, is_active=True).exists(),
         "Téléverser et activer le logo dans « Branding & Logo » (sinon : aucun logo, "
         "jamais celui d'une autre académie)."),
    ]
    return {
        "academy_id": academy.pk,
        "ready": all(done for _, _, done, _ in checks if _ != "logo"),
        "checks": [
            {"key": key, "label": label, "done": done, "action": "" if done else action}
            for key, label, done, action in checks
        ],
    }
