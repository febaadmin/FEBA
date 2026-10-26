"""
Commentaire du directeur et génération des bulletins, pour un élève, une
classe ou toute une académie.

Point d'entrée unique, utilisé par l'API (opération sur un bulletin) et
par la tâche Celery (opérations groupées) : les mêmes règles s'appliquent
quel que soit le chemin.

Règles :
  - la portée est TOUJOURS résolue à l'intérieur d'une académie : l'élève,
    la classe et l'année scolaire doivent lui appartenir (sinon refus) ;
  - le commentaire est enregistré AVANT la régénération du PDF : si la
    génération échoue, le commentaire est conservé, l'ancien PDF aussi, et
    l'échec est compté comme tel (« PDF non régénéré ») ;
  - un bulletin absent n'est créé que si l'utilisateur l'a demandé
    (`create_missing`), et jamais pour un élève sans aucune note sur la
    période : on ne fabrique pas de bulletin vide ;
  - le bilan rapporte ce qui a été FAIT, élève par élève.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.grades.models import Grade
from apps.schools.models import SchoolYear
from apps.students.models import Student, StudentEnrollment

from .models import GENERAL_COMMENT_MAX_LENGTH, Bulletin, BulletinOperation

logger = logging.getLogger("apps")

PERIODS = {code for code, _ in Bulletin.PERIOD_CHOICES}


class ScopeError(ValueError):
    """Paramètres de portée invalides ou hors de l'académie (→ 400/404)."""

    def __init__(self, message, status=400, current_comment=None):
        self.current_comment = current_comment
        super().__init__(message)
        self.status = status


