"""Déroulement d'une épreuve : le serveur tient l'heure, le sujet et le résultat."""
import random
import secrets
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.teachers.affectations import peut_noter

from .correction import _arrondi, points_auto
from .models import (
    Amenagement,
    Epreuve,
    EvenementTentative,
    HistoriqueCorrection,
    Question,
    QuestionVersion,
    Reponse,
    Tentative,
    TransfertNote,
)


def journal(tentative, type_evenement, **donnees):
    EvenementTentative.objects.create(tentative=tentative, type=type_evenement, donnees=donnees)


def eleve_concerne(epreuve, student):
    if epreuve.eleves_cibles.exists():
        return epreuve.eleves_cibles.filter(pk=student.pk).exists()
    return student.current_class_id == epreuve.class_obj_id


def creer_version(question, donnees, user):
    dernier = question.versions.order_by("-numero").values_list("numero", flat=True).first() or 0
    return QuestionVersion.objects.create(question=question, numero=dernier + 1, created_by=user, **donnees)


def publier(epreuve):
    with transaction.atomic():
        epreuve = Epreuve.objects.select_for_update().get(pk=epreuve.pk)
        if epreuve.statut != Epreuve.BROUILLON:
            raise ValidationError({"detail": "Seul un brouillon peut être publié."})
        if not epreuve.questions.exists() and not epreuve.regles_tirage:
            raise ValidationError({"detail": "Ajoutez au moins une question."})
        if epreuve.produit_note and not epreuve.periode:
            raise ValidationError({"periode": "Une épreuve qui produit une note doit indiquer son trimestre."})
        epreuve.statut = Epreuve.PUBLIEE
        epreuve.save(update_fields=["statut", "updated_at"])
    return epreuve


def _tirage(epreuve, rng):
    """Questions tirées dans la banque, à répartition identique pour chaque candidat."""
    lignes = []
    deja = set(epreuve.questions.values_list("version__question_id", flat=True))
    for regle in epreuve.regles_tirage or []:
        qs = Question.objects.filter(school=epreuve.school, archive=False, prive=False).exclude(pk__in=deja)
        if regle.get("subject"):
            qs = qs.filter(subject_id=regle["subject"])
        if regle.get("difficulte"):
            qs = qs.filter(difficulte=regle["difficulte"])
        if regle.get("competence"):
            qs = qs.filter(competences=regle["competence"])
        ids = sorted(qs.values_list("pk", flat=True))
        nombre = int(regle.get("nombre", 0))
        if len(ids) < nombre:
            raise ValidationError({"detail": "La banque ne contient pas assez de questions pour cette épreuve."})
        for pk in rng.sample(ids, nombre):
            deja.add(pk)
            version = Question.objects.get(pk=pk).version_courante
            lignes.append((version, Decimal(str(regle.get("points", version.points)))))
    return lignes


def _sujet(epreuve, seed):
    """Fige le sujet d'une tentative. Même graine, même sujet : reproductible."""
    rng = random.Random(seed)
    lignes = [(q.version, q.points) for q in epreuve.questions.select_related("version")] + _tirage(epreuve, rng)
    if epreuve.melanger_questions:
        rng.shuffle(lignes)
    sujet = []
    for version, points in lignes:
        ordre = {}
        contenu = version.contenu or {}
        for cle in ("choix", "droite", "elements"):
            if contenu.get(cle):
                valeurs = [c["id"] for c in contenu[cle]]
                if cle != "choix" or epreuve.melanger_reponses:
                    rng.shuffle(valeurs)
                ordre[cle] = valeurs
        sujet.append({"version": version.pk, "points": str(points), "ordre": ordre})
    return sujet


