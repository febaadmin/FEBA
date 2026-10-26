"""
apps/documents/academy_template_views.py — Gabarits téléversés et production

QUI PEUT QUOI
-------------
  - Gérer les gabarits (téléverser, configurer, vérifier, activer,
    désactiver, supprimer, télécharger l'original) : l'administration de
    l'académie, ou le super administrateur POUR L'ACADÉMIE SÉLECTIONNÉE.
  - Rien pour les enseignants, parents et élèves.

L'académie n'est JAMAIS lue dans le corps de la requête : elle vient de
`get_request_school`, qui renvoie l'établissement de l'administrateur (il
ne peut pas l'élargir) ou l'académie active du super administrateur. Un
gabarit d'une autre académie est donc introuvable (404), quel que soit
l'identifiant essayé.
"""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.tenancy import get_request_school
from apps.documents import academy_templates as uploads
from apps.documents.models import AcademyDocumentTemplate, GeneratedDocument
from apps.documents.renderer import RenderError
from apps.documents.services import (
    create_for_kind, issue_document, prepare_uploaded,
)
from apps.documents.templates_registry import TemplateError
from apps.documents.views import ISSUER_ROLE_LEVEL, _serialize, _visible_documents, _visible_students

KINDS = dict(AcademyDocumentTemplate.KIND_CHOICES)
#: Lot maximal : une classe. Au-delà, la requête dépasserait le délai du
#: serveur web, et l'erreur arriverait après coup, document par document.
MAX_BATCH = 80


def _messages(exc):
    return list(getattr(exc, "messages", None) or [str(exc)])


def _error(exc, code=status.HTTP_400_BAD_REQUEST):
    messages = _messages(exc)
    return Response({"detail": " ".join(messages), "errors": messages}, status=code)


def _managed_academy(request):
    """
    `(académie, None)` si l'utilisateur peut gérer les gabarits de
    l'académie en cours, sinon `(None, Response)`.
    """
    user = request.user
    if user.role_level < ISSUER_ROLE_LEVEL and not user.is_superadmin():
        return None, Response(
            {"detail": "Seule l'administration de l'académie gère ses gabarits."},
            status=status.HTTP_403_FORBIDDEN)
    academy = get_request_school(request)
    if academy is None:
        return None, Response(
            {"detail": "Sélectionnez une académie : les gabarits appartiennent à une "
                       "académie précise."},
            status=status.HTTP_400_BAD_REQUEST)
    return academy, None


def _template_or_404(request, pk):
    academy, denied = _managed_academy(request)
    if denied is not None:
        return None, denied
    template = AcademyDocumentTemplate.objects.filter(pk=pk, academy=academy).first()
    if template is None:
        return None, Response({"detail": "Gabarit introuvable."},
                              status=status.HTTP_404_NOT_FOUND)
    return template, None


def serialize_template(template, *, events=False):
    data = {
        "id": template.pk,
        "kind": template.kind,
        "kind_display": template.get_kind_display(),
        "version": template.version,
        "status": template.status,
        "status_display": template.get_status_display(),
        "original_filename": template.original_filename,
        "file_format": template.file_format,
        "file_format_display": template.get_file_format_display(),
        "file_size": template.file_size,
        "file_sha256": template.file_sha256,
        "page_count": template.page_count,
        "page_index": template.page_index,
        "page_width_mm": template.page_width_mm,
        "page_height_mm": template.page_height_mm,
        "orientation": ("landscape" if template.page_width_mm >= template.page_height_mm
                        else "portrait"),
        "image_width_px": template.image_width_px,
        "image_height_px": template.image_height_px,
        "fields": template.fields,
        "options": template.options,
        "validation_report": template.validation_report,
        "is_editable": template.is_editable,
        "documents_count": template.documents.count(),
        "uploaded_by": template.uploaded_by.get_full_name() if template.uploaded_by else None,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "validated_at": template.validated_at,
        "activated_at": template.activated_at,
        # Aucun chemin de stockage : seulement les routes authentifiées.
        "background_path": f"/api/documents/academy-templates/{template.pk}/background/",
        "original_path": f"/api/documents/academy-templates/{template.pk}/original/",
    }
    if events:
        data["events"] = [
            {"action": e.action, "detail": e.detail, "performed_at": e.performed_at,
             "performed_by": e.performed_by.get_full_name() if e.performed_by else None}
            for e in template.events.all()[:50]
        ]
    return data


