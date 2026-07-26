"""
Règles de notation FEBA — SOURCE UNIQUE DE VÉRITÉ (V8).

Deux notions distinctes, longtemps confondues :

A. POIDS D'UNE ÉVALUATION (`assessment weight`)
   Depuis la V8, **toutes** les évaluations d'une matière pèsent pareil : 1,
   quel que soit leur type (devoir, interrogation, contrôle, examen, TP…).
   Exemple imposé : interrogation 12 et examen 5 → (12 + 5) / 2 = 8,5.

B. COEFFICIENT D'UNE MATIÈRE (`Subject.coefficient`)
   Inchangé : il pondère les MATIÈRES entre elles dans la moyenne générale
   (Mathématiques coeff 4 vs Arts coeff 1). Il n'a rien à voir avec (A).

Le barème d'AFFICHAGE dépend du niveau :
   - niveaux 1 à 11 (Garderie → CM2) : bulletin sur 10 ;
   - niveaux supérieurs (Collège…)   : bulletin sur 20.
Les calculs internes restent TOUJOURS sur 20 ; la conversion n'a lieu qu'une
seule fois, au moment de l'affichage.
"""
from decimal import Decimal, ROUND_HALF_UP

# (A) Poids unique de toute évaluation.
ASSESSMENT_WEIGHT = 1

# Barème de référence des calculs internes.
REFERENCE_SCALE = Decimal("20")

# (B) Cycles notés sur 10 / sur 20 — champ `Level.cycle`, indépendant de la
# numérotation choisie par l'établissement.
PRIMARY_CYCLES = frozenset({"maternelle", "primaire"})
SECONDARY_CYCLES = frozenset({"college", "collège", "lycee", "lycée"})

# Repli quand le cycle n'est pas renseigné : dernier niveau affiché sur 10
# (CM2 = 11ᵉ niveau : Garderie, Maternelle 1 et 2, CI, CP, CE1, CE2, CM1, CM2…).
PRIMARY_MAX_LEVEL_ORDER = 11


def normalize_to_reference(value, max_value=REFERENCE_SCALE):
    """Ramène une note à l'échelle interne /20 (ex. 45/50 → 18)."""
    if value is None:
        return None
    note = Decimal(str(value))
    maximum = Decimal(str(max_value or REFERENCE_SCALE))
    if maximum <= 0:
        raise ValueError(f"Barème invalide : {max_value!r}")
    if maximum == REFERENCE_SCALE:
        return note
    return note / maximum * REFERENCE_SCALE


def subject_average(values, max_values=None):
    """Moyenne d'une matière : moyenne ARITHMÉTIQUE des notes valides.

    Toutes les évaluations pèsent 1 (règle V8) : aucun type n'est privilégié.
    `values` ne doit contenir que des notes RÉELLES — une matière « non notée »
    n'envoie rien (elle ne vaut pas 0), tandis qu'un 0 réel compte bien.
    """
    notes = [v for v in (values or []) if v is not None]
    if not notes:
        return None
    if max_values:
        notes = [normalize_to_reference(v, m)
                 for v, m in zip(notes, max_values)]
    else:
        notes = [Decimal(str(v)) for v in notes]
    return sum(notes) / Decimal(len(notes))


def get_grading_scale(level):
    """Barème d'AFFICHAGE (10 ou 20) pour un niveau.

    S'appuie sur des CHAMPS STABLES de `Level`, jamais sur le libellé de la
    classe :

    1. `Level.cycle` d'abord — c'est le champ qui porte le SENS (maternelle,
       primaire, collège, lycée). Il est administrable et fiable.
    2. `Level.order` en repli, pour un établissement qui n'aurait pas
       renseigné le cycle : niveaux 1 à 11 (Garderie → CM2) → /10, au-delà
       → /20.

    `order` seul ne suffit PAS : c'est un rang d'affichage propre à chaque
    établissement (le jeu de démonstration numérote CP1 = 0 … 3ème = 9), donc
    un collège s'y retrouverait noté sur 10. Le cycle, lui, ne dépend pas de
    la numérotation choisie.

    Sans niveau identifiable, on conserve le barème de référence /20.
    """
    if level is None:
        return REFERENCE_SCALE

    cycle = getattr(level, "cycle", None)
    if cycle:
        cycle = str(cycle).strip().lower()
        if cycle in SECONDARY_CYCLES:
            return REFERENCE_SCALE
        if cycle in PRIMARY_CYCLES:
            return Decimal("10")

    order = getattr(level, "order", None)
    if order is None:
        return REFERENCE_SCALE
    try:
        order = int(order)
    except (TypeError, ValueError):
        return REFERENCE_SCALE
    if 1 <= order <= PRIMARY_MAX_LEVEL_ORDER:
        return Decimal("10")
    return REFERENCE_SCALE


def convert_average_for_scale(value, scale):
    """Convertit une moyenne interne /20 vers le barème d'affichage.

    N'est appelée QU'UNE FOIS, à l'affichage (jamais en cascade).
    """
    if value is None:
        return None
    target = Decimal(str(scale or REFERENCE_SCALE))
    converted = Decimal(str(value)) * target / REFERENCE_SCALE
    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_average(value, scale):
    """Rendu « 6.00/10 » ou « 12.00/20 » (dénominateur explicite)."""
    converted = convert_average_for_scale(value, scale)
    if converted is None:
        return "—"
    return f"{converted:.2f}/{int(Decimal(str(scale)))}"


def scale_label(scale):
    """Libellé d'en-tête : « Moy. /10 » ou « Moy. /20 »."""
    return f"Moy. /{int(Decimal(str(scale)))}"