def clean_comment(value):
    """
    Normalise un commentaire saisi : retours à la ligne unifiés, espaces de
    fin de ligne et lignes vides en excès retirés. Le texte reste du TEXTE :
    l'échappement est fait au rendu PDF (apps.core.pdf_longtext).
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ScopeError("Le commentaire doit être un texte.")
    text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned, blank = [], 0
    for line in lines:
        blank = blank + 1 if not line.strip() else 0
        if blank <= 1:
            cleaned.append(line)
    text = "\n".join(cleaned).strip()
    if len(text) > GENERAL_COMMENT_MAX_LENGTH:
        raise ScopeError(
            f"Commentaire trop long : {len(text)} caractères pour "
            f"{GENERAL_COMMENT_MAX_LENGTH} au maximum (au-delà, il ne tient plus "
            f"sur le bulletin à côté du cachet)."
        )
    return text


def _get_in_school(model, pk, label, **lookup):
    if pk in (None, ""):
        raise ScopeError(f"{label} : identifiant requis.")
    try:
        return model.objects.get(pk=int(pk), **lookup)
    except (ValueError, TypeError):
        raise ScopeError(f"{label} : identifiant invalide.")
    except model.DoesNotExist:
        # Même réponse qu'il soit inexistant ou d'une autre académie : son
        # existence n'est pas révélée.
        raise ScopeError(f"{label} introuvable dans cette académie.", status=404)


def resolve_scope(school, *, scope, period, school_year_id, student_id=None, class_id=None):
    """
    Valide les identifiants reçus et retourne (school_year, student, class_obj,
    queryset des élèves ciblés). Tout est vérifié contre `school`.
    """
    from apps.classes.models import Class

    if school is None:
        raise ScopeError("Sélectionnez d'abord une académie : une opération groupée "
                         "ne porte jamais sur toutes les académies.", status=400)
    if period not in PERIODS:
        raise ScopeError("Période invalide (T1, T2, T3 ou annual).")
    if scope not in dict(BulletinOperation.SCOPES):
        raise ScopeError("Portée invalide (student, class ou academy).")
    year = _get_in_school(SchoolYear, school_year_id, "Année scolaire", school=school)

    student = class_obj = None
    if scope == BulletinOperation.SCOPE_STUDENT:
        student = _get_in_school(Student, student_id, "Élève", school=school)
        students = Student.objects.filter(pk=student.pk)
    elif scope == BulletinOperation.SCOPE_CLASS:
        class_obj = _get_in_school(Class, class_id, "Classe", school_year__school=school)
        # Classe de l'élève POUR CETTE ANNÉE : celle de son inscription, à
        # défaut sa classe actuelle (même règle que Grade._class_for_year).
        has_class_enrollment = StudentEnrollment.objects.filter(
            student=OuterRef("pk"), school_year=year, class_obj__isnull=False)
        students = Student.objects.filter(school=school).filter(
            Q(enrollments__school_year=year, enrollments__class_obj=class_obj)
            | (~Exists(has_class_enrollment) & Q(current_class=class_obj))
        ).distinct()
    else:
        students = Student.objects.filter(school=school)
    if scope != BulletinOperation.SCOPE_STUDENT:
        # Élèves éligibles : actifs, compte actif (même règle que la
        # génération groupée historique).
        students = students.filter(is_active=True).filter(
            Q(user__isnull=True) | Q(user__is_active=True))
    return year, student, class_obj, students.select_related("user", "current_class").order_by(
        "last_name", "first_name", "pk")


def _has_grades(student, year, period):
    qs = Grade.objects.filter(student=student, school_year=year, is_deleted=False)
    if period != "annual":
        qs = qs.filter(period=period)
    return qs.exists()


def _new_result(total):
    return {
        "targeted": total,          # élèves dans la portée
        "processed": 0,             # bulletins effectivement traités
        "comments_set": 0,          # commentaires ajoutés ou remplacés
        "comments_cleared": 0,      # commentaires supprimés
        "unchanged": 0,             # commentaire déjà identique
        "pdf_generated": 0,         # PDF générés ou régénérés
        "bulletins_created": 0,     # bulletins absents créés (sur demande)
        "failed": 0,
        "skipped": 0,
        "failures": [],             # [{student_id, student, reason}]
        "skipped_items": [],        # [{student_id, student, reason}]
        "items": [],                # [{student_id, student, bulletin_id, outcome}]
    }


def _row(student):
    return {"student_id": student.pk, "student": student.get_full_name()}


def apply_to_student(student, year, period, *, action, comment="", regenerate=True,
                     create_missing=False, user=None, result=None):
    """Applique l'opération à UN élève et met `result` à jour. Retourne le bulletin."""
    from .pdf_generator import UNCHANGED, generate_bulletin

    res = result if result is not None else _new_result(1)
    row = _row(student)

    if not student.is_active or (student.user_id and not student.user.is_active):
        res["skipped"] += 1
        res["skipped_items"].append({**row, "reason": "élève désactivé"})
        return None

    bulletin = Bulletin.objects.filter(student=student, school_year=year, period=period).first()

    if bulletin is None:
        if action == BulletinOperation.ACTION_CLEAR:
            res["skipped"] += 1
            res["skipped_items"].append({**row, "reason": "aucun bulletin : rien à supprimer"})
            return None
        if action == BulletinOperation.ACTION_SET and not create_missing:
            res["skipped"] += 1
            res["skipped_items"].append(
                {**row, "reason": "bulletin pas encore généré (création non demandée)"})
            return None
        if not _has_grades(student, year, period):
            res["skipped"] += 1
            res["skipped_items"].append({**row, "reason": "aucune note sur la période"})
            return None
        try:
            new_comment = comment if action == BulletinOperation.ACTION_SET else UNCHANGED
            bulletin = generate_bulletin(student, period, year, comment=new_comment)
        except Exception as exc:
            logger.error("Bulletin non créé %s/%s : %s", student.matricule, period, exc, exc_info=True)
            res["failed"] += 1
            res["failures"].append({**row, "reason": f"génération impossible : {exc}"})
            return None
        if action == BulletinOperation.ACTION_SET:
            Bulletin.objects.filter(pk=bulletin.pk).update(
                comment_updated_at=bulletin.generated_at, comment_updated_by=user)
            res["comments_set"] += 1
        res["processed"] += 1
        res["bulletins_created"] += 1
        res["pdf_generated"] += 1
        res["items"].append({**row, "bulletin_id": bulletin.pk, "outcome": "créé"})
        return bulletin

    # Bulletin existant : on enregistre d'abord le commentaire.
    outcome = "régénéré"
    if action in (BulletinOperation.ACTION_SET, BulletinOperation.ACTION_CLEAR):
        target = comment if action == BulletinOperation.ACTION_SET else ""
        with transaction.atomic():
            locked = Bulletin.objects.select_for_update().get(pk=bulletin.pk)
            if locked.general_comment == target:
                res["unchanged"] += 1
                outcome = "commentaire inchangé"
            else:
                locked.general_comment = target
                locked.comment_updated_at = timezone.now()
                locked.comment_updated_by = user
                locked.save(update_fields=["general_comment", "comment_updated_at",
                                           "comment_updated_by"])
                if action == BulletinOperation.ACTION_SET:
                    res["comments_set"] += 1
                    outcome = "commentaire enregistré"
                else:
                    res["comments_cleared"] += 1
                    outcome = "commentaire supprimé"
        bulletin.refresh_from_db()

    res["processed"] += 1
    must_generate = action == BulletinOperation.ACTION_GENERATE or (
        regenerate and (outcome not in ("commentaire inchangé",) or bulletin.pdf_outdated))
    if must_generate and not bulletin.pdf_file and not _has_grades(student, year, period):
        # Brouillon (commentaire saisi avant génération) d'un élève encore
        # sans note : on ne fabrique pas de bulletin vide. Le commentaire est
        # enregistré ; le PDF viendra avec la première génération.
        must_generate = False
        res["skipped"] += 1
        res["skipped_items"].append({**row, "reason": "PDF non généré : aucune note sur la période "
                                                      "(commentaire enregistré)"})
        outcome += ", PDF non généré (aucune note)"
    if must_generate:
        try:
            bulletin = generate_bulletin(student, period, year)
            res["pdf_generated"] += 1
            outcome += ", PDF régénéré" if action != BulletinOperation.ACTION_GENERATE else ""
        except Exception as exc:
            logger.error("PDF non régénéré %s/%s : %s", student.matricule, period, exc, exc_info=True)
            res["failed"] += 1
            res["failures"].append({
                **row, "reason": (f"PDF non régénéré ({exc}) ; le commentaire est enregistré "
                                  f"et l'ancien PDF est conservé"),
            })
            outcome += ", PDF NON régénéré"
    res["items"].append({**row, "bulletin_id": bulletin.pk, "outcome": outcome})
    return bulletin


