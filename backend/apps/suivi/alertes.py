"""
Alertes à examiner par l'enseignant : chaque alerte dit sa règle, ses données et
sa période. Le même signal n'est jamais répété. Aucune n'est envoyée aux familles.
"""
from datetime import timedelta

from django.utils import timezone

from apps.attendance.models import Attendance
from apps.students.models import Student

from . import services
from .models import AlertePedagogique, EvaluationPedagogique, Objectif, RegleAlerte

CATEGORIES = {"baisse_resultats": "surveiller", "progression_positive": "positif", "stagnation": "attention",
              "absences": "surveiller", "difficultes": "surveiller", "objectif_atteint": "objectif"}
RECOMMANDATIONS = {
    "baisse_resultats": "Prévoir une révision ciblée puis une évaluation de contrôle.",
    "progression_positive": "Proposer des activités complémentaires et un nouvel objectif.",
    "stagnation": "Proposer des exercices ciblés sur cette compétence.",
    "absences": "Faire le point avec l'élève et, si nécessaire, proposer un rendez-vous aux parents.",
    "difficultes": "Envisager un plan d'accompagnement.",
    "objectif_atteint": "Définir l'objectif suivant.",
}


def regles(school):
    for code, seuil in RegleAlerte.DEFAUTS.items():
        RegleAlerte.objects.get_or_create(school=school, code=code, defaults={"seuil": seuil})
    return {r.code: r for r in RegleAlerte.objects.filter(school=school, actif=True)}


def _creer(student, code, cle, message, donnees):
    _, cree = AlertePedagogique.objects.get_or_create(
        student=student, code=code, cle=str(cle)[:60],
        defaults={"categorie": CATEGORIES[code], "message": message, "donnees": donnees,
                  "recommandation": RECOMMANDATIONS[code]})
    return int(cree)


def detecter_eleve(student, actives):
    total = 0
    deux = list(EvaluationPedagogique.objects.filter(student=student).order_by("-date_evaluation", "-id")[:2])
    if len(deux) == 2:
        ecart = float(deux[0].score_pourcent - deux[1].score_pourcent)
        donnees = {"du": str(deux[1].date_evaluation), "au": str(deux[0].date_evaluation), "avant": float(deux[1].score_pourcent), "apres": float(deux[0].score_pourcent)}
        if "baisse_resultats" in actives and ecart <= -actives["baisse_resultats"].seuil:
            total += _creer(student, "baisse_resultats", deux[0].pk, f"Résultat en baisse de {abs(ecart):.1f} points entre deux évaluations du suivi.", donnees)
        if "progression_positive" in actives and ecart >= actives["progression_positive"].seuil:
            total += _creer(student, "progression_positive", deux[0].pk, f"Résultat en hausse de {ecart:.1f} points entre deux évaluations du suivi.", donnees)
    etat = services.etat_competences(student)
    if "stagnation" in actives:
        for l in etat["lignes"]:
            if l["tendance"] == "stagne" and l["nombre_evaluations"] >= actives["stagnation"].seuil and not l["acquis"]:
                total += _creer(student, "stagnation", f"{l['competence']}-{l['date']}", f"La compétence « {l['nom']} » reste au niveau {l['niveau']}.", {"competence": l["competence"], "date": str(l["date"])})
    if "difficultes" in actives:
        faibles = [l["nom"] for l in etat["lignes"] if l["rang"] == 1]
        if len(faibles) >= actives["difficultes"].seuil:
            total += _creer(student, "difficultes", f"{len(faibles)}-{timezone.now():%Y-%m}", f"{len(faibles)} compétences sont au premier niveau.", {"competences": faibles})
    if "absences" in actives:
        depuis = timezone.now().date() - timedelta(days=30)
        nombre = Attendance.objects.filter(student=student, status="absent", date__gte=depuis).count()
        if nombre >= actives["absences"].seuil:
            total += _creer(student, "absences", f"{timezone.now():%Y-%m}", f"{nombre} absences sur les 30 derniers jours.", {"depuis": str(depuis), "absences": nombre})
    if "objectif_atteint" in actives:
        for o in Objectif.objects.filter(student=student, statut="atteint"):
            total += _creer(student, "objectif_atteint", o.pk, f"Objectif atteint : {o.titre}.", {"objectif": o.pk})
    return total


def detecter_academie(school):
    actives = regles(school)
    return sum(detecter_eleve(e, actives) for e in Student.objects.filter(school=school, is_active=True))


def detecter_toutes():
    from apps.schools.models import School
    total = 0
    for school in School.objects.all():
        if school.has_feature("suivi_pedagogique"):
            total += detecter_academie(school)
    return total