def _kind_summary(academy, kind):
    versions = list(AcademyDocumentTemplate.objects.filter(academy=academy, kind=kind)
                    .select_related("uploaded_by").order_by("-version"))
    active = next((v for v in versions if v.status == AcademyDocumentTemplate.ACTIVE), None)
    pending = next((v for v in versions
                    if v.status in (AcademyDocumentTemplate.DRAFT,
                                    AcademyDocumentTemplate.VALIDATED,
                                    AcademyDocumentTemplate.INVALID)), None)
    builtin = uploads.builtin_template(academy, kind)
    if active is not None:
        state = "replacing" if pending is not None else "active"
    elif pending is not None:
        state = {"draft": "uploaded", "validated": "ready", "invalid": "invalid"}[pending.status]
    elif any(v.status == AcademyDocumentTemplate.DISABLED for v in versions):
        state = "disabled"
    else:
        state = "absent"
    builtin_blockers = []
    if builtin is not None:
        builtin_blockers = builtin.issuance_blockers()
    return {
        "kind": kind,
        "kind_display": KINDS[kind],
        "state": state,
        "active": serialize_template(active) if active else None,
        "pending": serialize_template(pending) if pending else None,
        "versions": [serialize_template(v) for v in versions],
        # Gabarit livré avec l'application : sert tant qu'aucune version
        # téléversée n'est active, et l'écran le dit.
        "builtin": {
            "id": builtin.id, "label": builtin.label, "version": builtin.version,
            "can_issue": not builtin_blockers, "blockers": builtin_blockers,
            "in_use": active is None,
        } if builtin is not None else None,
    }


def _catalog(kind=None):
    return [
        {"name": name, "label": spec["label"], "label_en": spec["label_en"],
         "kinds": sorted(spec["kinds"]), "source": spec["source"]}
        for name, spec in uploads.FIELD_CATALOG.items()
        if kind is None or kind in spec["kinds"]
    ]