def demarrer(epreuve, student, ip=""):
    """Démarre ou reprend. Idempotent : deux clics ne créent pas deux tentatives."""
    maintenant = timezone.now()
    if epreuve.statut != Epreuve.PUBLIEE or not epreuve.ouverture <= maintenant <= epreuve.fermeture:
        raise PermissionDenied("Cette épreuve n'est pas ouverte.")
    if not eleve_concerne(epreuve, student):
        raise PermissionDenied("Cette épreuve ne vous concerne pas.")
    amenagement = Amenagement.objects.filter(epreuve=epreuve, student=student).first()
    # Hors transaction : un refus plus loin ne doit pas annuler la remise automatique.
    for echue in Tentative.objects.filter(epreuve=epreuve, student=student, statut=Tentative.EN_COURS):
        clore_si_echue(echue)
    for essai in range(2):
        try:
            with transaction.atomic():
                en_cours = Tentative.objects.select_for_update().filter(
                    epreuve=epreuve, student=student, statut=Tentative.EN_COURS).first()
                if en_cours:
                    if not epreuve.reprise_autorisee:
                        raise PermissionDenied("La reprise n'est pas autorisée : demandez à l'enseignant.")
                    en_cours.jeton = uuid.uuid4()
                    en_cours.save(update_fields=["jeton"])
                    journal(en_cours, "reprise", ip=ip)
                    return en_cours
                faites = Tentative.objects.filter(epreuve=epreuve, student=student).count()
                autorisees = epreuve.tentatives_max + (amenagement.tentatives_sup if amenagement else 0)
                if faites >= autorisees:
                    raise PermissionDenied("Vous avez utilisé toutes vos tentatives.")
                seed = secrets.randbits(48)
                sujet = _sujet(epreuve, seed)
                minutes = epreuve.duree_minutes + (amenagement.minutes_sup if amenagement else 0)
                # L'aménagement de temps peut dépasser la fermeture ; sinon, la fermeture prime.
                limite = epreuve.fermeture + timedelta(minutes=amenagement.minutes_sup if amenagement else 0)
                tentative = Tentative.objects.create(
                    epreuve=epreuve, student=student, numero=faites + 1, seed=seed, sujet=sujet,
                    debut=maintenant, echeance=min(maintenant + timedelta(minutes=minutes), limite),
                    total_points=sum((Decimal(s["points"]) for s in sujet), Decimal(0)),
                )
                journal(tentative, "demarrage", ip=ip)
                return tentative
        except IntegrityError:
            if essai:
                raise
    raise ValidationError({"detail": "Réessayez."})


def _points_de(tentative, version_id):
    return next((Decimal(s["points"]) for s in tentative.sujet if s["version"] == version_id), None)


def enregistrer_reponse(tentative_id, student, version_id, valeur, jeton=None, fichier=None):
    """Sauvegarde idempotente. Refusée après l'échéance : le serveur fait foi."""
    # Hors transaction : le refus qui suit ne doit pas annuler la remise automatique.
    clore_si_echue(Tentative.objects.get(pk=tentative_id, student=student))
    with transaction.atomic():
        tentative = Tentative.objects.select_for_update().get(pk=tentative_id, student=student)
        if tentative.statut != Tentative.EN_COURS or timezone.now() >= tentative.echeance:
            raise ValidationError({"detail": "L'épreuve est terminée : cette réponse n'est pas enregistrée.", "code": "terminee"})
        if _points_de(tentative, version_id) is None:
            raise ValidationError({"version": "Cette question n'appartient pas à votre sujet."})
        if jeton and str(jeton).replace("-", "") != str(tentative.jeton).replace("-", ""):
            journal(tentative, "session_concurrente")
        defaults = {"valeur": valeur}
        if fichier is not None:
            defaults["fichier"] = fichier
        reponse, _ = Reponse.objects.update_or_create(tentative=tentative, version_id=version_id, defaults=defaults)
        return tentative, reponse


def remettre(tentative, mode="eleve"):
    """Remise idempotente : une seconde remise renvoie la première sans rien changer."""
    with transaction.atomic():
        tentative = Tentative.objects.select_for_update().get(pk=tentative.pk)
        if tentative.statut != Tentative.EN_COURS:
            return tentative
        tentative.remise_le = timezone.now()
        tentative.mode_remise = mode
        _corriger_auto(tentative)
        journal(tentative, "remise", mode=mode)
    return tentative


def clore_si_echue(tentative):
    if tentative.statut == Tentative.EN_COURS and timezone.now() >= tentative.echeance:
        remettre(tentative, "auto")
        tentative.refresh_from_db()
        return True
    return False


def cloturer_echues():
    total = 0
    for tentative in Tentative.objects.filter(statut=Tentative.EN_COURS, echeance__lte=timezone.now()):
        remettre(tentative, "auto")
        total += 1
    return total


def _corriger_auto(tentative):
    versions = QuestionVersion.objects.select_related("question").in_bulk([s["version"] for s in tentative.sujet])
    reponses = {r.version_id: r for r in tentative.reponses.all()}
    total, manuel = Decimal(0), False
    for ligne in tentative.sujet:
        version = versions[ligne["version"]]
        reponse = reponses.get(version.pk)
        if reponse is None:
            reponse = Reponse.objects.create(tentative=tentative, version=version)
        points = points_auto(version.question.type, version.corrige or {}, reponse.valeur, ligne["points"])
        reponse.points_auto = points
        reponse.save(update_fields=["points_auto"])
        if points is None:
            manuel = True
        else:
            total += points
    tentative.score_brut = total
    tentative.score_corrige = None if manuel else total
    tentative.statut = Tentative.REMISE if manuel else Tentative.CORRIGEE
    _resultat(tentative, tentative.score_corrige)
    tentative.save()


