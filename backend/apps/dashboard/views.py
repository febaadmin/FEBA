from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from django.utils import timezone
import logging

from apps.core.tenancy import get_request_school

logger = logging.getLogger("apps")


def safe_float(val):
    try:
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role_level < 80:
            return Response({"error": "Accès refusé."}, status=403)

        from apps.students.models import Student
        from apps.teachers.models import Teacher
        from apps.classes.models import Class
        from apps.payments.models import Payment
        from apps.schools.models import SchoolYear
        from apps.announcements.models import Announcement
        from apps.bulletins.models import Bulletin

        # FIX SÉCURITÉ CRITIQUE (v29) : ce tableau de bord agrégeait
        # littéralement les données de TOUS les établissements de la
        # plateforme (élèves, enseignants, paiements, classes...) sans
        # AUCUN filtre — la fuite la plus visible de tout l'audit, vue
        # par chaque administrateur dès sa connexion. Corrigé par un
        # filtrage systématique par établissement courant.
        school = get_request_school(request)
        if school is None and not request.user.is_superadmin():
            return Response({"error": "Aucun établissement rattaché à ce compte."}, status=403)

        # FIX: Filtrer par année scolaire ACTIVE (de CE tenant) pour des statistiques exactes
        active_year = SchoolYear.objects.filter(school=school, is_current=True).first()
        now = timezone.now()

        # Revenus mensuels filtrés sur l'année active uniquement
        monthly_revenue = []
        for m in range(1, 13):
            pay_qs = Payment.objects.filter(
                student__school=school,
                payment_date__year=now.year,
                payment_date__month=m,
                is_deleted=False,
            )
            if active_year:
                pay_qs = pay_qs.filter(school_year=active_year)
            total = pay_qs.aggregate(s=Sum("amount"))["s"] or 0
            monthly_revenue.append({"month": m, "amount": safe_float(total)})

        # KPIs filtrés par année active ET par établissement.
        # FIX (audit) : user__is_active=True excluait les élèves SANS compte
        # utilisateur lié (user=None) — ils disparaissaient du comptage.
        from django.db.models import Q
        student_qs = Student.objects.filter(school=school, is_active=True).filter(
            Q(user__isnull=True) | Q(user__is_active=True)
        )
        # FIX v20: Filtrer les élèves par année active (school_year field)
        if active_year:
            student_qs = student_qs.filter(school_year=active_year)
        payment_qs = Payment.objects.filter(student__school=school, is_deleted=False)
        if active_year:
            # Élèves avec une inscription dans la classe courante (année active)
            payment_qs = payment_qs.filter(school_year=active_year)

        monthly_pay = payment_qs.filter(
            payment_date__month=now.month, payment_date__year=now.year
        ).aggregate(s=Sum("amount"))["s"]
        ytd_pay = payment_qs.filter(
            payment_date__year=now.year
        ).aggregate(s=Sum("amount"))["s"]

        # Classes actives (ayant des élèves cette année, dans cet établissement)
        active_class_qs = Class.objects.filter(school_year__school=school)
        if active_year:
            active_class_qs = active_class_qs.filter(school_year=active_year)

        # Bulletins générés cette année (cet établissement)
        bulletin_count = 0
        if active_year:
            bulletin_count = Bulletin.objects.filter(student__school=school, school_year=active_year).count()

        return Response({
            "active_year": {"id": active_year.id, "name": active_year.name} if active_year else None,
            "kpis": {
                "total_students": student_qs.count(),
                "total_teachers": Teacher.objects.filter(user__is_active=True, user__school=school).count(),
                "total_classes": active_class_qs.count(),
                "monthly_revenue": safe_float(monthly_pay),
                "total_revenue_ytd": safe_float(ytd_pay),
                "announcements": Announcement.objects.filter(is_published=True, author__school=school).count(),
                "total_bulletins": bulletin_count,
            },
            "monthly_revenue": monthly_revenue,
            "recent_payments": [
                {
                    "id": p.id,
                    "student": p.student.get_full_name(),
                    "student_class": p.student.current_class.name if p.student.current_class else "—",
                    "amount": safe_float(p.amount),
                    "type": p.get_payment_type_display(),
                    "payment_type": p.payment_type,
                    "date": str(p.payment_date),
                    "reference_number": p.reference_number,
                }
                for p in payment_qs.select_related("student__current_class").order_by("-payment_date")[:5]
            ],
            "recent_students": [
                {
                    "id": s.id,
                    "name": s.get_full_name(),
                    "class": s.current_class.name if s.current_class else "—",
                    "matricule": s.matricule,
                    "enrollment_date": str(s.enrollment_date),
                }
                for s in student_qs.select_related("current_class").order_by("-enrollment_date")[:5]
            ],
            "students_by_level": list(
                student_qs
                .values("current_class__level__name")
                .annotate(count=Count("id"))
                .order_by("current_class__level__order")
            ),
        })


class TeacherDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_teacher():
            return Response({"error": "Accès refusé."}, status=403)

        try:
            teacher = user.teacher_profile
        except Exception:
            return Response({"error": "Profil enseignant introuvable."}, status=404)

        from apps.students.models import Student
        from apps.homework.models import Homework
        from apps.attendance.models import Attendance
        from apps.grades.models import Grade
        from apps.schools.models import SchoolYear

        today = timezone.now().date()
        week_start = today - timezone.timedelta(days=today.weekday())
        school = get_request_school(request)
        active_year = SchoolYear.objects.filter(school=school, is_current=True).first()

        my_classes = teacher.classes.all()
        my_students = Student.objects.filter(current_class__in=my_classes, is_active=True)

        recent_grades_qs = Grade.objects.filter(teacher=teacher).select_related("student", "subject").order_by("-created_at")
        if active_year:
            recent_grades_qs = recent_grades_qs.filter(school_year=active_year)
        recent_grades = recent_grades_qs[:5]

        hw_qs = Homework.objects.filter(teacher=teacher, due_date__gte=today)
        if active_year:
            hw_qs = hw_qs.filter(school_year=active_year)

        absent_qs = Attendance.objects.filter(student__current_class__in=my_classes, date__gte=week_start, status="absent")
        if active_year:
            absent_qs = absent_qs.filter(school_year=active_year)

        return Response({
            "kpis": {
                "my_classes": my_classes.count(),
                "my_students": my_students.count(),
                "pending_homework": hw_qs.count(),
                "absences_this_week": absent_qs.count(),
                "grades_this_month": Grade.objects.filter(
                    teacher=teacher,
                    created_at__month=today.month,
                    created_at__year=today.year,
                ).count(),
            },
            "my_classes": [
                {
                    "id": c.id,
                    "name": c.name,
                    "level": c.level.name if c.level else "—",
                    "student_count": Student.objects.filter(current_class=c, is_active=True).count(),
                }
                for c in my_classes.select_related("level")
            ],
            "recent_grades": [
                {
                    "student": g.student.get_full_name(),
                    "subject": g.subject.name,
                    "value": float(g.value),
                    "period": g.period,
                    "date": str(g.graded_at or g.created_at.date()),
                }
                for g in recent_grades
            ],
        })


class ParentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_parent():
            return Response({"error": "Accès refusé."}, status=403)

        try:
            parent = user.parent_profile
        except Exception:
            return Response({"error": "Profil parent introuvable."}, status=404)

        from apps.grades.models import Grade
        from apps.schools.models import SchoolYear
        from apps.attendance.models import Attendance
        from apps.homework.models import Homework

        school_year = SchoolYear.objects.filter(school=get_request_school(request), is_current=True).first()
        today = timezone.now().date()

        children_links = parent.children_links.select_related(
            "student__current_class__level",
            "student__school_year",
        ).all()

        children_data = []
        for link in children_links:
            child = link.student
            # FIX BUG N°3 : calculate_average(child, school_year) sans période
            # filtrait sur period=None → jamais aucune note → moyenne toujours
            # vide ("—") sur le tableau de bord parent. La moyenne générale
            # est la moyenne annuelle (moyenne des trimestres notés).
            avg = Grade.calculate_annual_average(child, school_year) if school_year else None
            avg_t1 = Grade.calculate_average(child, school_year, "T1") if school_year else None
            avg_t2 = Grade.calculate_average(child, school_year, "T2") if school_year else None
            avg_t3 = Grade.calculate_average(child, school_year, "T3") if school_year else None
            from apps.grades.models import get_appreciation
            absent_qs = Attendance.objects.filter(student=child, status="absent")
            if school_year:
                absent_qs = absent_qs.filter(school_year=school_year)
            absent_count = absent_qs.count()
            hw_qs = Homework.objects.filter(cls=child.current_class, due_date__gte=today) if child.current_class else Homework.objects.none()
            if school_year:
                hw_qs = hw_qs.filter(school_year=school_year)
            hw_count = hw_qs.count()

            children_data.append({
                "id": child.id,
                "name": child.get_full_name(),
                "first_name": child.first_name,
                "last_name": child.last_name,
                "matricule": child.matricule,
                "gender": child.gender,
                "class": child.current_class.name if child.current_class else "—",
                "class_id": child.current_class.id if child.current_class else None,
                "level": child.current_class.level.name if child.current_class and child.current_class.level else "—",
                "school_year": child.school_year.name if child.school_year else "—",
                "average": safe_float(avg) if avg is not None else None,
                "average_t1": safe_float(avg_t1) if avg_t1 is not None else None,
                "average_t2": safe_float(avg_t2) if avg_t2 is not None else None,
                "average_t3": safe_float(avg_t3) if avg_t3 is not None else None,
                "appreciation": get_appreciation(avg) if avg is not None else None,
                "progression": (
                    round(safe_float(avg_t2) - safe_float(avg_t1), 2)
                    if avg_t1 is not None and avg_t2 is not None else None
                ),
                "absent_count": absent_count,
                "pending_homework": hw_count,
                "relationship": link.relationship,
                "is_primary_contact": link.is_primary_contact,
            })

        return Response({
            "children": children_data,
            "total_children": len(children_data),
        })


