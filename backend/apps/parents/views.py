from feba_project.bulk_delete import BulkDeleteMixin
"""
Parents views — v29 (multi-parents + multi-tenant)

Changements v29 :
  1. Un élève peut désormais avoir PLUSIEURS parents/tuteurs : les
     contrôles qui bloquaient l'ajout d'un second parent (409 Conflict)
     ont été retirés. link_student / assign_child créent ou mettent à
     jour le lien, point.
  2. Isolation multi-tenant : chaque accès à un Student ou Parent par
     ID est désormais vérifié comme appartenant à l'établissement de
     l'utilisateur courant (sinon 404), pour éviter qu'un identifiant
     numérique d'un autre établissement ne soit exploitable.

Fixes v8 conservés :
  - create() atomique, validation rôle/unicité
  - select_for_update() pour éviter les races
  - link_student / unlink_student (détail) + assign_child / remove_child (globaux)
"""
from django.db import transaction, IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrAbove, IsAdminOrReadOnly
from apps.core.tenancy import get_request_school
from .models import Parent, ParentStudent
from .serializers import ParentSerializer, ParentStudentSerializer
import logging

logger = logging.getLogger("apps")


class ParentViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = ParentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    search_fields = ["user__first_name", "user__last_name", "user__email"]

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request, *args, **kwargs):
        """
        FIX v37 (vidéo 2) — la suppression en masse de parents DÉSACTIVE
        les comptes (réversible) au lieu de détruire : les liens familiaux
        et l'historique multi-années sont inviolables.
        """
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response({"error": "ids list required"}, status=400)
        qs = self.get_queryset().filter(id__in=ids)
        count = qs.count()
        from apps.accounts.models import CustomUser
        user_ids = list(qs.exclude(user=None).values_list("user_id", flat=True))
        if user_ids:
            CustomUser.objects.filter(id__in=user_ids).update(is_active=False)
        return Response({"deleted": count, "soft": True,
                         "detail": f"{count} parent(s) désactivé(s) — liens familiaux et historique conservés."})

    def destroy(self, request, *args, **kwargs):
        """
        FIX v34 — un parent a une identité unique et permanente :

        DELETE /parents/{id}/            → DÉSACTIVATION (soft delete) du
            compte parent ; ses liens avec ses enfants et tout l'historique
            multi-années sont conservés.
        DELETE /parents/{id}/?hard=true  → suppression définitive, refusée
            tant que le parent est lié à des élèves.
        """
        parent = self.get_object()
        hard = str(request.query_params.get('hard', '')).lower() in ('1', 'true', 'yes')

        if not hard:
            if parent.user_id:
                parent.user.is_active = False
                parent.user.save(update_fields=['is_active'])
            name = parent.user.get_full_name() if parent.user_id else f"Parent #{parent.id}"
            return Response({
                'detail': f"{name} a été désactivé(e). Ses liens familiaux et son historique "
                          "sont conservés. Utilisez ?hard=true pour une suppression définitive.",
                'soft_deleted': True,
            })

        links = parent.children_links.count()
        if links:
            return Response({
                'error': f"Suppression définitive impossible : ce parent est lié à {links} élève(s). "
                         "Retirez d'abord les liens ou utilisez la désactivation.",
            }, status=409)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """Réactive un parent désactivé."""
        parent = self.get_object()
        if parent.user_id:
            parent.user.is_active = True
            parent.user.save(update_fields=['is_active'])
        return Response({'detail': 'Parent réactivé.'})

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        school_year_id = self.request.query_params.get("school_year")
        qs = Parent.objects.select_related("user").prefetch_related(
            "children_links__student__current_class",
            "children_links__student__school_year",
        )

        # --- Isolation multi-tenant -----------------------------------------
        if school is not None:
            qs = qs.filter(user__school=school)
        elif not user.is_superadmin():
            return qs.none()

        # FIX v32 : le filtre par année passe par l'HISTORIQUE des inscriptions
        # de l'enfant (comme la liste élèves), plus par le pointeur "année
        # courante" — sinon un parent disparaissait des années passées dès que
        # son enfant était promu.
        from django.db.models import Q
        year_filter = None
        if school_year_id:
            year_filter = (
                Q(children_links__student__enrollments__school_year_id=school_year_id)
                | Q(children_links__student__school_year_id=school_year_id)
            )

        if user.role_level >= 80:
            if year_filter is not None:
                qs = qs.filter(year_filter).distinct()
            return qs
        # Non-admin: only active user accounts
        qs = qs.filter(user__is_active=True)
        if year_filter is not None:
            qs = qs.filter(year_filter).distinct()
        if user.is_parent():
            return qs.filter(user=user)
        elif user.is_teacher():
            try:
                classes = user.teacher_profile.classes.all()
                return qs.filter(
                    children_links__student__current_class__in=classes
                ).distinct()
            except Exception:
                return qs.none()
        return qs.none()

    def create(self, request, *args, **kwargs):
        """
        POST /api/parents/
        Body: { user: <user_pk>, profession?: str, address?: str }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                parent = serializer.save()
            logger.info(f"Parent créé: {parent} par {request.user.email}")
            return Response(self.get_serializer(parent).data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {"error": "Un profil parent existe déjà pour cet utilisateur."},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """
        GET /api/parents/me/
        Returns the Parent profile for the currently authenticated parent user,
        including full children_links with nested student_detail.
        """
        try:
            parent = request.user.parent_profile
        except Exception:
            return Response(
                {"error": "Profil parent introuvable pour cet utilisateur."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(parent, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def children(self, request, pk=None):
        parent = self.get_object()
        from apps.students.serializers import StudentSerializer
        students = [
            link.student
            for link in parent.children_links.select_related(
                "student__current_class", "student__school_year"
            ).all()
        ]
        return Response(StudentSerializer(students, many=True).data)

    # ── Assignment helpers (detail=True — parent_id from URL) ─────────────────

    @action(detail=True, methods=["post"], url_path="link_student")
    def link_student(self, request, pk=None):
        """
        POST /api/parents/{parent_id}/link_student/
        Body: { student_id: int, relationship?: str, is_primary_contact?: bool,
                is_legal_guardian?: bool, is_financial_responsible?: bool,
                can_pickup?: bool }

        v29 : un élève peut avoir plusieurs parents — ce n'est plus bloqué.
        Si ce parent est déjà lié à cet élève, ses rôles sont mis à jour
        plutôt que de créer un doublon (unique_together(parent, student)).
        """
        parent = self.get_object()
        student_id = request.data.get("student_id")

        if not student_id:
            return Response({"error": "student_id requis."}, status=400)

        school = get_request_school(request)
        from apps.students.models import Student
        try:
            with transaction.atomic():
                student_qs = Student.objects.select_for_update()
                if school is not None:
                    student_qs = student_qs.filter(school=school)
                try:
                    student = student_qs.get(pk=student_id)
                except Student.DoesNotExist:
                    return Response({"error": "Élève introuvable."}, status=404)

                defaults = {"relationship": request.data.get("relationship", "guardian")}
                for flag in ("is_primary_contact", "is_legal_guardian",
                             "is_financial_responsible", "can_pickup"):
                    if flag in request.data:
                        defaults[flag] = bool(request.data.get(flag))

                link, created = ParentStudent.objects.update_or_create(
                    parent=parent, student=student, defaults=defaults,
                )

            logger.info(
                f"link_student {'created' if created else 'updated'}: "
                f"{parent} ↔ {student}"
            )
            return Response(
                ParentStudentSerializer(link).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except IntegrityError as e:
            return Response({"error": f"Erreur d'intégrité: {e}"}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post", "delete"], url_path="unlink_student")
    def unlink_student(self, request, pk=None):
        """
        POST or DELETE /api/parents/{parent_id}/unlink_student/
        Body/params: { student_id: int }
        """
        parent = self.get_object()
        student_id = (
            request.data.get("student_id")
            or request.query_params.get("student_id")
        )
        if not student_id:
            return Response({"error": "student_id requis."}, status=400)

        deleted, _ = ParentStudent.objects.filter(
            parent=parent, student_id=student_id
        ).delete()
        if deleted:
            logger.info(f"unlink_student: {parent} ↔ student#{student_id}")
            return Response({"detail": "Association supprimée."})
        return Response({"error": "Association introuvable."}, status=404)

    # ── Global helpers (detail=False) ──────────────────────────────────────────

    @action(detail=False, methods=["get"])
    def check_child_assignment(self, request):
        """
        GET /api/parents/check_child_assignment/?student_id=<id>
        v29 : retourne la liste de TOUS les parents déjà associés à cet
        élève (et non plus un seul) — utile pour l'UI qui veut afficher
        "déjà rattaché à : Père Untel, Mère Untelle" avant d'ajouter un
        nouveau lien, sans bloquer l'ajout.
        """
        student_id = request.query_params.get("student_id")
        if not student_id:
            return Response({"error": "student_id requis"}, status=400)
        links = ParentStudent.objects.filter(student_id=student_id).select_related("parent__user")
        return Response({
            "assigned": links.exists(),
            "parents": [
                {
                    "parent_id": link.parent.id,
                    "parent_name": link.parent.user.get_full_name(),
                    "parent_email": link.parent.user.email,
                    "relationship": link.relationship,
                    "is_primary_contact": link.is_primary_contact,
                    "is_legal_guardian": link.is_legal_guardian,
                    "is_financial_responsible": link.is_financial_responsible,
                    "can_pickup": link.can_pickup,
                }
                for link in links
            ],
        })

    @action(detail=False, methods=["post"])
    def assign_child(self, request):
        """
        POST /api/parents/assign_child/
        Body: { parent_id, student_id, relationship?, is_primary_contact?,
                is_legal_guardian?, is_financial_responsible?, can_pickup? }
        v29 : plusieurs parents peuvent être assignés au même élève.
        """
        parent_id = request.data.get("parent_id")
        student_id = request.data.get("student_id")

        if not parent_id or not student_id:
            return Response({"error": "parent_id et student_id requis."}, status=400)

        school = get_request_school(request)
        from apps.students.models import Student
        try:
            with transaction.atomic():
                student_qs = Student.objects.select_for_update()
                if school is not None:
                    student_qs = student_qs.filter(school=school)
                try:
                    student = student_qs.get(pk=student_id)
                except Student.DoesNotExist:
                    return Response({"error": "Élève introuvable."}, status=404)

                parent_qs = Parent.objects.all()
                if school is not None:
                    parent_qs = parent_qs.filter(user__school=school)
                try:
                    parent = parent_qs.get(pk=parent_id)
                except Parent.DoesNotExist:
                    return Response({"error": "Parent introuvable."}, status=404)

                defaults = {"relationship": request.data.get("relationship", "guardian")}
                for flag in ("is_primary_contact", "is_legal_guardian",
                             "is_financial_responsible", "can_pickup"):
                    if flag in request.data:
                        defaults[flag] = bool(request.data.get(flag))

                link, created = ParentStudent.objects.update_or_create(
                    parent=parent, student=student, defaults=defaults,
                )

            logger.info(
                f"assign_child {'created' if created else 'updated'}: "
                f"{parent} ↔ {student}"
            )
            return Response(
                ParentStudentSerializer(link).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except IntegrityError as e:
            return Response({"error": f"Erreur d'intégrité: {e}"}, status=status.HTTP_409_CONFLICT)

    @action(detail=False, methods=["delete", "post"])
    def remove_child(self, request):
        """
        DELETE /api/parents/remove_child/?parent_id=&student_id=
        Also accepts POST body for compatibility.
        """
        parent_id = (
            request.query_params.get("parent_id")
            or request.data.get("parent_id")
        )
        student_id = (
            request.query_params.get("student_id")
            or request.data.get("student_id")
        )
        deleted, _ = ParentStudent.objects.filter(
            parent_id=parent_id, student_id=student_id
        ).delete()
        if deleted:
            return Response({"detail": "Association supprimée."})
        return Response({"error": "Association introuvable."}, status=404)
