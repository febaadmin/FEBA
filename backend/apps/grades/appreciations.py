"""
Barème d'appréciations — SOURCE UNIQUE (P0 du 26/10/2026).

Avant : les seuils et les libellés étaient codés en dur dans
`apps.grades.models.APPRECIATION_SCALE` (et recopiés côté React). Ils sont
désormais des données par académie (`AppreciationRule`), administrées
depuis l'écran « Appréciations ». Ce module est le seul à les lire.

Règle de calcul (documentée dans AppreciationRule) : seuil bas inclusif en
POURCENTAGE de la note maximale. Comparaison faite sans division
(n × 100 ≥ seuil × m) : aucune erreur d'arrondi à une borne.

Résolution du barème d'une note :
  1. paliers actifs de l'académie pour le CYCLE du niveau, s'il en existe ;
  2. sinon paliers actifs de l'académie « tous cycles » ;
  3. sinon le barème historique (DEFAULT_SCALE) — académie créée hors de
     l'écran « Académies » et jamais configurée : comportement inchangé.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction

#: Libellés anglais historiques (frontend/src/i18n/translations.js).
_EN = {
    'EXCELLENT': 'EXCELLENT',
    'TRÈS SATISFAISANT': 'VERY SATISFACTORY',
    'SATISFAISANT': 'SATISFACTORY',
    'ACCEPTABLE': 'ACCEPTABLE',
    'PEUT MIEUX FAIRE': 'CAN DO BETTER',
    'INSUFFISANT': 'INSUFFICIENT',
    'TRÈS INSUFFISANT': 'VERY INSUFFICIENT',
    'FAIBLE': 'WEAK',
    'TRÈS FAIBLE': 'VERY WEAK',
}

HUNDRED = Decimal('100')
CYCLES = ('maternelle', 'primaire', 'college', 'lycee')


def _default_scale():
    """Barème historique (seuils /20) converti en pourcentages : 19 → 95 %."""
    from .models import APPRECIATION_SCALE

    return [
        (threshold * Decimal('5'), label, _EN.get(label, ''))
        for threshold, label in APPRECIATION_SCALE
    ]


DEFAULT_SCALE = _default_scale()


def _rules_for(school, cycle, cache=None):
    """Paliers actifs (seuil décroissant) pour une académie et un cycle."""
    if school is None:
        return DEFAULT_SCALE
    key = (school.pk, cycle or '')
    if cache is not None and key in cache:
        return cache[key]
    from .models import AppreciationRule

    rows = list(
        AppreciationRule.objects.filter(school_id=school.pk, is_active=True,
                                        cycle__in={cycle or '', ''})
        .order_by('-min_percent')
        .values_list('cycle', 'min_percent', 'label_fr', 'label_en')
    )
    specific = [(p, fr, en) for c, p, fr, en in rows if cycle and c == cycle]
    general = [(p, fr, en) for c, p, fr, en in rows if c == '']
    scale = specific or general or DEFAULT_SCALE
    if cache is not None:
        cache[key] = scale
    return scale


def effective_scale(school, cycle=None, cache=None):
    """Barème effectivement appliqué, et sa provenance (pour l'écran)."""
    scale = _rules_for(school, cycle, cache)
    if scale is DEFAULT_SCALE:
        origin = 'default'
    elif cycle and school is not None and school.appreciation_rules.filter(
            cycle=cycle, is_active=True).exists():
        origin = 'cycle'
    else:
        origin = 'academy'
    return scale, origin


def appreciation_for(value, max_value=20, *, academy=None, cycle=None,
                     language='fr', cache=None):
    """
    Appréciation d'une note `value` sur `max_value`.

    None → « — » (une matière non notée n'a pas d'appréciation). Une note
    négative, supérieure au barème ou un barème nul lèvent ValueError : une
    donnée invalide est refusée, jamais traduite en appréciation trompeuse.
    """
    if value is None:
        return '—'
    try:
        v = Decimal(str(value))
        m = Decimal(str(max_value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'Note ou barème non numérique : {value!r} / {max_value!r}')
    if m <= 0:
        raise ValueError(f'Barème invalide : {max_value!r} (doit être strictement positif)')
    if v < 0:
        raise ValueError(f'Note négative : {value!r}')
    if v > m:
        raise ValueError(f'Note {value!r} supérieure au barème {max_value!r}')
    scale = _rules_for(academy, cycle, cache)
    for min_percent, label_fr, label_en in scale:
        if v * HUNDRED >= Decimal(min_percent) * m:
            return (label_en or label_fr) if language == 'en' else label_fr
    # Inatteignable avec un barème valide (palier à 0 %) ; le barème par
    # défaut sert de filet si une configuration incomplète a été forcée en base.
    return DEFAULT_SCALE[-1][2 if language == 'en' else 1]


def cycle_of_class(student_class):
    level = getattr(student_class, 'level', None) if student_class is not None else None
    cycle = getattr(level, 'cycle', None)
    return cycle if cycle in CYCLES else None


# ── Validation et enregistrement d'un barème complet ────────────────────────

def validate_scale(rows):
    """
    Contrôle un barème COMPLET (liste de dicts min_percent / label_fr /
    label_en / is_active). Retourne la liste des erreurs, vide si valide.

    Le barème est validé en entier, jamais palier par palier : modifier deux
    seuils l'un après l'autre ferait passer par un état incohérent.
    """
    errors = []
    active = []
    for index, row in enumerate(rows, start=1):
        label = str(row.get('label_fr') or '').strip()
        try:
            percent = Decimal(str(row.get('min_percent')))
        except (InvalidOperation, ValueError, TypeError):
            errors.append(f"Ligne {index} : seuil invalide ({row.get('min_percent')!r}).")
            continue
        if percent.is_nan() or percent < 0 or percent > 100:
            errors.append(f"Ligne {index} : le seuil doit être compris entre 0 et 100 %.")
        if percent != percent.quantize(Decimal('0.01')):
            errors.append(f"Ligne {index} : deux décimales au plus pour le seuil.")
        if row.get('is_active', True):
            if not label:
                errors.append(f"Ligne {index} : le libellé français d'une appréciation active est obligatoire.")
            active.append((percent, label.upper(), index))
    if not active:
        errors.append("Le barème doit comporter au moins une appréciation active.")
        return errors
    seen_percent, seen_label = {}, {}
    for percent, label, index in active:
        if percent in seen_percent:
            errors.append(
                f"Lignes {seen_percent[percent]} et {index} : deux appréciations actives ont le même "
                f"seuil ({percent} %) : une note à ce seuil aurait deux appréciations.")
        seen_percent.setdefault(percent, index)
        if label and label in seen_label:
            errors.append(f"Lignes {seen_label[label]} et {index} : libellé « {label} » en double.")
        seen_label.setdefault(label, index)
    if min(p for p, _, _ in active) != 0:
        errors.append(
            "Le seuil le plus bas doit valoir 0 % : sinon les notes les plus faibles "
            "n'auraient aucune appréciation.")
    return errors


def label_usage(school, label):
    """Nombre de bulletins de CETTE académie portant ce libellé."""
    from apps.bulletins.models import Bulletin

    return Bulletin.objects.filter(student__school=school, appreciation=label).count()


class ScaleError(Exception):
    def __init__(self, errors, status=400):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.status = status


@transaction.atomic
def save_scale(school, cycle, rows, user=None):
    """
    Remplace atomiquement le barème (académie, cycle) par `rows`.

    Une ligne portant un `id` met à jour ce palier (qui doit appartenir à ce
    barème) ; sans `id`, un palier est créé ; un palier absent de `rows` est
    supprimé — sauf s'il figure sur des bulletins déjà émis (409) : il faut
    alors le désactiver, pour que l'historique garde son sens.
    """
    from .models import AppreciationRule

    cycle = cycle or ''
    if cycle and cycle not in CYCLES:
        raise ScaleError([f"Cycle inconnu : {cycle!r}."])
    errors = validate_scale(rows)
    if errors:
        raise ScaleError(errors)

    existing = {r.pk: r for r in AppreciationRule.objects.select_for_update()
                .filter(school=school, cycle=cycle)}
    kept_ids = set()
    for row in rows:
        rid = row.get('id')
        if rid is not None:
            try:
                rid = int(rid)
            except (TypeError, ValueError):
                raise ScaleError([f"Identifiant de palier invalide : {row.get('id')!r}."])
            if rid not in existing:
                # Identifiant d'un autre barème — ou d'une autre académie.
                raise ScaleError([f"Le palier {rid} n'appartient pas à ce barème."], status=404)
            kept_ids.add(rid)

    removed = [r for pk, r in existing.items() if pk not in kept_ids]
    blocked = [(r, label_usage(school, r.label_fr)) for r in removed]
    blocked = [(r, n) for r, n in blocked if n]
    if blocked:
        raise ScaleError([
            f"« {r.label_fr} » figure sur {n} bulletin(s) déjà émis : désactivez-la au lieu "
            "de la supprimer, pour que ces bulletins gardent leur signification."
            for r, n in blocked
        ], status=409)

    # Ordre des écritures : suppressions et désactivations d'abord, pour que
    # la contrainte d'unicité des seuils actifs ne voie jamais d'état
    # intermédiaire (un seuil libéré puis repris par une autre ligne).
    AppreciationRule.objects.filter(pk__in=[r.pk for r in removed]).delete()
    AppreciationRule.objects.filter(pk__in=kept_ids).update(is_active=False)
    for row in rows:
        values = dict(
            min_percent=Decimal(str(row['min_percent'])),
            label_fr=str(row.get('label_fr') or '').strip(),
            label_en=str(row.get('label_en') or '').strip(),
            is_active=bool(row.get('is_active', True)),
            updated_by=user,
        )
        if row.get('id') is not None:
            rule = existing[int(row['id'])]
            for key, val in values.items():
                setattr(rule, key, val)
            rule.save()
        else:
            AppreciationRule.objects.create(school=school, cycle=cycle, **values)
    return list(AppreciationRule.objects.filter(school=school, cycle=cycle)
                .order_by('-is_active', '-min_percent'))


def install_default_rules(school, user=None):
    """
    Copie le barème par défaut dans l'académie (portée « tous cycles »).
    Idempotent : ne touche pas une académie qui a déjà son barème.
    """
    from .models import AppreciationRule

    if AppreciationRule.objects.filter(school=school, cycle='').exists():
        return False
    AppreciationRule.objects.bulk_create([
        AppreciationRule(school=school, cycle='', min_percent=p, label_fr=fr,
                         label_en=en, updated_by=user)
        for p, fr, en in DEFAULT_SCALE
    ])
    return True


@transaction.atomic
def reset_to_defaults(school, cycle='', user=None):
    """
    Rétablit le barème par défaut pour (académie, cycle). Pour un cycle,
    « rétablir » = supprimer la surcharge : le barème de l'académie
    s'applique de nouveau. Les paliers utilisés par des bulletins ne sont
    pas supprimés mais désactivés.
    """
    from .models import AppreciationRule

    rules = list(AppreciationRule.objects.select_for_update().filter(school=school, cycle=cycle or ''))
    for rule in rules:
        if label_usage(school, rule.label_fr):
            if rule.is_active:
                rule.is_active = False
                rule.updated_by = user
                rule.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        else:
            rule.delete()
    if not cycle:
        AppreciationRule.objects.bulk_create([
            AppreciationRule(school=school, cycle='', min_percent=p, label_fr=fr,
                             label_en=en, updated_by=user)
            for p, fr, en in DEFAULT_SCALE
        ])