class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_student():
            return Response({"error": "Accès refusé."}, status=403)

        try:
            student = user.student_profile
        except Exception:
            return Response({"error": "Profil élève introuvable."}, status=404)

        from apps.grades.models import Grade
        from apps.homework.models import Homework
        from apps.attendance.models import Attendance
        from apps.schools.models import SchoolYear
        from apps.announcements.models import Announcement
        from django.db.models import Q

        school_year = SchoolYear.objects.filter(school=get_request_school(request), is_current=True).first()
        today = timezone.now().date()

        # FIX BUG N°3 : calculate_average(student, school_year) sans période
        # filtrait sur period=None → la « Moyenne générale » du tableau de
        # bord élève était toujours vide ("—"). La moyenne générale est la
        # moyenne annuelle (moyenne des trimestres effectivement notés).
        avg = Grade.calculate_annual_average(student, school_year) if school_year else None
        grades_t1 = Grade.calculate_average(student, school_year, "T1") if school_year else None
        grades_t2 = Grade.calculate_average(student, school_year, "T2") if school_year else None
        grades_t3 = Grade.calculate_average(student, school_year, "T3") if school_year else None
        from apps.grades.models import get_appreciation

        # Filter attendance by active year
        att_base = Attendance.objects.filter(student=student)
        if school_year:
            att_base = att_base.filter(school_year=school_year)
        absent_count = att_base.filter(status="absent").count()
        late_count = att_base.filter(status="late").count()

        # Recent grades filtered by active year
        recent_grades_qs = Grade.objects.filter(student=student).select_related("subject").order_by("-created_at")
        if school_year:
            recent_grades_qs = recent_grades_qs.filter(school_year=school_year)
        recent_grades = recent_grades_qs[:5]

        # Announcements for student
        announcements = Announcement.objects.filter(
            is_published=True
        ).filter(
            Q(target_roles__contains=["student"]) | Q(target_roles__contains=["all"])
        ).order_by("-created_at")[:3]

        return Response({
            "student": {
                "id": student.id,
                "name": student.get_full_name(),
                "first_name": student.first_name,
                "last_name": student.last_name,
                "matricule": student.matricule,
                "class": student.current_class.name if student.current_class else "—",
                "class_id": student.current_class.id if student.current_class else None,
                "level": student.current_class.level.name if student.current_class and student.current_class.level else "—",
                "school_year": student.school_year.name if student.school_year else "—",
                "gender": student.gender,
            },
            "kpis": {
                "average": safe_float(avg) if avg is not None else None,
                "average_t1": safe_float(grades_t1) if grades_t1 is not None else None,
                "average_t2": safe_float(grades_t2) if grades_t2 is not None else None,
                "average_t3": safe_float(grades_t3) if grades_t3 is not None else None,
                "annual_average": safe_float(avg) if avg is not None else None,
                "appreciation": get_appreciation(avg) if avg is not None else None,
                "progression": (
                    round(safe_float(grades_t2) - safe_float(grades_t1), 2)
                    if grades_t1 is not None and grades_t2 is not None else None
                ),
                "absent_count": absent_count,
                "late_count": late_count,
                "pending_homework": (
                    Homework.objects.filter(cls=student.current_class, due_date__gte=today, school_year=school_year).count()
                    if student.current_class and school_year else
                    Homework.objects.filter(cls=student.current_class, due_date__gte=today).count()
                    if student.current_class else 0
                ),
            },
            "recent_grades": [
                {
                    "subject": g.subject.name,
                    "value": float(g.value),
                    "period": g.period,
                    "coefficient": g.subject.coefficient,
                }
                for g in recent_grades
            ],
            "announcements": [
                {
                    "id": a.id,
                    "title": a.title,
                    "content": a.content[:200],
                    "date": str(a.created_at.date()),
                }
                for a in announcements
            ],
        })