def _resultat(tentative, score):
    if score is None or not tentative.total_points:
        tentative.pourcentage = tentative.note_echelle = tentative.reussie = None
        return
    part = score / tentative.total_points
    tentative.pourcentage = _arrondi(part * 100)
    tentative.note_echelle = (part * tentative.epreuve.note_max).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tentative.reussie = tentative.pourcentage >= tentative.epreuve.seuil_reussite


def corriger(reponse_id, points, commentaire, user):
    with transaction.atomic():
        reponse = Reponse.objects.select_for_update().select_related("tentative__epreuve").get(pk=reponse_id)
        tentative = Tentative.objects.select_for_update().get(pk=reponse.tentative_id)
        if tentative.statut == Tentative.EN_COURS:
            raise ValidationError({"detail": "Cette tentative n'est pas encore remise."})
        if TransfertNote.objects.filter(tentative=tentative).exists():
            raise ValidationError({"detail": "Note déjà transférée : la correction passe par une nouvelle validation dans le module de notes."})
        maximum = _points_de(tentative, reponse.version_id)
        if points is None or points < 0 or points > maximum:
            raise ValidationError({"points": f"Entre 0 et {maximum}."})
        HistoriqueCorrection.objects.create(reponse=reponse, points_avant=reponse.points, points_apres=points,
                                            commentaire=commentaire, par=user)
        reponse.points_manuel, reponse.commentaire, reponse.corrige_par, reponse.corrige_le = points, commentaire, user, timezone.now()
        reponse.save()
        reponses = tentative.reponses.all()
        if all(r.points is not None for r in reponses):
            tentative.score_corrige = sum((r.points for r in reponses), Decimal(0))
            tentative.statut = Tentative.CORRIGEE
            tentative.score_valide = tentative.valide_le = tentative.valide_par = None
            _resultat(tentative, tentative.score_corrige)
            tentative.save()
    return reponse


def valider(tentative, user):
    with transaction.atomic():
        tentative = Tentative.objects.select_for_update().get(pk=tentative.pk)
        if tentative.statut not in (Tentative.CORRIGEE, Tentative.VALIDEE):
            raise ValidationError({"detail": "La correction n'est pas terminée."})
        tentative.score_valide, tentative.statut = tentative.score_corrige, Tentative.VALIDEE
        tentative.valide_par, tentative.valide_le = user, timezone.now()
        tentative.save()
        journal(tentative, "validation", par=user.pk)
    return tentative


def tentative_retenue(epreuve, student):
    qs = Tentative.objects.filter(epreuve=epreuve, student=student, statut=Tentative.VALIDEE)
    if epreuve.politique == "meilleure":
        return qs.order_by("-score_valide", "numero").first()
    if epreuve.politique == "derniere":
        return qs.order_by("-numero").first()
    if epreuve.politique == "premiere":
        return qs.order_by("numero").first()
    return qs.filter(choisie=True).first()


def transferer(epreuve, student, user):
    """
    Crée la note officielle, une seule fois. Le résultat d'origine reste ici, et
    les moyennes et bulletins continuent d'être calculés par le module de notes.
    """
    from apps.classes.subject_rules import grade_subject_error
    from apps.grades.models import Grade
    from apps.grades.views import _log_grade
    from apps.students.services import get_or_create_enrollment

    if not epreuve.produit_note:
        raise ValidationError({"detail": "Cette épreuve ne produit pas de note officielle."})
    if user.is_teacher() and not peut_noter(user.teacher_profile, epreuve.subject_id, student.current_class_id):
        raise PermissionDenied("Vous n'êtes pas affecté à cette matière dans la classe de cet élève.")
    with transaction.atomic():
        Epreuve.objects.select_for_update().get(pk=epreuve.pk)
        existant = TransfertNote.objects.filter(epreuve=epreuve, student=student).first()
        if existant:
            return existant, False
        tentative = tentative_retenue(epreuve, student)
        if tentative is None:
            raise ValidationError({"detail": f"Aucune tentative validée à retenir pour {student.get_full_name()}."})
        refus = grade_subject_error(student, epreuve.subject, epreuve.school_year)
        if refus:
            raise ValidationError({"detail": refus})
        part = (tentative.score_valide / tentative.total_points) if tentative.total_points else Decimal(0)
        valeur = (part * 20).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        enrollment, _ = get_or_create_enrollment(student, epreuve.school_year_id)
        grade = Grade.objects.create(
            student=student, subject=epreuve.subject, school_year=epreuve.school_year, enrollment=enrollment,
            period=epreuve.periode, value=valeur, note_type=epreuve.note_type,
            teacher=getattr(epreuve.responsable, "teacher_profile", None),
            comment=f"Épreuve en ligne : {epreuve.titre}",
        )
        _log_grade(grade, None, "", "create", user, justification=f"Transfert de l'épreuve en ligne n° {epreuve.pk}")
        transfert = TransfertNote.objects.create(epreuve=epreuve, student=student, tentative=tentative, grade=grade,
                                                 valeur=valeur, par=user)
        journal(tentative, "transfert_note", grade=grade.pk, par=user.pk)
    return transfert, True


