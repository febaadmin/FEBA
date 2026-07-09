from feba_project.bulk_delete import BulkDeleteMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant, require_school_or_403
from .models import Student, StudentEnrollment
from .serializers import StudentSerializer, StudentEnrollmentSerializer


def resolve_school_for_year(request, year_id):
    """
    Établissement (tenant) d'une opération de promotion/inscription.

    FIX v31 (cause racine) : pour un SUPERADMIN, get_request_school()
    renvoie None (il n'a pas d'établissement propre) → toutes les
    promotions échouaient avec "Établissement introuvable", alors que
    l'opération cible une année scolaire qui appartient sans ambiguïté
    à UN établissement. Le tenant est donc déduit de l'année cible.
    Pour tout autre rôle, l'établissement de l'utilisateur reste la
    seule source de vérité (l'année cible doit lui appartenir — la
    vérification tenant élève-par-élève du service s'en charge).
    """
    school = get_request_school(request)
    if school is None and request.user.is_superadmin() and year_id:
        from apps.schools.models import SchoolYear
        year = SchoolYear.objects.select_related('school').filter(pk=year_id).first()
        if year:
            return year.school
    return school


class StudentViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    # NOTE v31 : 'school_year' volontairement retiré des filterset_fields —
    # le filtre année est géré manuellement dans get_queryset via l'historique
    # des inscriptions (sinon django-filter ré-appliquerait le filtre sur le
    # pointeur Student.school_year et annulerait la correction).
    filterset_fields = ['current_class', 'is_active']
    search_fields = ['first_name', 'last_name', 'matricule']

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)

        qs = Student.objects.select_related(
            'current_class__level', 'school_year', 'school', 'user'
        ).prefetch_related(
            'enrollments__school_year', 'enrollments__class_obj__level'
        )
        # FIX v34 : les élèves DÉSACTIVÉS (soft delete) sont masqués par
        # défaut des listes actives ; ?include_inactive=1 les réaffiche
        # (écran de réactivation). Le filtre explicite ?is_active= reste
        # prioritaire via django-filter.
        params = self.request.query_params
        if not params.get('is_active') and not params.get('include_inactive'):
            qs = qs.filter(is_active=True)

        # --- Isolation multi-tenant : socle de toute requête ----------------
        if school is not None:
            qs = qs.filter(school=school)
        elif not (user.is_authenticated and user.is_superadmin()):
            return qs.none()
        # superadmin sans ?school_id= : vue plateforme volontaire (ex: support)

        # Filtre par année scolaire.
        # FIX v31 (cause racine) : filtrer sur Student.school_year (pointeur
        # "année courante") faisait disparaître les élèves des années passées
        # dès leur passage en classe supérieure. Le filtre interroge désormais
        # l'HISTORIQUE des inscriptions annuelles (StudentEnrollment), avec
        # repli sur le pointeur pour les élèves sans inscription formalisée.
        school_year = self.request.query_params.get('school_year')
        if school_year:
            from django.db.models import Q
            qs = qs.filter(
                Q(enrollments__school_year=school_year) | Q(school_year=school_year)
            ).distinct()

        if user.role_level >= 80:
            return qs
        if user.is_teacher():
            try:
                return qs.filter(current_class__in=user.teacher_profile.classes.all())
            except Exception:
                return qs.none()
        if user.is_parent():
            return qs.filter(parents__parent__user=user)
        if user.is_student():
            return qs.filter(user=user)
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrAbove(), IsSameTenant()]
        return [IsAuthenticated(), IsSameTenant()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        """Auto-assign tenant + active school year if not provided."""
        require_school_or_403(self.request.user)
        school = get_request_school(self.request)
        data = serializer.validated_data
        # FIX v31 : un superadmin n'a pas d'établissement propre — le tenant
        # est déduit de l'année scolaire fournie par le formulaire.
        if school is None and self.request.user.is_superadmin():
            sy = data.get('school_year')
            if sy is not None:
                school = sy.school
        extra = {}
        if school is not None:
            extra['school'] = school
        if not data.get('school_year'):
            from apps.schools.models import SchoolYear
            active = SchoolYear.objects.filter(school=school, is_current=True).first()
            if active:
                extra['school_year'] = active
        serializer.save(**extra)

    @action(detail=True, methods=['post'], url_path='enroll',
            permission_classes=[IsAuthenticated, IsAdminOrAbove])
    def enroll(self, request, pk=None):
        """
        POST /students/{id}/enroll/
        Inscrit un élève dans une année scolaire / classe.

        Payload attendu : { school_year: <id>, class_obj: <id>|null, promotion_status: str }
        Le champ 'student' n'est pas dans le payload : il est passé
        via serializer.save(student=student) après validation.

        FIX v29.2 : 'student' était dans les fields du serializer et
        requis dans le payload → erreur "student: Champ requis." invisible.
        Corrigé : student est désormais read_only dans le serializer.
        """
        student = self.get_object()
        serializer = StudentEnrollmentSerializer(
            data=request.data,
            context={'request': request, 'view': self},
        )
        if serializer.is_valid():
            school_year_id = request.data.get('school_year')
            # Désactiver l'inscription précédente pour la même année (si elle existait)
            StudentEnrollment.objects.filter(
                student=student, school_year_id=school_year_id
            ).update(is_active=False)
            enrollment = serializer.save(student=student)
            # Mettre à jour le pointeur "courant" de l'élève
            if enrollment.class_obj_id:
                student.current_class_id = enrollment.class_obj_id
            if school_year_id:
                student.school_year_id = school_year_id
            student.save(update_fields=['current_class', 'school_year'])
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Retourner les erreurs de validation telles quelles (message DRF précis)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='enroll-all-from-year',
            permission_classes=[IsAuthenticated, IsAdminOrAbove])
    def enroll_all_from_year(self, request):
        """
        POST /students/enroll-all-from-year/
        Body: { "source_year_id": X, "target_year_id": Y }
        Inscrit TOUS les élèves de l'année source dans l'année cible (1 clic).
        Préserve l'historique, ne duplique pas.
        Conservé pour compatibilité — utilise désormais le service partagé
        `bulk_promote_students` (voir apps/students/services.py).
        """
        from .services import bulk_promote_students

        source_year_id = request.data.get('source_year_id')
        target_year_id = request.data.get('target_year_id')
        if not (source_year_id and target_year_id):
            return Response({'error': 'source_year_id et target_year_id requis.'}, status=400)
        if str(source_year_id) == str(target_year_id):
            return Response({'error': 'Les années source et cible doivent être différentes.'}, status=400)
        school = resolve_school_for_year(request, target_year_id)

        result = bulk_promote_students(
            school=school,
            source_year_id=source_year_id,
            target_year_id=target_year_id,
            scope='year',
        )
        return Response(result)

    @action(detail=False, methods=['post'], url_path='enroll-class',
            permission_classes=[IsAuthenticated, IsAdminOrAbove])
    def enroll_class(self, request):
        """
        POST /students/enroll-class/
        Body: { "class_id": X, "target_year_id": Y, "new_class_id": Z (optional) }
        Inscrit tous les élèves d'une classe dans une nouvelle année.
        Conservé pour compatibilité — utilise désormais le service partagé.
        """
        from .services import bulk_promote_students

        class_id = request.data.get('class_id')
        target_year_id = request.data.get('target_year_id')
        school = resolve_school_for_year(request, target_year_id)
        new_class_id = request.data.get('new_class_id')

        if not (class_id and target_year_id):
            return Response({'error': 'class_id et target_year_id requis.'}, status=400)

        result = bulk_promote_students(
            school=school,
            target_year_id=target_year_id,
            scope='class',
            source_class_id=class_id,
            target_class_id=new_class_id,
        )
        return Response(result)

    @action(detail=False, methods=["post"], url_path="bulk-remove-from-year")
    def bulk_remove_from_year(self, request):
        """
        FIX v35 (vidéos fournies) — suppression EN MASSE depuis une année :
        retire uniquement les inscriptions de CETTE année pour les élèves
        sélectionnés. Les autres années restent strictement intactes.
        Body: { "ids": [...], "school_year_id": X }
        """
        ids = request.data.get("ids", [])
        year_id = request.data.get("school_year_id")
        if not ids or not isinstance(ids, list) or not year_id:
            return Response({"error": "ids (liste) et school_year_id requis."}, status=400)

        students = self.get_queryset().filter(id__in=ids)
        removed = 0
        for student in students:
            enrollment = student.enrollments.filter(school_year_id=year_id).first()
            if enrollment is None:
                continue
            enrollment.delete()
            removed += 1
            if str(student.school_year_id) == str(year_id):
                latest = student.enrollments.select_related("school_year").order_by(
                    "-school_year__start_date").first()
                student.school_year = latest.school_year if latest else None
                student.current_class = latest.class_obj if latest else None
                student.save(update_fields=["school_year", "current_class"])

        from apps.schools.models import SchoolYear
        year = SchoolYear.objects.filter(pk=year_id).first()
        return Response({
            "removed": removed,
            "detail": f"{removed} élève(s) retiré(s) de l'année "
                      f"{year.name if year else year_id}. Les autres années sont intactes.",
        })

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request, *args, **kwargs):
        """
        FIX v34 — la suppression en masse d'élèves DÉSACTIVE (soft delete)
        au lieu de détruire : l'historique multi-années est inviolable.
        """
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response({"error": "ids list required"}, status=400)
        qs = self.get_queryset().filter(id__in=ids)
        count = qs.count()
        from apps.accounts.models import CustomUser
        user_ids = list(qs.exclude(user=None).values_list("user_id", flat=True))
        qs.update(is_active=False)
        if user_ids:
            CustomUser.objects.filter(id__in=user_ids).update(is_active=False)
        return Response({"deleted": count, "soft": True,
                         "detail": f"{count} élève(s) désactivé(s) — historique conservé."})

    def destroy(self, request, *args, **kwargs):
        """
        FIX v34 — sémantique de suppression conforme au modèle multi-années :

        DELETE /students/{id}/            → DÉSACTIVATION (soft delete) :
            l'élève disparaît des listes actives mais TOUT son historique
            (inscriptions, notes, paiements de toutes les années) est conservé.

        DELETE /students/{id}/?hard=true  → suppression DÉFINITIVE, refusée
            tant que des données pédagogiques existent (notes, paiements,
            absences, bulletins, inscriptions) — le détail est renvoyé.
        """
        student = self.get_object()
        hard = str(request.query_params.get('hard', '')).lower() in ('1', 'true', 'yes')

        if not hard:
            student.is_active = False
            student.save(update_fields=['is_active'])
            if student.user_id:
                student.user.is_active = False
                student.user.save(update_fields=['is_active'])
            return Response({
                'detail': f"{student.get_full_name()} a été désactivé(e). "
                          "Son historique (toutes années) est conservé. "
                          "Utilisez ?hard=true pour une suppression définitive.",
                'soft_deleted': True,
            })

        deps = {
            'inscriptions': student.enrollments.count(),
            'notes': student.grades.count(),
            'paiements': student.payments.count(),
            'absences': student.attendance_records.count() if hasattr(student, 'attendance_records') else 0,
            'bulletins': student.bulletins.count() if hasattr(student, 'bulletins') else 0,
        }
        blocking = {k: v for k, v in deps.items() if v}
        if blocking:
            detail = ", ".join(f"{v} {k}" for k, v in blocking.items())
            return Response({
                'error': "Suppression définitive impossible : des données dépendent de cet élève "
                         f"({detail}). Retirez d'abord ses inscriptions annuelles ou utilisez la désactivation.",
                'dependencies': deps,
            }, status=409)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='remove-from-year')
    def remove_from_year(self, request, pk=None):
        """
        FIX v34 — retire l'élève d'UNE année scolaire uniquement :
        supprime son inscription annuelle (les notes/paiements de l'année
        sont conservés, détachés de l'inscription mais liés à l'élève et à
        l'année). Les autres années restent strictement intactes.
        Body: { "school_year_id": X }
        """
        student = self.get_object()
        year_id = request.data.get('school_year_id')
        if not year_id:
            return Response({'error': 'school_year_id requis.'}, status=400)

        enrollment = student.enrollments.filter(school_year_id=year_id).first()
        if enrollment is None:
            return Response({'error': "Cet élève n'est pas inscrit dans cette année."}, status=404)

        year_name = enrollment.school_year.name if enrollment.school_year else str(year_id)
        enrollment.delete()

        # Cohérence du pointeur "année courante" : s'il visait l'année
        # retirée, le repositionner sur l'inscription la plus récente restante.
        if str(student.school_year_id) == str(year_id):
            latest = student.enrollments.select_related('school_year').order_by(
                '-school_year__start_date').first()
            student.school_year = latest.school_year if latest else None
            student.current_class = latest.class_obj if latest else None
            student.save(update_fields=['school_year', 'current_class'])

        return Response({
            'detail': f"{student.get_full_name()} retiré(e) de l'année {year_name}. "
                      "Les autres années sont intactes.",
        })

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """Réactive un élève désactivé (annule le soft delete)."""
        student = self.get_object()
        student.is_active = True
        student.save(update_fields=['is_active'])
        if student.user_id:
            student.user.is_active = True
            student.user.save(update_fields=['is_active'])
        return Response({'detail': f"{student.get_full_name()} réactivé(e)."})

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        Parcours académique complet, année par année.

        FIX v31 : renvoie pour CHAQUE année le dossier de l'élève —
        classe, moyenne et nombre de notes, absences/retards/excusés,
        total payé et nombre de paiements, bulletins, devoirs de la
        classe, décision de passage. Toutes les données sont filtrées
        par l'année de l'inscription : consulter N-1, N-2, N-3 est
        possible sans jamais mélanger les années.
        """
        from django.db.models import Avg, Count, Sum, Q
        from apps.grades.models import Grade
        from apps.attendance.models import Attendance
        from apps.payments.models import Payment
        from apps.bulletins.models import Bulletin
        from apps.homework.models import Homework

        student = self.get_object()  # déjà filtré par tenant
        enrollments = StudentEnrollment.objects.filter(student=student).select_related(
            'school_year', 'class_obj__level'
        ).order_by('-school_year__start_date')

        payload = []
        for enr in enrollments:
            year = enr.school_year
            base = StudentEnrollmentSerializer(enr).data

            grades = Grade.objects.filter(student=student, school_year=year)
            g = grades.aggregate(count=Count('id'), average=Avg('value'))

            att = Attendance.objects.filter(student=student, school_year=year).aggregate(
                absences=Count('id', filter=Q(status='absent')),
                lates=Count('id', filter=Q(status='late')),
                excused=Count('id', filter=Q(status='excused')),
            )

            pay = Payment.objects.filter(student=student, school_year=year).aggregate(
                count=Count('id'), total=Sum('amount'),
            )

            base['stats'] = {
                'grades_count':   g['count'] or 0,
                'grades_average': round(float(g['average']), 2) if g['average'] is not None else None,
                'absences':       att['absences'] or 0,
                'lates':          att['lates'] or 0,
                'excused':        att['excused'] or 0,
                'payments_count': pay['count'] or 0,
                'payments_total': float(pay['total']) if pay['total'] is not None else 0,
                'bulletins_count': Bulletin.objects.filter(student=student, school_year=year).count(),
                'homework_count': (
                    Homework.objects.filter(cls=enr.class_obj, school_year=year).count()
                    if enr.class_obj_id else 0
                ),
            }
            payload.append(base)
        return Response(payload)

    @action(detail=False, methods=['post'], url_path='promote',
            permission_classes=[IsAuthenticated, IsAdminOrAbove])
    def promote(self, request):
        """
        Bulk promote students to a new school year (liste explicite d'élèves).
        Conservé pour compatibilité — utilise désormais le service partagé,
        qui vérifie que chaque élève appartient bien au tenant courant.
        """
        from .services import bulk_promote_students

        student_ids = request.data.get('student_ids', [])
        new_year_id = request.data.get('school_year_id')
        school = resolve_school_for_year(request, new_year_id)
        new_class_id = request.data.get('class_id')
        promotion_status = request.data.get('promotion_status', 'normal')

        if not (student_ids and new_year_id):
            return Response({'error': 'student_ids et school_year_id requis.'}, status=400)

        result = bulk_promote_students(
            school=school,
            target_year_id=new_year_id,
            scope='students',
            student_ids=student_ids,
            target_class_id=new_class_id,
            promotion_status=promotion_status,
        )
        return Response({'promoted': result['enrolled'], 'failed': result['failed']})

    @action(detail=False, methods=['post'], url_path='end-of-year-assistant',
            permission_classes=[IsAuthenticated, IsAdminOrAbove])
    def end_of_year_assistant(self, request):
        """
        POST /students/end-of-year-assistant/
        Assistant de fin d'année unifié — gère en un seul appel :
          - la promotion (normale, avec mention, redoublement, transfert de filière)
          - le départ de l'établissement
          - l'exclusion
          - la diplômation / fin de cycle

        Body :
        {
          "target_year_id": 12,
          "decisions": [
            {"student_id": 1, "action": "promote", "class_id": 45, "status": "normal"},
            {"student_id": 2, "action": "repeat",  "class_id": 12},
            {"student_id": 3, "action": "depart",  "reason": "Déménagement"},
            {"student_id": 4, "action": "exclude", "reason": "Conseil de discipline"},
            {"student_id": 5, "action": "graduate"}
          ]
        }

        Chaque décision est traitée indépendamment ; les échecs n'annulent
        pas les décisions déjà appliquées (retour détaillé par élève).
        """
        from .services import apply_end_of_year_decision

        target_year_id = request.data.get('target_year_id')
        decisions = request.data.get('decisions', [])

        if not target_year_id or not decisions:
            return Response({'error': 'target_year_id et decisions[] requis.'}, status=400)
        school = resolve_school_for_year(request, target_year_id)

        results = []
        for decision in decisions:
            results.append(apply_end_of_year_decision(school, target_year_id, decision))

        succeeded = sum(1 for r in results if r['ok'])
        return Response({
            'total': len(results),
            'succeeded': succeeded,
            'failed': len(results) - succeeded,
            'details': results,
        })


class StudentEnrollmentViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = StudentEnrollmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAbove, IsSameTenant]
    filterset_fields = ['student', 'school_year', 'class_obj']
    tenant_lookup = 'student__school'

    def perform_destroy(self, instance):
        """
        FIX v34 — supprimer une inscription annuelle ne touche qu'à CETTE
        année ; si le pointeur "année courante" de l'élève visait cette
        inscription, il est repositionné sur l'inscription restante la
        plus récente (cohérence des listes).
        """
        student = instance.student
        removed_year_id = instance.school_year_id
        super().perform_destroy(instance)
        if student and str(student.school_year_id) == str(removed_year_id):
            latest = student.enrollments.select_related('school_year').order_by(
                '-school_year__start_date').first()
            student.school_year = latest.school_year if latest else None
            student.current_class = latest.class_obj if latest else None
            student.save(update_fields=['school_year', 'current_class'])

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = StudentEnrollment.objects.select_related('student', 'school_year', 'class_obj').all()
        if school is not None:
            qs = qs.filter(student__school=school)
        elif not self.request.user.is_superadmin():
            return qs.none()
        return qs
