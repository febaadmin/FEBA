from feba_project.bulk_delete import BulkDeleteMixin
"""
Grades views — v10 CORRIGÉ

Corrections :
  - Suppression de la logique d'upsert par unique_together (contrainte supprimée)
  - perform_create : crée toujours une NOUVELLE note (multi-notes autorisées)
  - bulk_save : idem, crée de nouvelles notes (pas de remplacement)
  - averages : utilise calculate_average() corrigé
  - (v32) ensure_zeros supprimé : les matières sans note sont exclues des moyennes
  - class_averages : utilise la formule corrigée
  - Filtre note_type dans get_queryset si fourni en query param
"""
import logging
from decimal import Decimal

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Grade, GradeHistory
from .serializers import GradeSerializer, GradeHistorySerializer
from apps.core.tenancy import get_request_school, IsSameTenant

logger = logging.getLogger("apps")


def _log_grade(grade, old_value, old_comment, action, request_user, justification=""):
    GradeHistory.objects.create(
        grade=grade,
        changed_by=request_user,
        old_value=old_value,
        new_value=grade.value,
        old_comment=old_comment or "",
        new_comment=grade.comment or "",
        justification=justification,
        action=action,
    )


class GradeViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class   = GradeSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    filterset_fields   = ["student", "subject", "school_year", "period", "teacher", "note_type", "student__current_class"]
    tenant_lookup = "student__school"

    # ──────────────────────────────────────────────────────────────────────────
    # Queryset
    # ──────────────────────────────────────────────────────────────────────────

    def get_queryset(self):
        user        = self.request.user
        school      = get_request_school(self.request)
        # FIX v20: show_deleted réservé aux admins et au-dessus
        show_deleted = (
            self.request.query_params.get("show_deleted", "0") == "1"
            and user.role_level >= 80
        )

        qs = Grade.objects.select_related(
            "student", "subject", "teacher__user", "school_year"
        ).prefetch_related("history__changed_by")

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        if school is not None:
            qs = qs.filter(student__school=school)
        elif not user.is_superadmin():
            return qs.none()

        if not show_deleted:
            qs = qs.filter(is_deleted=False)

        # Filtre année courante par défaut
        if (
            not self.request.query_params.get("school_year")
            and self.request.query_params.get("all_years") != "1"
        ):
            from apps.schools.models import SchoolYear
            # FIX v29 : "année courante" doit être celle du TENANT courant,
            # pas un enregistrement is_current=True arbitraire d'un autre
            # établissement (bug latent depuis l'introduction du multi-tenant).
            current = SchoolYear.objects.filter(school=school, is_current=True).first()
            if current:
                qs = qs.filter(school_year=current)

        # Filtre note_type optionnel
        note_type = self.request.query_params.get("note_type")
        if note_type:
            qs = qs.filter(note_type=note_type)

        # FIX v26: filtre langue de matière (FR/EN) — filtres combinés admin
        lang = self.request.query_params.get("language")
        if lang:
            qs = qs.filter(subject__language=lang)

        # RBAC
        if user.role_level >= 80:
            return qs

        qs = qs.filter(student__is_active=True, student__user__is_active=True)

        if user.is_teacher():
            try:
                teacher = user.teacher_profile
                return (
                    qs.filter(teacher=teacher)
                    | qs.filter(student__current_class__in=teacher.classes.all())
                )
            except Exception:
                return qs.none()

        elif user.is_parent():
            return qs.filter(student__parents__parent__user=user)

        elif user.is_student():
            try:
                return qs.filter(student__user=user)
            except Exception:
                return qs.none()

        return qs.none()

    # ──────────────────────────────────────────────────────────────────────────
    # Permissions
    # ──────────────────────────────────────────────────────────────────────────

    def get_permissions(self):
        if self.action in [
            "create", "update", "partial_update", "destroy",
            "restore", "bulk_save",
        ]:
            from apps.accounts.permissions import IsAdminOrTeacher
            return [IsAuthenticated(), IsAdminOrTeacher()]
        return super().get_permissions()

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve_teacher(self):
        if self.request.user.is_teacher():
            try:
                return self.request.user.teacher_profile
            except Exception as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        return None

    def _validate_teacher_permission(self, teacher, subject, student):
        if not teacher:
            return True, ""
        if not teacher.subjects.filter(id=subject.id).exists():
            return False, (
                f"Vous n'êtes pas autorisé à noter en {subject.name}. "
                "Vous pouvez uniquement noter vos propres matières."
            )
        if not teacher.classes.filter(id=student.current_class_id).exists():
            return False, (
                f"L'élève {student.get_full_name()} n'est pas dans vos classes."
            )
        return True, ""

    # ──────────────────────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────────────────────

    def perform_create(self, serializer):
        teacher = self._resolve_teacher()
        data    = serializer.validated_data
        subject = data.get("subject")
        student = data.get("student")

        # Élève inactif
        if student and (not student.is_active or (student.user and not student.user.is_active)):
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Impossible d'ajouter une note : cet élève est désactivé.")

        # Permission enseignant
        if teacher and subject and student:
            ok, err = self._validate_teacher_permission(teacher, subject, student)
            if not ok:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(err)

        # Auto-assign active school year if missing
        save_kwargs = {"teacher": teacher} if teacher else {}
        if not data.get("school_year"):
            from apps.schools.models import SchoolYear
            school = get_request_school(self.request) or (student.school if student else None)
            active = SchoolYear.objects.filter(school=school, is_current=True).first()
            if active:
                save_kwargs["school_year"] = active

        # Lien vers l'inscription annuelle (StudentEnrollment) — socle de la
        # refonte "années scolaires" : la note est rattachée à l'ANNÉE
        # D'INSCRIPTION de l'élève, pas seulement à un couple (élève, année)
        # libre qui pourrait diverger de sa classe réelle cette année-là.
        school_year_for_enrollment = save_kwargs.get("school_year") or data.get("school_year")
        if student and school_year_for_enrollment:
            from apps.students.services import _get_or_create_enrollment
            enrollment, _ = _get_or_create_enrollment(student, school_year_for_enrollment.id)
            save_kwargs["enrollment"] = enrollment

        grade = serializer.save(**save_kwargs)
        _log_grade(grade, None, "", "create", self.request.user)
        logger.info(f"Grade created: {grade} by {self.request.user.email}")

        # Notification
        try:
            from apps.notifications.utils import create_notification, notification_path
            if grade.student.user:
                create_notification(
                    grade.student.user, "grade",
                    f"Nouvelle note en {grade.subject.name}: {grade.value}/20",
                    f"Période {grade.period} — {grade.subject.name}: {grade.value}/20",
                    related_url=notification_path(grade.student.user, "grades"),
                )
            # FIX (notifications) : les parents ne recevaient jamais de
            # notification de note — seul l'élève était notifié.
            for ps in grade.student.parents.select_related("parent__user").all():
                create_notification(
                    ps.parent.user, "grade",
                    f"Nouvelle note pour {grade.student.get_full_name()} en {grade.subject.name}: {grade.value}/20",
                    f"Période {grade.period} — {grade.subject.name}: {grade.value}/20",
                    related_url=notification_path(ps.parent.user, "grades"),
                )
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    def perform_update(self, serializer):
        instance   = self.get_object()
        teacher    = self._resolve_teacher()
        new_subject = serializer.validated_data.get("subject", instance.subject)
        new_student = serializer.validated_data.get("student", instance.student)

        if teacher:
            ok, err = self._validate_teacher_permission(teacher, new_subject, new_student)
            if not ok:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(err)

        old_value   = instance.value
        old_comment = instance.comment
        new_value   = serializer.validated_data.get("value", old_value)

        if abs(float(new_value) - float(old_value)) > 5:
            logger.warning(f"Large grade modification: {instance} by {self.request.user.email}")

        grade = serializer.save()
        _log_grade(grade, old_value, old_comment, "update", self.request.user,
                   justification=self.request.data.get("justification", ""))

    def destroy(self, request, *args, **kwargs):
        """Soft delete avec justification obligatoire."""
        instance = self.get_object()
        if instance.is_deleted:
            return Response({"detail": "Déjà supprimé."}, status=status.HTTP_400_BAD_REQUEST)
        # FIX: justification obligatoire pour la suppression
        justification = request.data.get("justification", "").strip()
        if not justification:
            return Response({"error": "La justification est obligatoire pour supprimer une note."}, status=status.HTTP_400_BAD_REQUEST)
        old_value = instance.value
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        instance.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])
        _log_grade(instance, old_value, instance.comment, "delete", request.user, justification=justification)
        logger.info(f"Grade soft-deleted: {instance} by {request.user.email} — {justification}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ──────────────────────────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """POST /api/grades/{id}/restore/"""
        grade = Grade.objects.get(pk=pk)
        if not grade.is_deleted:
            return Response({"detail": "Cette note n'est pas supprimée."}, status=400)
        grade.is_deleted = False
        grade.deleted_at = None
        grade.deleted_by = None
        grade.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])
        _log_grade(grade, grade.value, grade.comment, "update", request.user,
                   justification="Restauration de note supprimée")
        return Response(GradeSerializer(grade).data)

    @action(detail=True, methods=["get"])
    def grade_history(self, request, pk=None):
        grade = self.get_object()
        return Response(GradeHistorySerializer(grade.history.all(), many=True).data)

    @action(detail=False, methods=["post"])
    def bulk_save(self, request):
        """
        POST /api/grades/bulk_save/
        Crée de nouvelles notes en masse (multi-notes autorisées).
        """
        grades_data = request.data.get("grades", [])
        teacher     = self._resolve_teacher()
        school      = get_request_school(request)
        saved, errors = 0, []

        for item in grades_data:
            try:
                from apps.students.models import Student
                from apps.subjects.models import Subject
                from apps.schools.models import SchoolYear
                from apps.students.services import get_or_create_enrollment

                # FIX SÉCURITÉ (v29) : sans ce filtrage par tenant, un
                # enseignant pouvait soumettre l'ID d'un élève/matière/année
                # appartenant à un AUTRE établissement et créer une note
                # dessus (IDOR cross-tenant).
                student_qs = Student.objects.all()
                subject_qs = Subject.objects.all()
                year_qs = SchoolYear.objects.all()
                if school is not None:
                    student_qs = student_qs.filter(school=school)
                    subject_qs = subject_qs.filter(school=school)
                    year_qs = year_qs.filter(school=school)

                student     = student_qs.get(pk=item["student"])
                subject     = subject_qs.get(pk=item["subject"])
                school_year = year_qs.get(pk=item["school_year"])

                if teacher:
                    ok, err = self._validate_teacher_permission(teacher, subject, student)
                    if not ok:
                        errors.append({"item": item, "error": err})
                        continue

                enrollment, _ = get_or_create_enrollment(student, school_year.id)

                # CORRECTION : crée toujours une nouvelle note
                grade = Grade.objects.create(
                    student=student,
                    subject=subject,
                    school_year=school_year,
                    enrollment=enrollment,
                    period=item["period"],
                    value=item["value"],
                    note_type=item.get("note_type", "devoir"),
                    note_coefficient=item.get("note_coefficient", 1),
                    comment=item.get("comment", ""),
                    teacher=teacher,
                )
                _log_grade(grade, None, "", "create", request.user)
                saved += 1

            except Exception as e:
                errors.append({"item": item, "error": str(e)})

        return Response({"saved": saved, "errors": errors})

    @action(detail=False, methods=["get"])
    def averages(self, request):
        """GET /api/grades/averages/?student=&period=&school_year=
        FIX v26: auto-détecte l'élève quand l'utilisateur connecté est un élève.
        """
        user           = request.user
        student_id     = request.query_params.get("student")
        period         = request.query_params.get("period")
        school_year_id = request.query_params.get("school_year")

        # Auto-detect student for authenticated student users
        if not student_id:
            if user.is_student():
                try:
                    student_id = str(user.student_profile.id)
                except Exception:
                    return Response({"error": "Profil élève introuvable."}, status=404)
            elif user.is_parent():
                # Parent without explicit student → error (need to specify child)
                return Response({"error": "Paramètre student requis pour les parents."}, status=400)
            else:
                return Response({"error": "student requis"}, status=400)

        from apps.students.models import Student
        from apps.schools.models import SchoolYear
        school = get_request_school(request)
        try:
            student_qs = Student.objects.all()
            if school is not None:
                student_qs = student_qs.filter(school=school)
            student = student_qs.get(pk=student_id)

            # FIX v41 (500 console) : résolution robuste de l'année.
            # - superadmin/élève sans tenant : on résout sur l'établissement
            #   DE L'ÉLÈVE (school peut être None) ;
            # - année inexistante : repli sur l'année active plutôt qu'une
            #   exception non gérée (SchoolYear.DoesNotExist → 500).
            year_school = school or student.school
            year_qs = SchoolYear.objects.filter(school=year_school)
            school_year = None
            if school_year_id:
                school_year = year_qs.filter(pk=school_year_id).first()
            if school_year is None:
                school_year = year_qs.filter(is_current=True).first()
            if school_year is None:
                return Response({
                    "average": None, "student": student_id,
                    "period": period, "by_subject": {},
                })

            avg = Grade.calculate_average(student, school_year, period)

            # Détail par matière si période spécifiée
            subject_avgs = {}
            if period and period != "annual":
                for sid, info in Grade.get_subject_averages(student, school_year, period).items():
                    # FIX v41 : average peut être None (matière non notée, v32)
                    # → float(None) plantait en 500. On garde None tel quel.
                    subject_avgs[sid] = {
                        "name":        info["subject_name"],
                        "coefficient": info["coefficient"],
                        "average":     float(info["average"]) if info["average"] is not None else None,
                        "has_notes":   info["has_notes"],
                        "notes_count": len(info["notes"]),
                    }

            return Response({
                "average":     float(avg) if avg is not None else None,
                "student":     student_id,
                "period":      period,
                "by_subject":  subject_avgs,
            })
        except Student.DoesNotExist:
            return Response({"error": "Élève introuvable"}, status=404)
        except Exception as exc:  # pragma: no cover — filet de sécurité
            # FIX v41 : un tableau de bord élève ne doit jamais casser sur le
            # calcul de moyenne. On journalise et on renvoie une valeur nulle.
            import logging
            logging.getLogger(__name__).exception("averages failed: %s", exc)
            return Response({
                "average": None, "student": student_id,
                "period": period, "by_subject": {},
            })

    @action(detail=False, methods=["get"], url_path="student-summary")
    def student_summary(self, request):
        """
        GET /api/grades/student-summary/?student=&period=&school_year=
        Full summary per student: all subjects with averages, letters, notes detail.
        FIX v26: auto-détecte l'élève quand l'utilisateur connecté est un élève.
        """
        user           = request.user
        student_id     = request.query_params.get("student")
        period         = request.query_params.get("period")
        school_year_id = request.query_params.get("school_year")

        if not student_id:
            if user.is_student():
                try:
                    student_id = str(user.student_profile.id)
                except Exception:
                    return Response({"error": "Profil élève introuvable."}, status=404)
            else:
                return Response({"error": "student requis"}, status=400)

        from apps.students.models import Student
        from apps.schools.models import SchoolYear
        from .models import get_letter_grade, get_appreciation

        school = get_request_school(request)
        try:
            student_qs = Student.objects.all()
            if school is not None:
                student_qs = student_qs.filter(school=school)
            student = student_qs.get(pk=student_id)
        except Student.DoesNotExist:
            return Response({"error": "Élève introuvable"}, status=404)

        # RBAC: vérifier que le demandeur a le droit de voir cet élève
        user = request.user
        if user.role_level < 50:  # Moins que teacher
            if user.is_parent():
                has_access = student.parents.filter(parent__user=user).exists()
                if not has_access:
                    return Response({"error": "Accès refusé."}, status=403)
            elif user.is_student():
                if not hasattr(student, 'user') or student.user != user:
                    return Response({"error": "Accès refusé."}, status=403)

        # FIX v33 : un superadmin n'a pas d'établissement (school=None) —
        # l'ancien filtre school=None rendait l'année introuvable (404) et
        # cassait tout le Résumé par élève. On résout l'année sur le tenant
        # si présent, sinon sur l'établissement de l'élève.
        year_qs = SchoolYear.objects.all()
        year_qs = year_qs.filter(school=school) if school is not None else year_qs.filter(school=student.school)
        school_year = (
            year_qs.filter(pk=school_year_id).first()
            if school_year_id
            else year_qs.filter(is_current=True).first()
        )
        if not school_year:
            return Response({"error": "Année scolaire introuvable"}, status=404)

        # Si aucune période fournie, défaut = T1
        if not period:
            period = "T1"

        avg = Grade.calculate_average(student, school_year, period)
        letter, meaning, stars = get_letter_grade(avg)

        # Subject averages with full detail
        if period and period != "annual":
            subject_avgs = Grade.get_subject_averages(student, school_year, period)
        else:
            from apps.bulletins.pdf_generator import _build_annual_subject_data
            subject_avgs = _build_annual_subject_data(student, school_year)

        subjects_list = []
        for sid, info in subject_avgs.items():
            # FIX v33 : average peut être None (matière non notée, exclue des moyennes)
            subj_letter, subj_meaning, subj_stars = get_letter_grade(info["average"])
            if subj_letter is None:
                subj_letter, subj_meaning, subj_stars = "—", "Non noté", 0
            notes_serialized = [
                {
                    "id": n.id,
                    "value": float(n.value),
                    "note_type": n.note_type,
                    "note_coefficient": n.note_coefficient,
                    "comment": n.comment,
                }
                for n in info.get("notes", [])
            ]
            subjects_list.append({
                "subject_id":   sid,
                "subject_name": info["subject_name"],
                "coefficient":  info["coefficient"],
                "language":     info.get("language", "fr"),
                "average":      float(info["average"]) if info["average"] is not None else None,
                "letter":       subj_letter,
                "meaning":      subj_meaning,
                "stars":        subj_stars,
                "has_notes":    info["has_notes"],
                "notes":        notes_serialized,
            })

        # Rank in class — classe résolue pour l'ANNÉE demandée (FIX v33)
        student_class = Grade._class_for_year(student, school_year)
        rank = None
        total_in_class = 0
        if student_class:
            from apps.students.models import StudentEnrollment
            class_students = list(Student.objects.filter(
                enrollments__school_year=school_year,
                enrollments__class_obj=student_class,
                is_active=True,
            ).distinct()) or list(student_class.students.filter(is_active=True))
            total_in_class = len(class_students)
            avgs_list = []
            for s in class_students:
                a = Grade.calculate_average(s, school_year, period)
                if a is not None:
                    avgs_list.append((s.id, float(a)))
            avgs_list.sort(key=lambda x: -x[1])
            for r, (sid, _) in enumerate(avgs_list, 1):
                if sid == student.id:
                    rank = r
                    break

        return Response({
            "student_id":   student.id,
            "student_name": student.get_full_name(),
            "class_name":   student_class.name if student_class else None,
            "school_year":  school_year.name,
            "period":       period,
            "average":      float(avg) if avg is not None else None,
            "letter":       letter,
            "meaning":      meaning,
            "stars":        stars,
            "appreciation": get_appreciation(avg),
            "rank":         rank,
            "total_in_class": total_in_class,
            "subjects":     subjects_list,
        })

    @action(detail=False, methods=["get"], url_path="class-averages")

    def class_averages(self, request):
        """GET /api/grades/class-averages/?class=&period=&school_year="""
        class_id       = request.query_params.get("class")
        period         = request.query_params.get("period")
        school_year_id = request.query_params.get("school_year")

        if not class_id:
            return Response({"error": "class requis"}, status=400)

        from apps.students.models import Student
        from apps.schools.models import SchoolYear

        school = get_request_school(request)
        school_year = (
            SchoolYear.objects.filter(school=school, pk=school_year_id).first()
            if school_year_id
            else SchoolYear.objects.filter(school=school, is_current=True).first()
        )

        students = Student.objects.filter(current_class_id=class_id, is_active=True)
        if school is not None:
            students = students.filter(school=school)
        elif not request.user.is_superadmin():
            students = students.none()
        data = []
        for s in students:
            avg = Grade.calculate_average(s, school_year, period)
            data.append({
                "student_id":   s.id,
                "student_name": s.get_full_name(),
                "average":      float(avg) if avg is not None else None,
            })

        data.sort(key=lambda x: -(x["average"] or 0))
        for i, d in enumerate(data, 1):
            d["rank"] = i

        return Response(data)


# (FIX v32) _ensure_zeros_for_period supprimé : les matières non notées
# ne génèrent plus de notes à 0 — elles sont exclues des moyennes.

# ──────────────────────────────────────────────────────────────────────────────
# Bilingual grades endpoint (appended to GradeViewSet via monkey-patch workaround)
# ──────────────────────────────────────────────────────────────────────────────

from rest_framework.decorators import api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated as IA


@api_view(['GET'])
@pc([IA])
def bilingual_averages_view(request):
    """
    GET /api/grades/bilingual/?student=&period=&school_year=
    Returns full bilingual breakdown: FR avg, EN avg, bilingual avg (FR×60%+EN×40%)
    FIX v26: auto-détecte l'élève si user est student, rend period optionnel.
    """
    user           = request.user
    student_id     = request.query_params.get('student')
    period         = request.query_params.get('period')
    school_year_id = request.query_params.get('school_year')

    # Auto-detect student for authenticated student users
    if not student_id:
        if user.is_student():
            try:
                student_id = str(user.student_profile.id)
            except Exception:
                return Response({'error': 'Profil élève introuvable.'}, status=404)
        elif not student_id:
            return Response({'error': 'student requis.'}, status=400)

    from apps.students.models import Student
    from apps.schools.models import SchoolYear

    school = get_request_school(request)
    try:
        student_qs = Student.objects.all()
        if school is not None:
            student_qs = student_qs.filter(school=school)
        student = student_qs.get(pk=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Élève introuvable.'}, status=404)

    # FIX v33 : superadmin (school=None) — résoudre l'année sur l'établissement
    # de l'élève, sinon le calcul bilingue était toujours "indisponible".
    year_qs = SchoolYear.objects.filter(school=school) if school is not None \
        else SchoolYear.objects.filter(school=student.school)
    if school_year_id:
        school_year = year_qs.filter(pk=school_year_id).first()
    else:
        school_year = year_qs.filter(is_current=True).first()

    if not school_year:
        return Response({'error': 'Année scolaire introuvable.'}, status=404)

    # FIX v42 : filet de sécurité — le calcul bilingue ne doit jamais renvoyer
    # 500 (message trompeur « Calcul indisponible » côté UI). Toute erreur
    # imprévue est journalisée et renvoie une charge utile neutre (« pas de
    # matières ») que l'interface sait afficher proprement.
    try:
        if not period or period == 'annual':
            data = Grade.get_annual_bilingual(student, school_year)
        else:
            data = Grade.calculate_bilingual_averages(student, school_year, period)
    except Exception as exc:  # pragma: no cover
        import logging
        logging.getLogger(__name__).exception("bilingual failed: %s", exc)
        data = {
            'fr_average': None, 'en_average': None, 'bilingual_average': None,
            'fr_subjects': [], 'en_subjects': [],
            'has_fr_subjects': False, 'has_en_subjects': False,
            'formula': Grade.BILINGUAL_FORMULA,
        }

    # FIX v33 : les entrées matières embarquent des instances Grade (clé
    # 'notes') non sérialisables en JSON → on les retire de la réponse.
    def _strip_notes(obj):
        if isinstance(obj, dict):
            return {k: _strip_notes(v) for k, v in obj.items() if k != 'notes'}
        if isinstance(obj, list):
            return [_strip_notes(i) for i in obj]
        return obj
    data = _strip_notes(data)

    # Convert Decimals to float for JSON
    def _convert(obj):
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert(i) for i in obj]
        from decimal import Decimal
        if isinstance(obj, Decimal):
            return float(obj)
        return obj

    return Response(_convert(data))


from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes as drf_permission_classes

@api_view(["GET"])
@drf_permission_classes([IsAuthenticated])
def all_history_view(request):
    """
    GET /api/grades/all-history/?student=&school_year=&limit=200
    Historique global de toutes les modifications de notes (admin only).
    FIX v28 — endpoint dédié, unique, sans doublon.
    """
    user = request.user
    if user.role_level < 80:
        return Response({"error": "Accès refusé."}, status=403)

    qs = GradeHistory.objects.select_related(
        "grade__student", "grade__subject", "grade__school_year", "changed_by"
    ).order_by("-changed_at")

    school = get_request_school(request)
    if school is not None:
        qs = qs.filter(grade__student__school=school)
    elif not user.is_superadmin():
        qs = qs.none()

    student_id = request.query_params.get("student")
    if student_id:
        qs = qs.filter(grade__student_id=student_id)

    school_year_id = request.query_params.get("school_year")
    if school_year_id:
        qs = qs.filter(grade__school_year_id=school_year_id)

    limit = min(int(request.query_params.get("limit", 200)), 500)
    qs = list(qs[:limit])

    data = []
    for h in qs:
        data.append({
            "id":             h.id,
            "grade_id":       h.grade_id,
            "student_name":   h.grade.student.get_full_name() if h.grade.student else "—",
            "student_id":     h.grade.student_id,
            "subject_name":   h.grade.subject.name if h.grade.subject else "—",
            "school_year":    h.grade.school_year.name if h.grade.school_year else "—",
            "period":         h.grade.period,
            "old_value":      float(h.old_value) if h.old_value is not None else None,
            "new_value":      float(h.new_value) if h.new_value is not None else None,
            "old_comment":    h.old_comment,
            "new_comment":    h.new_comment,
            "justification":  h.justification,
            "action":         h.action,
            "action_display": "Création" if h.action == "create" else "Modification",
            "changed_by":     h.changed_by.get_full_name() if h.changed_by else "—",
            "changed_at":     h.changed_at.isoformat(),
        })
    return Response({"results": data, "count": len(data)})