def save_student_comment(school, *, student_id, school_year_id, period, comment,
                         regenerate=True, expected_comment=None, user=None):
    """
    Commentaire d'UN élève (année, période), bulletin généré ou non.

    Tout se passe dans une transaction avec verrou de ligne : deux
    enregistrements simultanés sont sérialisés, une même demande répétée ne
    crée pas de doublon (contrainte unique élève/année/période) et ne change
    rien la seconde fois. `expected_comment` : commentaire que l'utilisateur
    avait sous les yeux ; s'il a changé entre-temps → ScopeError 409.
    """
    from django.db import IntegrityError
    year, student, _cls, _qs = resolve_scope(
        school, scope=BulletinOperation.SCOPE_STUDENT, period=period,
        school_year_id=school_year_id, student_id=student_id)
    result = _new_result(1)
    with transaction.atomic():
        try:
            bulletin, created = Bulletin.objects.select_for_update().get_or_create(
                student=student, school_year=year, period=period)
        except IntegrityError:
            created = False
            bulletin = Bulletin.objects.select_for_update().get(
                student=student, school_year=year, period=period)
        current = bulletin.general_comment or ""
        if expected_comment is not None and expected_comment.replace("\r\n", "\n").strip() != current:
            raise ScopeError("Le commentaire a été modifié par quelqu'un d'autre entre-temps. "
                             "Rechargez-le avant de l'enregistrer.", status=409, current_comment=current)
        changed = current != comment
        if changed:
            bulletin.general_comment = comment
            bulletin.comment_updated_at = timezone.now()
            bulletin.comment_updated_by = user
            bulletin.save(update_fields=["general_comment", "comment_updated_at", "comment_updated_by"])
            result["comments_set" if comment else "comments_cleared"] += 1
        else:
            result["unchanged"] += 1
    result["processed"] = 1
    result["draft_created"] = created
    outcome = ("commentaire enregistré" if comment else "commentaire supprimé") if changed else "commentaire inchangé"
    bulletin.refresh_from_db()
    if regenerate and (changed or bulletin.pdf_outdated):
        if not bulletin.pdf_file and not _has_grades(student, year, period):
            result["skipped"] += 1
            result["skipped_items"].append({**_row(student), "reason": "PDF non généré : aucune note "
                                            "sur la période (commentaire enregistré)"})
            outcome += ", PDF non généré (aucune note)"
        else:
            from .pdf_generator import generate_bulletin
            try:
                bulletin = generate_bulletin(student, period, year)
                result["pdf_generated"] += 1
                outcome += ", PDF régénéré"
            except Exception as exc:
                logger.error("PDF non régénéré %s/%s : %s", student.matricule, period, exc, exc_info=True)
                result["failed"] += 1
                result["failures"].append({**_row(student), "reason": (
                    f"PDF non régénéré ({exc}) ; le commentaire est enregistré"
                    + (" et l'ancien PDF est conservé" if bulletin.pdf_file else ""))})
                outcome += ", PDF NON régénéré"
    result["items"].append({**_row(student), "bulletin_id": bulletin.pk, "outcome": outcome})
    result["bulletin_id"] = bulletin.pk
    logger.info("Commentaire bulletin %s (%s %s/%s) par %s : %s", bulletin.pk, student.matricule,
                period, year.name, getattr(user, "pk", None), outcome)
    return result


