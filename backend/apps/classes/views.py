from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrReadOnly
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Class
from .serializers import ClassSerializer


class ClassViewSet(viewsets.ModelViewSet):
    serializer_class = ClassSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSameTenant]
    filterset_fields = ["level", "school_year"]
    search_fields = ["name"]
    tenant_lookup = "school_year__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = Class.objects.select_related("level", "school_year__school").prefetch_related("students", "subjects")

        if school is not None:
            qs = qs.filter(school_year__school=school)
        elif not user.is_superadmin():
            return qs.none()

        # FIX v34 (isolation par année) : par défaut, seules les classes de
        # l'ANNÉE ACTIVE sont renvoyées EN LISTE — chaque année est un espace
        # de travail indépendant, et les listes déroulantes ne montrent plus
        # les triplets « CP1-A / CP1-A / CP1-A » issus des autres années.
        # Dérogations explicites : ?school_year=<id> (année précise) ou
        # ?all_years=1 (gestion multi-années).
        #
        # FIX v40 (erreurs 404 console) : ce filtre par défaut ne s'applique
        # QU'À LA LISTE. Les actions de détail (retrieve/update/delete/subjects
        # /students…) doivent atteindre une classe de N'IMPORTE QUELLE année —
        # sinon éditer/supprimer une classe d'une année passée renvoyait 404
        # (et React Query réessayait en boucle → salve de 404 dans la console).
        params = self.request.query_params
        if self.action == "list" and not params.get("school_year") and not params.get("all_years"):
            qs = qs.filter(school_year__is_current=True)

        if user.role_level >= 80:
            return qs
        elif user.is_teacher():
            try:
                return qs.filter(teacher_classes__user=user).distinct()
            except Exception:
                return qs
        return qs   # parents/students can read all class names of their own school for display

    def destroy(self, request, *args, **kwargs):
        """
        FIX v37 (vidéo 3) — garde de suppression : une classe portant des
        inscriptions annuelles, des devoirs ou des créneaux d'emploi du temps
        ne peut pas être détruite (l'historique perdrait sa classe).
        Réponse 409 explicite listant les dépendances.
        """
        cls = self.get_object()
        deps = {
            "inscriptions": cls.enrollments.count(),
            "créneaux d'emploi du temps": cls.schedules.count(),
            "devoirs": cls.homework.count(),
        }
        blocking = {k: v for k, v in deps.items() if v}
        if blocking:
            detail = ", ".join(f"{v} {k}" for k, v in blocking.items())
            return Response({
                "error": f"Suppression impossible : la classe {cls.name} est référencée par {detail}. "
                         "Retirez d'abord ces éléments (ou conservez la classe : l'historique en dépend).",
                "dependencies": deps,
            }, status=409)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="copy-from-year")
    def copy_from_year(self, request):
        """
        FIX v38 — ouvre une nouvelle année en un clic : duplique les classes
        d'une année source vers une année cible (nom, niveau, capacité,
        matières FR/EN). Les classes homonymes déjà présentes dans la cible
        sont ignorées (idempotent). Aucun élève n'est copié : les effectifs
        se remplissent via les passages/inscriptions.
        Body: { "source_year_id": X, "target_year_id": Y }
        """
        from apps.schools.models import SchoolYear

        source_id = request.data.get("source_year_id")
        target_id = request.data.get("target_year_id")
        if not source_id or not target_id:
            return Response({"error": "source_year_id et target_year_id requis."}, status=400)
        if str(source_id) == str(target_id):
            return Response({"error": "Les années source et cible doivent être différentes."}, status=400)

        source = SchoolYear.objects.filter(pk=source_id).select_related("school").first()
        target = SchoolYear.objects.filter(pk=target_id).select_related("school").first()
        if not source or not target:
            return Response({"error": "Année source ou cible introuvable."}, status=404)
        if source.school_id != target.school_id:
            return Response({"error": "Les deux années doivent appartenir au même établissement."}, status=400)
        # Contrôle tenant (superadmin : déduit des années, cohérent avec v31)
        school = get_request_school(self.request)
        if school is not None and source.school_id != school.id:
            return Response({"error": "Année hors de votre établissement."}, status=403)

        existing = set(Class.objects.filter(school_year=target).values_list("name", flat=True))
        created, skipped = [], []
        for cls in Class.objects.filter(school_year=source).select_related("level").prefetch_related("subjects"):
            if cls.name in existing:
                skipped.append(cls.name)
                continue
            new_cls = Class.objects.create(
                name=cls.name, level=cls.level,
                school_year=target, max_students=cls.max_students,
            )
            new_cls.subjects.set(cls.subjects.all())
            created.append(cls.name)

        return Response({
            "created": len(created), "skipped": len(skipped),
            "created_names": created, "skipped_names": skipped,
            "detail": (f"{len(created)} classe(s) copiée(s) de {source.name} vers {target.name}"
                       + (f" ; {len(skipped)} déjà présente(s), ignorée(s)." if skipped else ".")),
        })

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request, *args, **kwargs):
        """FIX v37 — même garde en masse : seules les classes SANS dépendances sont supprimées."""
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response({"error": "ids list required"}, status=400)
        deleted, blocked = 0, []
        for cls in self.get_queryset().filter(id__in=ids):
            if cls.enrollments.exists() or cls.schedules.exists() or cls.homework.exists():
                blocked.append(cls.name)
                continue
            cls.delete()
            deleted += 1
        payload = {"deleted": deleted}
        if blocked:
            payload["blocked"] = blocked
            payload["detail"] = (f"{deleted} classe(s) supprimée(s) ; "
                                 f"{len(blocked)} conservée(s) car référencées par l'historique : "
                                 + ", ".join(blocked))
        else:
            payload["detail"] = f"{deleted} classe(s) supprimée(s)."
        return Response(payload)

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        from apps.students.serializers import StudentSerializer
        cls = self.get_object()
        students = cls.students.filter(is_active=True).select_related("user", "school_year")
        return Response(StudentSerializer(students, many=True).data)

    @action(detail=True, methods=["get"])
    def schedule(self, request, pk=None):
        from apps.schedule.serializers import ClassScheduleSerializer
        cls = self.get_object()
        schedules = cls.schedules.select_related("subject", "teacher__user", "school_year").order_by("day_of_week", "start_time")
        return Response(ClassScheduleSerializer(schedules, many=True).data)

    @action(detail=True, methods=["get"])
    def homework(self, request, pk=None):
        from apps.homework.serializers import HomeworkSerializer
        cls = self.get_object()
        hw = cls.homework.select_related("subject", "teacher__user").order_by("due_date")
        return Response(HomeworkSerializer(hw, many=True).data)

    @action(detail=True, methods=["get", "post", "delete"], url_path="subjects")
    def manage_subjects(self, request, pk=None):
        """
        GET    /classes/{id}/subjects/            → liste matières de la classe
        POST   /classes/{id}/subjects/            → { subject_ids: [1,2,3] } → remplace la liste
        DELETE /classes/{id}/subjects/            → { subject_id: 5 } → retire une matière
        """
        cls = self.get_object()
        from apps.subjects.models import Subject
        from apps.subjects.serializers import SubjectSerializer

        if request.method == "GET":
            subjects = cls.subjects.all().order_by("language", "order", "name")
            return Response({
                "fr": SubjectSerializer(subjects.filter(language="fr"), many=True).data,
                "en": SubjectSerializer(subjects.filter(language="en"), many=True).data,
                "all": SubjectSerializer(subjects, many=True).data,
                "has_bilingual": cls.has_bilingual_subjects(),
            })

        if request.method == "POST":
            subject_ids = request.data.get("subject_ids", [])
            if not isinstance(subject_ids, list):
                return Response({"error": "subject_ids doit être une liste."}, status=status.HTTP_400_BAD_REQUEST)
            subjects = Subject.objects.filter(id__in=subject_ids)
            cls.subjects.set(subjects)
            return Response({
                "message": f"{cls.subjects.count()} matière(s) assignée(s) à {cls.name}.",
                "has_bilingual": cls.has_bilingual_subjects(),
            })

        if request.method == "DELETE":
            subject_id = request.data.get("subject_id")
            if not subject_id:
                return Response({"error": "subject_id requis."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                subj = cls.subjects.get(id=subject_id)
                cls.subjects.remove(subj)
                return Response({"message": f"Matière retirée de {cls.name}."})
            except Subject.DoesNotExist:
                return Response({"error": "Cette matière n'est pas assignée à cette classe."}, status=status.HTTP_404_NOT_FOUND)