class AcademyTemplateListView(APIView):
    """
    GET  /api/documents/academy-templates/  — état des deux types
    POST /api/documents/academy-templates/  — téléverse une nouvelle version
         (multipart : kind, file, page_format, copy_from)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        academy, denied = _managed_academy(request)
        if denied is not None:
            return denied
        return Response({
            "academy": {"id": academy.pk, "code": academy.code, "name": academy.name,
                        "academy_type": academy.academy_type},
            "kinds": {kind: _kind_summary(academy, kind) for kind in KINDS},
            "catalog": _catalog(),
            "fonts": list(uploads.FONTS),
            "page_formats": {key: list(size) for key, size in uploads.PAGE_FORMATS.items()},
            "eligibility_rules": {k: list(v) for k, v in uploads.ELIGIBILITY_RULES.items()},
            "limits": {
                "max_bytes": uploads.MAX_TEMPLATE_BYTES,
                "formats": ["pdf", "png", "jpeg"],
                "extensions": sorted(uploads.ACCEPTED_EXTENSIONS),
                "max_pdf_pages": uploads.MAX_PDF_PAGES,
                "min_image_side_px": uploads.MIN_IMAGE_SIDE_PX,
            },
        })

    def post(self, request):
        academy, denied = _managed_academy(request)
        if denied is not None:
            return denied
        kind = request.data.get("kind")
        if kind not in KINDS:
            return Response({"detail": "Type de document attendu : diploma ou certificate."},
                            status=status.HTTP_400_BAD_REQUEST)
        copy_from = None
        if request.data.get("copy_from"):
            copy_from = AcademyDocumentTemplate.objects.filter(
                pk=request.data.get("copy_from"), academy=academy, kind=kind,
            ).first()
            if copy_from is None:
                return Response({"detail": "Version de référence introuvable."},
                                status=status.HTTP_404_NOT_FOUND)
        try:
            template = uploads.create_version(
                academy=academy, kind=kind, uploaded_file=request.FILES.get("file"),
                user=request.user, page_format=request.data.get("page_format") or "auto",
                copy_from=copy_from,
            )
        except ValidationError as exc:
            return _error(exc)
        return Response(serialize_template(template, events=True),
                        status=status.HTTP_201_CREATED)


class AcademyTemplateDetailView(APIView):
    """
    GET    …/<id>/                 — détail et journal
    PATCH  …/<id>/  {fields, options} — configuration (version modifiable)
    DELETE …/<id>/?confirm=1       — suppression d'une version jamais utilisée
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        return Response(serialize_template(template, events=True))

    def patch(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        try:
            uploads.save_configuration(
                template, fields=request.data.get("fields"),
                options=request.data.get("options"), user=request.user,
            )
        except ValidationError as exc:
            return _error(exc)
        return Response(serialize_template(template, events=True))

    def delete(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        confirm = str(request.query_params.get("confirm", "")).lower() in ("1", "true", "yes")
        try:
            uploads.delete_version(template, request.user, confirm=confirm)
        except ValidationError as exc:
            return _error(exc, status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AcademyTemplateActionView(APIView):
    """POST …/<id>/<validate|activate|disable|reactivate|duplicate>/"""
    permission_classes = [IsAuthenticated]
    action = None

    def post(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        try:
            if self.action == "validate":
                report = uploads.validate(template, request.user)
                payload = serialize_template(template, events=True)
                payload["report"] = report
                return Response(payload)
            if self.action == "activate":
                uploads.activate(template, request.user)
            elif self.action == "disable":
                uploads.disable(template, request.user)
            elif self.action == "reactivate":
                uploads.reactivate(template, request.user)
            elif self.action == "duplicate":
                with open(template.absolute_path, "rb") as handle:
                    content = handle.read()
                copy = uploads.create_version(
                    academy=template.academy, kind=template.kind,
                    uploaded_file=SimpleUploadedFile(template.original_filename, content,
                                                     "application/octet-stream"),
                    user=request.user,
                    page_format=(template.options or {}).get("page_format") or "auto",
                    copy_from=template,
                )
                if template.page_index and template.page_index < copy.page_count:
                    uploads.save_configuration(
                        copy, options={"page_index": template.page_index},
                        user=request.user)
                return Response(serialize_template(copy, events=True),
                                status=status.HTTP_201_CREATED)
        except FileNotFoundError:
            return Response({"detail": "Le fichier de ce gabarit est absent du stockage."},
                            status=status.HTTP_410_GONE)
        except ValidationError as exc:
            return _error(exc, status.HTTP_409_CONFLICT)
        return Response(serialize_template(template, events=True))


def _private_response(content, content_type, filename, inline=True):
    response = HttpResponse(content, content_type=content_type)
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class AcademyTemplateBackgroundView(APIView):
    """GET …/<id>/background/ — image du fond pour l'éditeur."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        try:
            content = uploads.background_png(template)
        except (OSError, ValueError) as exc:
            return Response({"detail": f"Fond illisible : {exc.__class__.__name__}."},
                            status=status.HTTP_410_GONE)
        return _private_response(content, "image/png", f"fond-{template.pk}.png")


class AcademyTemplateOriginalView(APIView):
    """GET …/<id>/original/ — fichier téléversé, tel quel (administration)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        try:
            handle = open(template.absolute_path, "rb")
        except OSError:
            return Response({"detail": "Le fichier de ce gabarit est absent du stockage."},
                            status=status.HTTP_410_GONE)
        content_type = {"pdf": "application/pdf", "png": "image/png",
                        "jpeg": "image/jpeg"}[template.file_format]
        ext = {"pdf": "pdf", "png": "png", "jpeg": "jpg"}[template.file_format]
        response = FileResponse(handle, content_type=content_type, as_attachment=True,
                                filename=f"gabarit-{template.kind}-v{template.version}.{ext}")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class AcademyTemplatePreviewView(APIView):
    """
    POST …/<id>/preview/  {student?, values?, frames?, format?}

    Aperçu filigrané. Sans élève : valeurs d'exemple. Avec un élève : ses
    vraies données — l'élève doit appartenir à l'académie du gabarit.
    Rien n'est enregistré.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        template, denied = _template_or_404(request, pk)
        if denied is not None:
            return denied
        frames = bool(request.data.get("frames"))
        info = {"missing": [], "warnings": [], "blockers": []}
        try:
            student_id = request.data.get("student")
            if student_id:
                student = _visible_students(request.user, request).filter(
                    pk=student_id, school=template.academy).first()
                if student is None:
                    return Response({"detail": "Élève introuvable dans cette académie."},
                                    status=status.HTTP_404_NOT_FOUND)
                prepared = prepare_uploaded(template, student,
                                            extra_values=request.data.get("values") or {})
                values = prepared["values"]
                info = {k: prepared[k] for k in ("missing", "warnings", "blockers")}
            else:
                values = uploads._sample_values(template)
            content = uploads.render(template, values, preview=True, frames=frames)
        except (RenderError, ValidationError) as exc:
            return _error(exc)
        if request.data.get("format") == "png":
            content, ctype, name = uploads.pdf_to_png(content), "image/png", "apercu.png"
        else:
            ctype, name = "application/pdf", "apercu.pdf"
        response = _private_response(content, ctype, name)
        response["X-Preview-Missing"] = str(len(info["missing"]))
        response["X-Preview-Blockers"] = str(len(info["blockers"]))
        return response


# ── Production depuis l'écran « Documents officiels » ─────────────────

def _student_for(request):
    return _visible_students(request.user, request).filter(
        pk=request.data.get("student")).select_related("school").first()


def _school_year(student, raw):
    if not raw:
        return None
    year = student.school.years.filter(pk=raw).first()
    if year is None:
        raise ValidationError("Année scolaire introuvable pour l'académie de cet élève.")
    return year


def _check_payload(kind, student, school_year, extra):
    """Ce que l'écran doit savoir AVANT de produire : source, manques, refus."""
    source, template = uploads.resolve_template(student.school, kind)
    base = {"kind": kind, "source": source,
            "academy": {"code": student.school.code, "name": student.school.name},
            "student": {"id": student.pk, "name": student.get_full_name()}}
    if source is None:
        base.update({"can_produce": False, "missing": [], "warnings": [], "values": {},
                     "blockers": [f"Aucun gabarit de {KINDS[kind].lower()} actif pour "
                                  f"« {student.school.name} »."]})
        return base, None
    if source == "builtin":
        blockers = template.issuance_blockers()
        base.update({"template": {"label": template.label, "version": template.version},
                     "can_produce": not blockers, "blockers": blockers, "missing": [],
                     "warnings": [], "values": {"student_name": student.get_full_name()}})
        return base, template
    prepared = prepare_uploaded(template, student, school_year=school_year,
                                extra_values=extra)
    placed = {f["name"] for f in template.fields}
    base.update({
        "template": {"id": template.pk, "version": template.version,
                     "label": template.options.get("document_title") or KINDS[kind],
                     "eligibility": template.options.get("eligibility")},
        "values": {k: v for k, v in prepared["values"].items() if k in placed},
        "labels": {k: uploads.FIELD_CATALOG[k]["label"] for k in placed},
        "inputs": sorted(placed & uploads.INPUT_FIELDS),
        "missing": prepared["missing"], "warnings": prepared["warnings"],
        "blockers": prepared["blockers"],
        "school_year": prepared["year"].name if prepared["year"] else None,
        "can_produce": not prepared["missing"] and not prepared["blockers"],
    })
    return base, template


def _issuer_or_403(request):
    if request.user.role_level < ISSUER_ROLE_LEVEL:
        return Response({"detail": "Seule l'administration peut produire un document officiel."},
                        status=status.HTTP_403_FORBIDDEN)
    return None


class DocumentCheckView(APIView):
    """POST /api/documents/check/ {student, kind, school_year?, values?}"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _issuer_or_403(request)
        if denied is not None:
            return denied
        kind = request.data.get("kind")
        if kind not in KINDS:
            return Response({"detail": "Type de document attendu : diploma ou certificate."},
                            status=status.HTTP_400_BAD_REQUEST)
        student = _student_for(request)
        if student is None:
            return Response({"detail": "Élève introuvable ou hors de votre périmètre."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            payload, _template = _check_payload(
                kind, student, _school_year(student, request.data.get("school_year")),
                request.data.get("values") or {})
        except ValidationError as exc:
            return _error(exc)
        return Response(payload)


class DocumentPreviewView(APIView):
    """
    POST /api/documents/preview/ {student, kind, …} — PDF filigrané « APERÇU ».
    Aucun document n'est créé, aucun numéro consommé.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.documents.renderer import render_document
        from apps.documents.services import build_values as builtin_values
        from apps.schools.branding import get_branding

        denied = _issuer_or_403(request)
        if denied is not None:
            return denied
        kind = request.data.get("kind")
        student = _student_for(request)
        if kind not in KINDS or student is None:
            return Response({"detail": "Élève ou type de document introuvable."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            payload, template = _check_payload(
                kind, student, _school_year(student, request.data.get("school_year")),
                request.data.get("values") or {})
            if template is None:
                return Response({"detail": " ".join(payload["blockers"])},
                                status=status.HTTP_409_CONFLICT)
            if payload["source"] == "builtin":
                values = builtin_values(template, student)
                values.setdefault("document_number", "")
                content = render_document(template.id, values,
                                          branding=get_branding(student.school), preview=True)
            else:
                full, _m, _w, _y, _f = uploads.build_values(
                    template, student,
                    school_year=_school_year(student, request.data.get("school_year")),
                    extra=request.data.get("values") or {})
                content = uploads.render(template, full, preview=True)
        except (RenderError, TemplateError, ValidationError) as exc:
            return _error(exc)
        response = _private_response(content, "application/pdf", "apercu.pdf")
        response["X-Preview-Can-Produce"] = "1" if payload["can_produce"] else "0"
        return response


class DocumentBatchView(APIView):
    """
    POST /api/documents/batch/ {kind, class_id, school_year?, values?}

    Un brouillon par élève de la classe, CHACUN sur le gabarit de SA propre
    académie (résolu élève par élève). Un élève refusé n'interrompt pas le
    lot : il figure dans le compte rendu, avec son motif.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.classes.models import Class

        denied = _issuer_or_403(request)
        if denied is not None:
            return denied
        kind = request.data.get("kind")
        if kind not in KINDS:
            return Response({"detail": "Type de document attendu : diploma ou certificate."},
                            status=status.HTTP_400_BAD_REQUEST)
        students = _visible_students(request.user, request)
        klass = Class.objects.filter(
            pk=request.data.get("class_id"),
            level__school__in=students.values("school").distinct(),
        ).select_related("school_year").first()
        if klass is None:
            return Response({"detail": "Classe introuvable dans votre périmètre."},
                            status=status.HTTP_404_NOT_FOUND)
        roster = students.filter(enrollments__class_obj=klass,
                                 enrollments__school_year=klass.school_year).distinct()
        if not roster.exists():
            roster = students.filter(current_class=klass)
        roster = list(roster.select_related("school").order_by("last_name", "first_name")[:MAX_BATCH + 1])
        if len(roster) > MAX_BATCH:
            return Response({"detail": f"Au plus {MAX_BATCH} élèves par lot."},
                            status=status.HTTP_400_BAD_REQUEST)
        results = []
        for student in roster:
            try:
                document = create_for_kind(
                    kind=kind, student=student, user=request.user,
                    school_year=klass.school_year, extra_values=request.data.get("values") or {},
                )
                results.append({"student": student.get_full_name(), "student_id": student.pk,
                                "ok": True, "document": _serialize(document, request)})
            except (RenderError, TemplateError, ValidationError) as exc:
                results.append({"student": student.get_full_name(), "student_id": student.pk,
                                "ok": False, "reason": " ".join(_messages(exc))})
        return Response({
            "class": klass.name, "kind": kind,
            "created": sum(1 for r in results if r["ok"]),
            "refused": sum(1 for r in results if not r["ok"]),
            "results": results,
        }, status=status.HTTP_201_CREATED if any(r["ok"] for r in results) else status.HTTP_200_OK)


class DocumentBatchIssueView(APIView):
    """POST /api/documents/batch-issue/ {ids} — délivre une sélection de brouillons."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _issuer_or_403(request)
        if denied is not None:
            return denied
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids or len(ids) > MAX_BATCH:
            return Response({"detail": f"Liste de 1 à {MAX_BATCH} documents attendue."},
                            status=status.HTTP_400_BAD_REQUEST)
        documents = {d.pk: d for d in _visible_documents(request.user, request).filter(pk__in=ids)}
        results = []
        for pk in ids:
            document = documents.get(pk)
            if document is None:
                results.append({"id": pk, "ok": False, "reason": "Document introuvable."})
                continue
            if document.status not in (GeneratedDocument.DRAFT, GeneratedDocument.VALIDATED):
                results.append({"id": pk, "ok": False,
                                "reason": f"Déjà {document.get_status_display().lower()}."})
                continue
            try:
                issue_document(document, user=request.user)
                results.append({"id": pk, "ok": True, "number": document.number})
            except (RenderError, TemplateError, ValidationError) as exc:
                results.append({"id": pk, "ok": False, "reason": " ".join(_messages(exc))})
        return Response({"issued": sum(1 for r in results if r["ok"]), "results": results})