#: Au-delà, une opération « en file » ou « en cours » sans fin est considérée
#: comme interrompue (worker arrêté, redémarrage) : elle ne bloque plus les
#: suivantes.
STALE_QUEUED_AFTER = timedelta(minutes=10)
STALE_RUNNING_AFTER = timedelta(minutes=60)


def expire_stale_operations(school):
    """Marque échouées les opérations bloquées de l'académie ; retourne leur nombre."""
    now = timezone.now()
    stale = BulletinOperation.objects.filter(school=school).filter(
        Q(status="queued", created_at__lt=now - STALE_QUEUED_AFTER)
        | Q(status="running", created_at__lt=now - STALE_RUNNING_AFTER))
    return stale.update(status="failed", finished_at=now, error=(
        "Opération interrompue : aucun worker ne l'a terminée (worker Celery arrêté ou "
        "redémarré). Relancez-la ; les bulletins déjà traités le resteront."))


def run_operation(op):
    """Exécute une BulletinOperation et enregistre son bilan."""
    BulletinOperation.objects.filter(pk=op.pk, started_at__isnull=True).update(
        started_at=timezone.now())
    BulletinOperation.objects.filter(pk=op.pk).update(status="running")
    try:
        year, _student, _cls, students = resolve_scope(
            op.school, scope=op.scope, period=op.period, school_year_id=op.school_year_id,
            student_id=op.student_id, class_id=op.class_obj_id)
        students = list(students)
        result = _new_result(len(students))
        for student in students:
            apply_to_student(student, year, op.period, action=op.action, comment=op.comment,
                             regenerate=op.regenerate, create_missing=op.create_missing,
                             user=op.created_by, result=result)
            # Progression visible pendant le traitement.
            BulletinOperation.objects.filter(pk=op.pk).update(result=result)
        status = "partial" if result["failed"] else "done"
        BulletinOperation.objects.filter(pk=op.pk).update(
            status=status, result=result, finished_at=timezone.now())
    except Exception as exc:
        logger.error("Opération bulletins %s échouée : %s", op.pk, exc, exc_info=True)
        BulletinOperation.objects.filter(pk=op.pk).update(
            status="failed", error=str(exc), finished_at=timezone.now())
    op.refresh_from_db()
    logger.info("Opération bulletins %s : %s par %s, académie %s, %s %s/%s, %s",
                op.pk, op.action, op.created_by_id, op.school_id, op.scope,
                op.period, op.school_year_id, op.status)
    return op
