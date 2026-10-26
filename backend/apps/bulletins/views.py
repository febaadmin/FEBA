from feba_project.bulk_delete import BulkDeleteMixin
"""
Bulletins views — v29 (multi-tenant)

Corrections v29 :
  - generate_all() ne générait AUCUN filtre par établissement : un clic
    générait un bulletin pour TOUS les élèves de TOUS les tenants de la
    plateforme. Corrigé : scope systématique par établissement courant.
  - generate() / generate_class() : l'élève / l'année scolaire ciblés
    doivent appartenir au tenant courant (sinon 404).
  - Lien vers l'inscription annuelle (enrollment) lors de la génération.

Commentaires du directeur et régénération sans perte (P0) :
  - la régénération RÉUTILISE le bulletin existant (pdf_generator) : elle
    ne le supprime plus. Avant, generate/generate-class/generate-all
    effaçaient le bulletin puis le recréaient : le commentaire du
    directeur disparaissait à chaque régénération, et un échec de
    génération laissait l'élève sans bulletin ni PDF ;
  - POST /bulletins/{id}/comment/ : commentaire d'un bulletin + PDF ;
  - /bulletins/operations/ : commentaire ou génération pour un élève, une
    classe ou toute l'académie, exécutés par le worker Celery, avec
    bilan ; /bulletins/comment-preview/ : portée avant confirmation ;
  - generate-class / generate-all passent par ces opérations : elles
    dépassaient le délai de 60 s du proxy sur une académie entière.
  - Filtre par année active par défaut dans get_queryset
  - Gestion du bulletin annuel (agrège T1+T2+T3 via pdf_generator)
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Bulletin, BulletinOperation
from .serializers import BulletinOperationSerializer, BulletinSerializer

logger = logging.getLogger("apps")


class BulletinViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class   = BulletinSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    filterset_fields   = ["student", "school_year", "period"]
    tenant_lookup = "student__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs   = Bulletin.objects.select_related("student__current_class", "student__school", "school_year")

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        if school is not None:
            qs = qs.filter(student__school=school)
        elif not user.is_superadmin():
            return qs.none()

        # Par défaut, filtrer sur l'année active (sauf si school_year est précisé dans les params)
        from apps.schools.models import SchoolYear
        school_year_param = self.request.query_params.get("school_year")
        # Ce filtre par défaut ne vaut que pour la LISTE : appliqué au détail,
        # il rendait introuvable (404) le bulletin d'une année passée — impossible
        # alors d'en modifier le commentaire, de le régénérer ou de le supprimer.
        if (getattr(self, "action", None) == "list" and not school_year_param
                and self.request.query_params.get("all_years") != "1"):
            from apps.core.tenancy import current_school_years
            active_years = current_school_years(school)
            if active_years.exists():
                qs = qs.filter(school_year__in=active_years)

        if user.role_level >= 80:
            return qs
        # Un bulletin sans PDF est un BROUILLON (commentaire saisi avant la
        # génération) : il n'existe pas encore pour les familles ni pour les
        # enseignants.
        qs = qs.exclude(pdf_file="").exclude(pdf_file__isnull=True)
        qs = qs.filter(student__is_active=True, student__user__is_active=True)
        if user.is_teacher():
            try:
                return qs.filter(student__current_class__in=user.teacher_profile.classes.all())
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

    def get_permissions(self):
        # Toute écriture (y compris create / update / partial_update, qui
        # étaient ouvertes à tout utilisateur authentifié — un parent
        # pouvait modifier le bulletin de son enfant) exige un administrateur.
        from rest_framework.permissions import SAFE_METHODS
        if getattr(self, "action", None) in ("operations", "operation_detail", "comment_preview",
                                             "comment_target", "preview"):
            # Journal et suivi des opérations : administration uniquement.
            return [IsAuthenticated(), IsAdminOrAbove()]
        if self.request is not None and self.request.method not in SAFE_METHODS:
            return [IsAuthenticated(), IsAdminOrAbove(), IsSameTenant()]
        return [IsAuthenticated(), IsSameTenant()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # ──────────────────────────────────────────────────────────────────────────

    # Les écritures génériques (POST /, PUT, PATCH) sont fermées : un
    # bulletin se crée par génération et son commentaire se modifie par
    # /comment/, qui valide le texte et régénère le PDF. Un PATCH direct
    # changeait la base sans changer le PDF.
    def create(self, request, *args, **kwargs):
        return Response({"error": "Utilisez la génération des bulletins."}, status=405)

    def update(self, request, *args, **kwargs):
        return Response(
            {"error": "Utilisez POST /api/bulletins/{id}/comment/ pour le commentaire du directeur."},
            status=405)

    # ── Commentaire d'un bulletin ────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        """
        POST /api/bulletins/{id}/comment/
        {"comment": "…" | "", "regenerate": true, "expected_comment": "…"}

        Enregistre (ou supprime, si vide) le commentaire du directeur puis
        régénère le PDF. `expected_comment` (facultatif) : commentaire que
        l'utilisateur avait sous les yeux ; s'il a changé entre-temps, 409.
        """
        from .operations import ScopeError, apply_to_student, clean_comment, _new_result
        bulletin = self.get_object()   # 404 si hors de l'académie
        try:
            text = clean_comment(request.data.get("comment", ""))
        except ScopeError as exc:
            return Response({"error": str(exc)}, status=exc.status)
        expected = request.data.get("expected_comment")
        if expected is not None and str(expected).replace("\r\n", "\n").strip() != bulletin.general_comment:
            return Response({
                "error": "Le commentaire a été modifié par quelqu'un d'autre entre-temps. "
                         "Rechargez-le avant de l'enregistrer.",
                "current_comment": bulletin.general_comment,
            }, status=409)
        regenerate = str(request.data.get("regenerate", "true")).lower() not in ("false", "0")
        action_name = BulletinOperation.ACTION_SET if text else BulletinOperation.ACTION_CLEAR
        result = _new_result(1)
        updated = apply_to_student(
            bulletin.student, bulletin.school_year, bulletin.period, action=action_name,
            comment=text, regenerate=regenerate, user=request.user, result=result)
        bulletin = Bulletin.objects.get(pk=(updated or bulletin).pk)
        data = BulletinSerializer(bulletin, context={"request": request}).data
        code = 200 if not result["failed"] and not result["skipped"] else 207
        return Response({"bulletin": data, "result": result}, status=code)

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        """
        POST /api/bulletins/preview/
        {"student_id", "school_year_id", "period", "comment"?: "…"}

        APERÇU du bulletin : PDF rendu par le moteur officiel à partir des
        données actuelles (notes, moyennes, classe, identité de l'académie),
        avec le commentaire saisi s'il est fourni, sinon le commentaire
        enregistré. Filigrane « APERÇU ».

        AUCUNE écriture : ni bulletin créé ou modifié, ni PDF officiel
        remplacé, ni fichier temporaire (le PDF est rendu en mémoire et
        renvoyé tel quel), ni notification.
        """
        from django.http import HttpResponse
        from .operations import ScopeError, clean_comment, resolve_scope
        from .pdf_generator import UNCHANGED, render_bulletin_pdf
        try:
            school = self._operation_school(request)
            year, student, _cls, _qs = resolve_scope(
                school, scope=BulletinOperation.SCOPE_STUDENT, period=request.data.get("period"),
                school_year_id=request.data.get("school_year_id"), student_id=request.data.get("student_id"))
            raw = request.data.get("comment")
            comment = UNCHANGED if raw is None else clean_comment(raw)
        except _ScopeHttpError as exc:
            return Response({"error": str(exc)}, status=400)
        except ScopeError as exc:
            return Response({"error": str(exc)}, status=exc.status)
        try:
            pdf, _draft = render_bulletin_pdf(student, request.data.get("period"), year,
                                              comment=comment, preview=True)
        except Exception as exc:
            logger.error("Aperçu impossible %s : %s", student.pk, exc, exc_info=True)
            return Response({"error": f"Aperçu impossible : {exc}"}, status=500)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="apercu_{student.matricule}_{request.data.get("period")}.pdf"'
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @action(detail=False, methods=["post"], url_path="comment-target")
    def comment_target(self, request):
        """
        POST /api/bulletins/comment-target/
        {"student_id", "school_year_id", "period", "comment": "…" | "",
         "regenerate": true, "expected_comment"?: "…"}

        Commentaire d'UN élève pour une année et une période, que son
        bulletin existe déjà ou non. Synchrone (aucun worker requis) :
          - bulletin existant : commentaire enregistré, PDF régénéré ;
          - bulletin pas encore généré : commentaire enregistré dans un
            BROUILLON (sans PDF, invisible des familles) ; le PDF est
            produit maintenant si l'élève a des notes et que `regenerate`
            est demandé, sinon à la prochaine génération, qui le reprendra.
        """
        from .operations import ScopeError, clean_comment, save_student_comment
        try:
            school = self._operation_school(request)
            text = clean_comment(request.data.get("comment", ""))
            expected = request.data.get("expected_comment")
            outcome = save_student_comment(
                school, student_id=request.data.get("student_id"),
                school_year_id=request.data.get("school_year_id"),
                period=request.data.get("period"), comment=text,
                regenerate=str(request.data.get("regenerate", "true")).lower() not in ("false", "0"),
                expected_comment=None if expected is None else str(expected),
                user=request.user)
        except _ScopeHttpError as exc:
            return Response({"error": str(exc)}, status=400)
        except ScopeError as exc:
            data = {"error": str(exc)}
            if getattr(exc, "current_comment", None) is not None:
                data["current_comment"] = exc.current_comment
            return Response(data, status=exc.status)
        bulletin = Bulletin.objects.select_related("student", "school_year").get(pk=outcome["bulletin_id"])
        return Response({
            "bulletin": BulletinSerializer(bulletin, context={"request": request}).data,
            "result": outcome,
        }, status=200 if not outcome["failed"] else 207)

    # ── Opérations groupées ──────────────────────────────────────────────

    def _operation_school(self, request):
        """Académie de l'opération : jamais « toutes les académies »."""
        school = get_request_school(request)
        if school is None:
            raise _ScopeHttpError(
                "Sélectionnez d'abord une académie : une opération sur les bulletins "
                "ne porte jamais sur toutes les académies.")
        return school

    @action(detail=False, methods=["post"], url_path="comment-preview")
    def comment_preview(self, request):
        """
        POST /api/bulletins/comment-preview/ — ce que toucherait l'opération,
        avant confirmation : nombre d'élèves, de bulletins existants, avec
        commentaire, absents (avec ou sans notes).
        """
        from .operations import ScopeError, _has_grades, resolve_scope
        try:
            school = self._operation_school(request)
            year, student, class_obj, students = resolve_scope(
                school, scope=request.data.get("scope"), period=request.data.get("period"),
                school_year_id=request.data.get("school_year_id"),
                student_id=request.data.get("student_id"), class_id=request.data.get("class_id"))
        except (ScopeError, _ScopeHttpError) as exc:
            return Response({"error": str(exc)}, status=getattr(exc, "status", 400))
        period = request.data.get("period")
        students = list(students)
        existing = {b.student_id: b for b in Bulletin.objects.filter(
            student__in=students, school_year=year, period=period)}
        missing = [s for s in students if s.pk not in existing]
        missing_with_grades = sum(1 for s in missing if _has_grades(s, year, period))
        bulletin = existing.get(student.pk) if student else None
        return Response({
            "academy": {"id": school.pk, "name": school.name},
            "school_year": {"id": year.pk, "name": year.name},
            "period": period,
            "scope": request.data.get("scope"),
            "student": {"id": student.pk, "name": student.get_full_name()} if student else None,
            "class": {"id": class_obj.pk, "name": class_obj.name} if class_obj else None,
            "students": len(students),
            "existing_bulletins": len(existing),
            "with_comment": sum(1 for b in existing.values() if b.general_comment),
            "missing_with_grades": missing_with_grades,
            "missing_without_grades": len(missing) - missing_with_grades,
            "bulletin": BulletinSerializer(bulletin, context={"request": request}).data
            if bulletin else None,
            # Un élève : a-t-il des notes sur la période (PDF possible) ?
            "has_grades": _has_grades(student, year, period) if student else None,
            # Classe / académie : liste pour la révision avant génération
            # (aperçu individuel de chaque élève).
            "students_list": [{
                "id": s.pk, "name": s.get_full_name(),
                "has_bulletin": s.pk in existing,
                "has_pdf": bool(existing.get(s.pk) and existing[s.pk].pdf_file),
                "comment": existing[s.pk].general_comment if s.pk in existing else "",
                "has_grades": (s.pk in existing and bool(existing[s.pk].pdf_file)) or _has_grades(s, year, period),
            } for s in students[:1000]] if not student else None,
        })

    @action(detail=False, methods=["get", "post"], url_path="operations")
    def operations(self, request):
        """
        GET  /api/bulletins/operations/ — dernières opérations de l'académie.
        POST /api/bulletins/operations/ — lance une opération (202) :
          {"scope": "student|class|academy", "action": "set_comment|clear_comment|generate",
           "period", "school_year_id", "student_id"?, "class_id"?, "comment"?,
           "regenerate": true, "create_missing": false}
        """
        from .operations import ScopeError, clean_comment, resolve_scope
        try:
            school = self._operation_school(request)
        except _ScopeHttpError as exc:
            return Response({"error": str(exc)}, status=400)
        if request.method == "GET":
            ops = BulletinOperation.objects.filter(school=school).select_related(
                "created_by", "school_year", "student", "class_obj")[:20]
            return Response(BulletinOperationSerializer(ops, many=True).data)

        return self._launch_operation(request, request.data, school)

    def _launch_operation(self, request, data, school):
        from .operations import ScopeError, clean_comment, resolve_scope
        action_name = data.get("action")
        if action_name not in dict(BulletinOperation.ACTIONS):
            return Response({"error": "Action invalide."}, status=400)
        try:
            comment = clean_comment(data.get("comment", "")) if action_name == "set_comment" else ""
            if action_name == "set_comment" and not comment:
                raise ScopeError("Commentaire vide : pour retirer un commentaire, "
                                 "choisissez « Supprimer le commentaire ».")
            year, student, class_obj, _students = resolve_scope(
                school, scope=data.get("scope"), period=data.get("period"),
                school_year_id=data.get("school_year_id"),
                student_id=data.get("student_id"), class_id=data.get("class_id"))
        except ScopeError as exc:
            return Response({"error": str(exc)}, status=exc.status)
        from .operations import expire_stale_operations
        expire_stale_operations(school)
        if BulletinOperation.objects.filter(
                school=school, status__in=BulletinOperation.ACTIVE_STATUSES).exists():
            return Response({"error": "Une opération sur les bulletins de cette académie est déjà "
                                      "en cours. Attendez sa fin avant d'en lancer une autre."},
                            status=409)
        op = BulletinOperation.objects.create(
            school=school, school_year=year, period=data.get("period"),
            scope=data.get("scope"), student=student, class_obj=class_obj,
            action=action_name, comment=comment,
            regenerate=str(data.get("regenerate", "true")).lower() not in ("false", "0"),
            create_missing=str(data.get("create_missing", "false")).lower() in ("true", "1"),
            created_by=request.user,
        )
        if not _enqueue(op):
            op.refresh_from_db()
            return Response({**BulletinOperationSerializer(op).data,
                             "error": op.error}, status=503)
        op.refresh_from_db()
        return Response(BulletinOperationSerializer(op).data, status=202)

    @action(detail=False, methods=["get"], url_path=r"operations/(?P<op_id>[0-9]+)")
    def operation_detail(self, request, op_id=None):
        """GET /api/bulletins/operations/{id}/ — état et bilan d'une opération."""
        school = get_request_school(request)
        qs = BulletinOperation.objects.select_related("created_by", "school_year", "student", "class_obj")
        if school is not None:
            qs = qs.filter(school=school)
        elif not request.user.is_superadmin():
            qs = qs.none()
        op = qs.filter(pk=op_id).first()
        if op is None:
            return Response({"error": "Opération introuvable."}, status=404)
        return Response(BulletinOperationSerializer(op).data)

    # ── Génération ───────────────────────────────────────────────────────

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """POST /api/bulletins/generate/ — un élève, synchrone."""
        student_id     = request.data.get("student_id")
        period         = request.data.get("period")
        school_year_id = request.data.get("school_year_id")

        if not all([student_id, period, school_year_id]):
            return Response(
                {"error": "student_id, period et school_year_id sont requis."},
                status=400,
            )
        if period not in dict(Bulletin.PERIOD_CHOICES):
            return Response({"error": "Période invalide."}, status=400)

        school = get_request_school(request)
        from apps.students.models import Student
        from apps.schools.models import SchoolYear
        from apps.bulletins.pdf_generator import generate_bulletin

        student_qs = Student.objects.all()
        year_qs = SchoolYear.objects.all()
        if school is not None:
            student_qs = student_qs.filter(school=school)
            year_qs = year_qs.filter(school=school)
        elif not request.user.is_superadmin():
            return Response({"error": "Établissement introuvable pour ce compte."}, status=403)
        student = student_qs.filter(pk=student_id).first()
        if student is None:
            return Response({"error": "Élève introuvable."}, status=404)
        # L'année doit appartenir à l'académie DE L'ÉLÈVE.
        school_year = year_qs.filter(pk=school_year_id, school=student.school).first()
        if school_year is None:
            return Response({"error": "Année scolaire introuvable."}, status=404)
        if not student.is_active or (student.user and not student.user.is_active):
            return Response(
                {"error": "Impossible de générer un bulletin pour un élève désactivé."},
                status=400,
            )
        try:
            # Le bulletin existant est réutilisé : commentaire conservé.
            bulletin = generate_bulletin(student, period, school_year)
        except Exception as e:
            logger.error(f"Bulletin generation error: {e}", exc_info=True)
            return Response({"error": f"Génération impossible : {e}. "
                                      f"Le bulletin précédent et son PDF sont conservés."},
                            status=500)
        url = bulletin.pdf_file.url if bulletin.pdf_file else None
        return Response(
            {**BulletinSerializer(bulletin, context={"request": request}).data, "pdf_url": url},
            status=status.HTTP_201_CREATED,
        )

    def _generate_operation(self, request, scope):
        try:
            school = self._operation_school(request)
        except _ScopeHttpError as exc:
            return Response({"error": str(exc)}, status=400)
        data = {k: request.data.get(k) for k in ("period", "school_year_id", "class_id")}
        data.update({"scope": scope, "action": BulletinOperation.ACTION_GENERATE})
        return self._launch_operation(request, data, school)

    @action(detail=False, methods=["post"], url_path="generate-class")
    def generate_class(self, request):
        """POST /api/bulletins/generate-class/ — opération Celery (202)."""
        if not all([request.data.get("class_id"), request.data.get("period"),
                    request.data.get("school_year_id")]):
            return Response({"error": "class_id, period et school_year_id requis."}, status=400)
        return self._generate_operation(request, BulletinOperation.SCOPE_CLASS)

    @action(detail=False, methods=["post"], url_path="generate-all")
    def generate_all(self, request):
        """
        POST /api/bulletins/generate-all/ — tous les élèves actifs de
        l'académie sélectionnée, en opération Celery (202).

        Corrigé : le commentaire disait « superadmin sans school_id :
        refusé », mais le code laissait passer — un super administrateur
        sans académie sélectionnée générait pour TOUTES les académies.
        """
        if not all([request.data.get("period"), request.data.get("school_year_id")]):
            return Response({"error": "period et school_year_id requis."}, status=400)
        return self._generate_operation(request, BulletinOperation.SCOPE_ACADEMY)


class _ScopeHttpError(Exception):
    status = 400


def _enqueue(op):
    """Confie l'opération au worker Celery ; en cas d'échec, l'opération est marquée échouée."""
    from django.utils import timezone
    from .tasks import run_bulletin_operation
    try:
        run_bulletin_operation.delay(op.pk)
        return True
    except Exception as exc:   # broker indisponible
        BulletinOperation.objects.filter(pk=op.pk).update(
            status="failed", finished_at=timezone.now(),
            error=f"File d'attente indisponible (Redis/Celery) : opération non lancée. Détail : {exc}")
        logger.error("Opération bulletins %s non mise en file : %s", op.pk, exc)
        return False