def proposer_competences(tentative):
    """
    Propositions pour le suivi, plafonnées sous le niveau le plus haut : seul
    l'enseignant décide qu'une compétence est acquise. Idempotent par tentative.
    """
    from apps.suivi.models import EvaluationCompetence
    from apps.suivi.services import assurer_niveaux

    niveaux = list(assurer_niveaux(tentative.epreuve.school).order_by("rang"))
    if len(niveaux) < 2 or tentative.statut != Tentative.VALIDEE:
        return 0
    versions = QuestionVersion.objects.select_related("question").prefetch_related("question__competences").in_bulk(
        [s["version"] for s in tentative.sujet])
    reponses = {r.version_id: r for r in tentative.reponses.all()}
    scores = {}
    for ligne in tentative.sujet:
        version = versions[ligne["version"]]
        reponse = reponses.get(version.pk)
        for competence in version.question.competences.all():
            obtenu, total = scores.get(competence.pk, (Decimal(0), Decimal(0)))
            scores[competence.pk] = (obtenu + (reponse.points or 0 if reponse else 0), total + Decimal(ligne["points"]))
    creees = 0
    plafonds = niveaux[:-1]
    for competence_id, (obtenu, total) in scores.items():
        if not total:
            continue
        indice = min(int(obtenu / total * len(plafonds)), len(plafonds) - 1)
        _, nouvelle = EvaluationCompetence.objects.get_or_create(
            student=tentative.student, competence_id=competence_id, reference_source=f"tentative-{tentative.pk}",
            defaults={"niveau": plafonds[indice], "date_evaluation": (tentative.remise_le or timezone.now()).date(),
                      "source": EvaluationCompetence.SOURCE_EXAMEN, "statut": EvaluationCompetence.PROPOSEE,
                      "evalue_par": tentative.valide_par,
                      "commentaire": f"Proposition issue de « {tentative.epreuve.titre} » : {obtenu}/{total} points."})
        creees += int(nouvelle)
    return creees


def statistiques(epreuve):
    from statistics import median

    tentatives = list(epreuve.tentatives.exclude(statut=Tentative.EN_COURS))
    retenues = {}
    for t in tentatives:
        if t.pourcentage is not None:
            retenues[t.student_id] = max(retenues.get(t.student_id, t), t, key=lambda x: x.pourcentage)
    notes = [float(t.pourcentage) for t in retenues.values()]
    if epreuve.eleves_cibles.exists():
        inscrits = epreuve.eleves_cibles.count()
    else:
        inscrits = epreuve.class_obj.students.filter(is_active=True).count() if hasattr(epreuve.class_obj, "students") else 0
    participants = len({t.student_id for t in tentatives})
    questions = {}
    for r in Reponse.objects.filter(tentative__in=tentatives).select_related("version__question"):
        q = questions.setdefault(r.version_id, {"version": r.version_id, "enonce": r.version.enonce[:120], "reponses": 0, "obtenu": Decimal(0), "total": Decimal(0)})
        points = _points_de(_cache_tentative(tentatives, r.tentative_id), r.version_id)
        if r.points is not None and points:
            q["reponses"] += 1
            q["obtenu"] += r.points
            q["total"] += points
    lignes = sorted(
        ({"version": q["version"], "enonce": q["enonce"], "reponses": q["reponses"],
          "reussite": round(float(q["obtenu"] / q["total"] * 100), 1) if q["total"] else None} for q in questions.values()),
        key=lambda x: (x["reussite"] is None, x["reussite"]),
    )
    return {
        "inscrits": inscrits, "participants": participants,
        "taux_participation": round(participants / inscrits * 100, 1) if inscrits else None,
        "corrigees": len(notes), "moyenne": round(sum(notes) / len(notes), 2) if notes else None,
        "mediane": round(median(notes), 2) if notes else None, "meilleur": max(notes) if notes else None,
        "plus_faible": min(notes) if notes else None,
        "taux_reussite": round(sum(1 for n in notes if n >= float(epreuve.seuil_reussite)) / len(notes) * 100, 1) if notes else None,
        "questions": lignes, "a_corriger": sum(1 for t in tentatives if t.statut == Tentative.REMISE),
    }


def _cache_tentative(tentatives, pk):
    return next(t for t in tentatives if t.pk == pk)


def epreuves_ouvertes_pour(student):
    return Epreuve.objects.filter(
        Q(eleves_cibles=student) | Q(class_obj_id=student.current_class_id, eleves_cibles__isnull=True),
        school=student.school, statut__in=[Epreuve.PUBLIEE, Epreuve.CLOSE],
    ).distinct()
