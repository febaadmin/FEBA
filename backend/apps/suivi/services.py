"""
Calculs du suivi. Aucune valeur n'est inventée : une rubrique sans donnée le dit
(`has_data: False`), et la progression n'utilise que des données existantes.

Progression générale (voir docs/SUIVI_PEDAGOGIQUE.md) : moyenne pondérée, sur les
seules composantes disponibles, de
  - la maîtrise : rang moyen du dernier niveau validé par compétence, ramené à 0-100 ;
  - les évaluations pédagogiques : moyenne des scores en pourcentage ;
  - les objectifs : part des objectifs atteints parmi ceux qui sont clos ou échus.
Les notes historiques n'y entrent pas : elles sont affichées à part, avec leur origine.
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q

from apps.attendance.models import Attendance
from apps.grades.models import Grade

from .models import (
    NIVEAUX_PAR_DEFAUT,
    EvaluationCompetence,
    EvaluationPedagogique,
    NiveauMaitrise,
    Objectif,
    ObservationParticipation,
    ParametresSuivi,
    PlanAccompagnement,
)

ORIGINE_HISTORIQUE = "notes_historiques"
ORIGINE_SUIVI = "suivi_pedagogique"
ORIGINE_EXAMEN = "examens_en_ligne"


def assurer_niveaux(school):
    """Crée les quatre niveaux par défaut d'une académie qui n'en a aucun."""
    if not NiveauMaitrise.objects.filter(school=school).exists():
        with transaction.atomic():
            for code, libelle, libelle_en, rang, couleur in NIVEAUX_PAR_DEFAUT:
                NiveauMaitrise.objects.get_or_create(
                    school=school, code=code,
                    defaults={"libelle": libelle, "libelle_en": libelle_en, "rang": rang, "couleur": couleur})
    return NiveauMaitrise.objects.filter(school=school)


def parametres(school):
    return ParametresSuivi.objects.get_or_create(school=school)[0]


def _dans_periode(qs, champ, du, au):
    if du:
        qs = qs.filter(**{f"{champ}__gte": du})
    if au:
        qs = qs.filter(**{f"{champ}__lte": au})
    return qs


def etat_competences(student, du=None, au=None, subject=None):
    """Dernier niveau validé par compétence, précédent niveau et tendance."""
    qs = EvaluationCompetence.objects.filter(student=student, statut=EvaluationCompetence.VALIDEE).select_related(
        "competence", "niveau").order_by("competence_id", "-date_evaluation", "-id")
    qs = _dans_periode(qs, "date_evaluation", du, au)
    if subject:
        qs = qs.filter(Q(competence__subject_id=subject) | Q(competence__referentiel__subject_id=subject))
    par_competence = defaultdict(list)
    for ev in qs:
        par_competence[ev.competence_id].append(ev)
    rang_max = max(NiveauMaitrise.objects.filter(school=student.school).values_list("rang", flat=True), default=0)
    lignes = []
    for evals in par_competence.values():
        actuel = evals[0]
        precedent = evals[1] if len(evals) > 1 else None
        if precedent is None:
            tendance = "premiere"
        elif actuel.niveau.rang > precedent.niveau.rang:
            tendance = "progresse"
        elif actuel.niveau.rang < precedent.niveau.rang:
            tendance = "regresse"
        else:
            tendance = "stagne"
        lignes.append({
            "competence": actuel.competence_id, "nom": actuel.competence.nom, "nom_en": actuel.competence.nom_en,
            "domaine": actuel.competence.domaine, "niveau": actuel.niveau.libelle,
            "niveau_en": actuel.niveau.libelle_en, "rang": actuel.niveau.rang, "couleur": actuel.niveau.couleur,
            "date": actuel.date_evaluation, "tendance": tendance, "nombre_evaluations": len(evals),
            "acquis": bool(rang_max) and actuel.niveau.rang == rang_max,
            "nouvellement_acquis": bool(rang_max) and actuel.niveau.rang == rang_max
            and precedent is not None and precedent.niveau.rang < rang_max,
        })
    lignes.sort(key=lambda x: (x["domaine"], x["nom"]))
    return {"has_data": bool(lignes), "rang_max": rang_max, "lignes": lignes}


def _maitrise(etat):
    if not etat["has_data"] or etat["rang_max"] <= 1:
        return None
    moyenne = sum(l["rang"] - 1 for l in etat["lignes"]) / len(etat["lignes"])
    return round(moyenne / (etat["rang_max"] - 1) * 100, 1)


def evaluations(student, du=None, au=None, subject=None):
    qs = _dans_periode(EvaluationPedagogique.objects.filter(student=student), "date_evaluation", du, au)
    if subject:
        qs = qs.filter(subject_id=subject)
    lignes = [{"id": e.pk, "date": e.date_evaluation, "titre": e.titre, "type": e.type,
               "score": float(e.score_pourcent), "subject": e.subject_id,
               "subject_name": e.subject.name if e.subject else None, "origine": ORIGINE_SUIVI}
              for e in qs.select_related("subject").order_by("date_evaluation", "id")]
    moyenne = round(sum(l["score"] for l in lignes) / len(lignes), 1) if lignes else None
    return {"has_data": bool(lignes), "moyenne": moyenne, "lignes": lignes}


def _objectifs(student, du=None, au=None, subject=None):
    qs = Objectif.objects.filter(Q(student=student) | Q(class_obj_id=student.current_class_id), archive_le__isnull=True)
    qs = _dans_periode(qs, "created_at__date", du, au)
    if subject:
        qs = qs.filter(subject_id=subject)
    compte = dict(qs.values_list("statut").annotate(n=Count("id")))
    clos = compte.get("atteint", 0) + compte.get("non_atteint", 0)
    return {
        "has_data": bool(compte), "par_statut": compte, "total": sum(compte.values()),
        "taux_atteinte": round(compte.get("atteint", 0) / clos * 100, 1) if clos else None,
    }


def progression(student, du=None, au=None, subject=None):
    """Composantes disponibles et moyenne pondérée. None s'il n'y a aucune donnée."""
    poids = parametres(student.school).poids_effectifs()
    valeurs = {
        "competences": _maitrise(etat_competences(student, du, au, subject)),
        "evaluations": evaluations(student, du, au, subject)["moyenne"],
        "objectifs": _objectifs(student, du, au, subject)["taux_atteinte"],
    }
    presentes = {k: v for k, v in valeurs.items() if v is not None and poids.get(k, 0) > 0}
    if not presentes:
        return {"has_data": False, "valeur": None, "composantes": valeurs, "poids": poids}
    total = sum(poids[k] for k in presentes)
    return {"has_data": True, "valeur": round(sum(presentes[k] * poids[k] for k in presentes) / total, 1),
            "composantes": valeurs, "poids": poids}


def assiduite(student, du=None, au=None):
    """
    Lecture seule du module Présences. Une même séance (date et matière) ne compte
    qu'une fois, la saisie la plus récente faisant foi. Sans relevé, pas de taux :
    l'absence de relevé n'est pas une présence.
    """
    qs = _dans_periode(Attendance.objects.filter(student=student), "date", du, au).order_by("id")
    seances = {(a.date, a.subject_id): a for a in qs}.values()
    total = len(seances)
    presents = sum(a.status == "present" for a in seances)
    retards = sum(a.status == "late" for a in seances)
    justifiees = sum(a.status == "excused" or (a.status == "absent" and bool(a.justification)) for a in seances)
    non_justifiees = sum(a.status == "absent" and not a.justification for a in seances)
    return {
        "has_data": bool(total), "total": total, "presents": presents, "retards": retards,
        "absents": justifiees + non_justifiees, "absences_justifiees": justifiees, "absences_non_justifiees": non_justifiees,
        "excuses": sum(a.status == "excused" for a in seances),
        "taux": round((presents + retards) / total * 100, 1) if total else None,
        "origine": ORIGINE_HISTORIQUE,
    }


def participation(student, du=None, au=None, subject=None):
    qs = _dans_periode(ObservationParticipation.objects.filter(student=student), "date_observation", du, au)
    if subject:
        qs = qs.filter(subject_id=subject)
    moyenne = qs.aggregate(m=Avg("niveau"))["m"]
    nombre = qs.count()
    suffisant = nombre >= parametres(student.school).min_observations
    return {"has_data": bool(nombre), "suffisant": suffisant, "nombre": nombre,
            "moyenne": round(moyenne, 2) if moyenne and suffisant else None,
            "par_niveau": dict(qs.values_list("niveau").annotate(n=Count("id")))}


def progression_par_matiere(student, du=None, au=None):
    """Détail par matière. Chaque mesure reste séparée : aucune n'est déduite d'une autre."""
    from apps.subjects.models import Subject

    evals = _dans_periode(EvaluationPedagogique.objects.filter(student=student, subject__isnull=False), "date_evaluation", du, au)
    notes = _dans_periode(Grade.objects.filter(student=student, is_deleted=False), "created_at__date", du, au)
    ids = set(evals.values_list("subject_id", flat=True)) | set(notes.values_list("subject_id", flat=True))
    lignes = []
    for matiere in Subject.objects.filter(pk__in=ids).order_by("name"):
        etat = etat_competences(student, du, au, matiere.pk)
        moy_eval = evals.filter(subject=matiere).aggregate(m=Avg("score_pourcent"))["m"]
        moy_note = notes.filter(subject=matiere).aggregate(m=Avg("value"))["m"]
        lignes.append({"subject": matiere.pk, "nom": matiere.name, "maitrise": _maitrise(etat),
                       "evaluations": round(float(moy_eval), 1) if moy_eval is not None else None,
                       "notes_officielles": round(float(moy_note), 2) if moy_note is not None else None})
    return {"has_data": bool(lignes), "lignes": lignes}


def resultats_historiques(student, du=None, au=None, subject=None):
    """
    Couche d'intégration en LECTURE SEULE vers les notes : aucune écriture, aucune
    conversion. Chaque ligne garde sa provenance et son contexte.
    """
    qs = Grade.objects.filter(student=student, is_deleted=False).select_related("subject", "school_year")
    qs = _dans_periode(qs, "created_at__date", du, au)
    if subject:
        qs = qs.filter(subject_id=subject)
    lignes = [{"id": g.pk, "date": g.graded_at or g.created_at.date(), "subject": g.subject_id,
               "subject_name": g.subject.name, "valeur": float(g.value), "bareme": 20, "periode": g.period,
               "annee": g.school_year.name, "type": g.note_type, "origine": ORIGINE_HISTORIQUE}
              for g in qs.order_by("created_at", "id")]
    return {"has_data": bool(lignes), "origine": ORIGINE_HISTORIQUE, "lignes": lignes}


def resultats_examens(student, du=None, au=None, famille=False):
    """Examens en ligne validés, en lecture seule. Une famille ne voit que les résultats publiés."""
    from apps.evaluations.models import Tentative

    qs = Tentative.objects.filter(student=student, statut=Tentative.VALIDEE).select_related("epreuve__subject")
    if famille:
        qs = qs.filter(epreuve__resultats_publies=True)
    qs = _dans_periode(qs, "remise_le__date", du, au)
    lignes = [{"id": t.pk, "date": t.remise_le.date(), "titre": t.epreuve.titre, "type": t.epreuve.type,
               "subject_name": t.epreuve.subject.name, "score": float(t.pourcentage or 0),
               "transferee": t.transferts.exists(), "origine": ORIGINE_EXAMEN}
              for t in qs.prefetch_related("transferts").order_by("remise_le", "id")]
    return {"has_data": bool(lignes), "origine": ORIGINE_EXAMEN, "lignes": lignes}


def series(student, du=None, au=None, subject=None, famille=False):
    """Séries mensuelles pour les graphiques. Chaque origine reste une série distincte."""
    from apps.evaluations.models import Tentative

    def mois(d):
        return d.strftime("%Y-%m")

    def moyennes(lignes):
        groupes = defaultdict(list)
        for d, v in lignes:
            groupes[mois(d)].append(float(v))
        return {m: round(sum(vs) / len(vs), 1) for m, vs in groupes.items()}

    evals = _dans_periode(EvaluationPedagogique.objects.filter(student=student), "date_evaluation", du, au)
    notes = _dans_periode(Grade.objects.filter(student=student, is_deleted=False), "created_at__date", du, au)
    examens = _dans_periode(Tentative.objects.filter(student=student, statut=Tentative.VALIDEE), "remise_le__date", du, au)
    if famille:
        examens = examens.filter(epreuve__resultats_publies=True)
    if subject:
        evals, notes, examens = evals.filter(subject_id=subject), notes.filter(subject_id=subject), examens.filter(epreuve__subject_id=subject)
    s_evals = moyennes(evals.values_list("date_evaluation", "score_pourcent"))
    # Notes sur 20 ramenées en pourcentage, seulement pour les placer sur le même axe.
    s_notes = moyennes((g.created_at, float(g.value) * 5) for g in notes)
    s_examens = moyennes((t.remise_le, t.pourcentage or 0) for t in examens)
    evolution = [{"mois": m, "suivi": s_evals.get(m), "examens": s_examens.get(m), "notes": s_notes.get(m)}
                 for m in sorted(set(s_evals) | set(s_notes) | set(s_examens))]
    presences = {}
    releves = _dans_periode(Attendance.objects.filter(student=student), "date", du, au).order_by("id")
    for a in {(x.date, x.subject_id): x for x in releves}.values():
        ligne = presences.setdefault(mois(a.date), {"mois": mois(a.date), "presents": 0, "retards": 0, "absences": 0})
        cle = {"present": "presents", "late": "retards"}.get(a.status, "absences")
        ligne[cle] += 1
    etat = etat_competences(student, du, au, subject)
    repartition = [{"niveau": n.libelle, "niveau_en": n.libelle_en, "couleur": n.couleur, "code": n.code,
                    "nombre": sum(1 for l in etat["lignes"] if l["rang"] == n.rang)}
                   for n in NiveauMaitrise.objects.filter(school=student.school)]
    return {"evolution": evolution, "assiduite": [presences[m] for m in sorted(presences)], "competences": repartition}


def chronologie(student, famille=False):
    """Frise : tout ce qui s'est passé pour l'élève, du plus récent au plus ancien."""
    from apps.evaluations.models import Tentative

    from .models import ObjectifHistorique, RapportPedagogique

    ev = []
    for e in EvaluationCompetence.objects.filter(student=student, statut=EvaluationCompetence.VALIDEE).select_related("competence", "niveau")[:200]:
        ev.append({"date": e.date_evaluation, "type": "competence", "titre": e.competence.nom, "detail": e.niveau.libelle})
    for e in EvaluationPedagogique.objects.filter(student=student)[:200]:
        ev.append({"date": e.date_evaluation, "type": "evaluation", "titre": e.titre, "detail": f"{float(e.score_pourcent):g} %"})
    examens = Tentative.objects.filter(student=student, statut=Tentative.VALIDEE).select_related("epreuve")
    if famille:
        examens = examens.filter(epreuve__resultats_publies=True)
    for t in examens[:200]:
        ev.append({"date": t.remise_le.date(), "type": "examen", "titre": t.epreuve.titre, "detail": f"{float(t.pourcentage or 0):g} %"})
    for h in ObjectifHistorique.objects.filter(objectif__student=student).select_related("objectif")[:200]:
        ev.append({"date": h.created_at.date(), "type": "objectif", "titre": h.objectif.titre, "statut": h.nouveau_statut, "detail": ""})
    plans = PlanAccompagnement.objects.filter(student=student)
    if famille:
        plans = plans.filter(partage_famille=True)
    for p in plans[:100]:
        ev.append({"date": p.debut, "type": "plan", "titre": p.titre, "detail": ""})
    rapports = RapportPedagogique.objects.filter(student=student)
    if famille:
        rapports = rapports.filter(versions__statut=RapportPedagogique.PUBLIE).distinct()
    for r in rapports[:100]:
        ev.append({"date": r.au, "type": "rapport", "titre": f"{r.du} - {r.au}", "detail": r.type})
    if not famille:
        for o in ObservationParticipation.objects.filter(student=student)[:200]:
            ev.append({"date": o.date_observation, "type": "observation", "titre": o.get_niveau_display(), "detail": o.note})
    ev.sort(key=lambda x: str(x["date"]), reverse=True)
    return ev[:300]


def fiche(student, du=None, au=None, subject=None, famille=False):
    plans = PlanAccompagnement.objects.filter(student=student)
    if famille:
        plans = plans.filter(partage_famille=True)
    donnees = {
        "progression": progression(student, du, au, subject),
        "par_matiere": progression_par_matiere(student, du, au),
        "assiduite": assiduite(student, du, au),
        "participation": participation(student, du, au, subject),
        "competences": etat_competences(student, du, au, subject),
        "evaluations": evaluations(student, du, au, subject),
        "objectifs": _objectifs(student, du, au, subject),
        "resultats_historiques": resultats_historiques(student, du, au, subject),
        "resultats_examens": resultats_examens(student, du, au, famille),
        "series": series(student, du, au, subject, famille),
        "chronologie": chronologie(student, famille),
        "plans_actifs": plans.filter(statut="actif").count(),
    }
    return donnees


def comparer(student, a, b, subject=None):
    """Compare deux périodes (du, au). Aucun écart n'est calculé si l'une des deux est vide."""
    gauche = progression(student, a[0], a[1], subject)
    droite = progression(student, b[0], b[1], subject)

    def ecart(x, y):
        return round(y - x, 1) if x is not None and y is not None else None

    return {
        "a": gauche, "b": droite, "ecart_progression": ecart(gauche["valeur"], droite["valeur"]),
        "ecart_maitrise": ecart(gauche["composantes"]["competences"], droite["composantes"]["competences"]),
        "ecart_evaluations": ecart(gauche["composantes"]["evaluations"], droite["composantes"]["evaluations"]),
        "note_moyenne_a": _moyenne_notes(student, a, subject), "note_moyenne_b": _moyenne_notes(student, b, subject),
    }


def _moyenne_notes(student, periode, subject):
    qs = _dans_periode(Grade.objects.filter(student=student, is_deleted=False), "created_at__date", periode[0], periode[1])
    if subject:
        qs = qs.filter(subject_id=subject)
    if qs.count() < parametres(student.school).min_notes_comparaison:
        return None
    moyenne = qs.aggregate(m=Avg("value"))["m"]
    return float(round(Decimal(moyenne), 2)) if moyenne is not None else None
