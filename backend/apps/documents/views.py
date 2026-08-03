"""
apps/documents/views.py — Accès aux documents officiels

DEUX RÈGLES D'ACCÈS
-------------------
1. **L'appartenance se vérifie sur l'élève, jamais sur l'identifiant reçu.**
   Une requête arrive avec un numéro dans l'URL ; ce numéro ne prouve rien.
   Le filtre part de l'utilisateur et descend vers les documents qu'il peut
   légitimement voir. Incrémenter l'identifiant tombe alors sur un 404.

2. **Le fichier n'a pas d'URL publique.** Il est diffusé par une vue
   authentifiée, depuis un répertoire que le serveur web ne sert pas. Un
   diplôme dans `/media/` est accessible à qui devine son nom — et un nom
   de fichier n'est pas un secret.
"""
import os

from django.core.exceptions import ValidationError
from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.tenancy import get_request_school
from apps.documents.models import DocumentEvent, GeneratedDocument
from apps.documents.services import create_document, issue_document, replace_document
from apps.documents.templates_registry import (
    TemplateError, available_templates, load_template,
)

#: Niveau à partir duquel on peut produire et délivrer un document.
#: Un enseignant ne délivre pas de diplôme : c'est un acte de
#: l'établissement, pas d'une classe.
ISSUER_ROLE_LEVEL = 80


def _visible_documents(user, request=None):
    """
    Documents que cet utilisateur peut légitimement consulter.

    P8 — L'ACADÉMIE SÉLECTIONNÉE EST APPLIQUÉE ICI.

    Le filtrage ne regardait que `user.school`. Pour un super
    administrateur, cela renvoyait TOUS les documents des deux académies,
    quelle que soit l'académie choisie dans l'en-tête : sélectionner FEBA
    affichait quand même les diplômes de FEBA French Heritage Academy, et
    la page contredisait le sélecteur juste au-dessus d'elle.
    """
    queryset = GeneratedDocument.objects.select_related(
        "academy", "student", "school_year",
    )
    if user.is_parent():
        return queryset.filter(student__parents__parent__user=user)
    if user.is_student():
        return queryset.filter(student__user=user)
    if user.role_level < ISSUER_ROLE_LEVEL and not user.is_superadmin():
        return queryset.none()

    school = get_request_school(request) if request is not None else None
    if school is not None:
        return queryset.filter(academy=school)
    if user.is_superadmin():
        # Mode « Toutes les Académies » : vue consolidée ASSUMÉE. Chaque
        # ligne porte son académie (`academy_code`), et l'interface impose
        # de la confirmer avant de produire quoi que ce soit.
        return queryset
    return queryset.filter(academy=user.school)


def _visible_students(user, request=None):
    """
    Élèves pour lesquels cet utilisateur peut produire un document.

    P8 — Même correction : sans l'académie sélectionnée, la liste d'élèves
    de la fenêtre « Produire un document » mélangeait les deux académies.
    Produire un diplôme pour l'élève d'une autre académie n'aurait alors
    demandé qu'une erreur de frappe.
    """
    from apps.students.models import Student

    school = get_request_school(request) if request is not None else None
    if user.is_superadmin():
        # Académie active du super administrateur, ou toutes en mode
        # consolidé. `get_request_school` ne lit jamais l'académie depuis
        # la requête du navigateur : elle est persistée en base par
        # l'endpoint de bascule, qui vérifie l'appartenance et journalise.
        return Student.objects.filter(school=school) if school else Student.objects.all()
    if user.role_level >= ISSUER_ROLE_LEVEL:
        return Student.objects.filter(school=user.school)
    return Student.objects.none()


def _serialize(document, request=None):
    return {
        "id": document.pk,
        "number": document.number,
        "academy_code": document.academy.code,
        "academy_name": document.academy.name,
        "student": document.student.get_full_name(),
        "student_id": document.student_id,
        "template_id": document.template_id,
        "template_version": document.template_version,
        "status": document.status,
        "status_display": document.get_status_display(),
        # Ni chemin, ni URL de fichier : le téléchargement passe par une
        # vue authentifiée, et un chemin exposé finit toujours par être
        # essayé directement.
        "download_path": f"/api/documents/{document.pk}/download/",
        "file_sha256": document.file_sha256,
        "file_size": document.file_size,
        "replaces": document.replaces_id,
        "revocation_reason": document.revocation_reason,
        "created_at": document.created_at,
        "issued_at": document.issued_at,
    }


class DocumentTemplateListView(APIView):
    """
    GET /api/documents/templates/

    État réel de chaque gabarit : fond installé ou non, calibré ou non, et
    ce qui empêche l'émission le cas échéant. L'interface s'en sert pour
    dire pourquoi un bouton est indisponible, plutôt que de le masquer.

    P8 — La réponse dépend de l'ACADÉMIE SÉLECTIONNÉE. Un gabarit dont le
    fond porte l'identité d'une académie n'est pas proposé aux autres : le
    document sortirait au nom de l'une et à l'effigie de l'autre.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        academy = get_request_school(request)
        items = []
        for template_id in available_templates():
            try:
                template = load_template(template_id)
            except TemplateError as exc:
                items.append({
                    "id": template_id, "usable": False,
                    "blockers": [exc.messages[0] if exc.messages else str(exc)],
                })
                continue

            blockers = template.issuance_blockers()
            # Le refus lié à l'académie s'ajoute aux blocages techniques :
            # ce sont deux raisons différentes, et l'écran doit pouvoir
            # dire laquelle s'applique.
            academy_blocker = (
                template.academy_blocker(academy) if academy is not None else None
            )
            if academy_blocker:
                blockers = blockers + [academy_blocker]

            items.append({
                "id": template.id,
                "label": template.label,
                "version": template.version,
                "background_file": template.background_file,
                "background_installed": template.background_installed,
                "calibrated": template.calibrated,
                "provisional_layout": template.provisional_layout,
                "tolerance_mm": template.tolerance_mm,
                "academies": template.academies,
                "allowed_for_academy": academy_blocker is None,
                "can_issue": not blockers,
                "blockers": blockers,
                "fields": [
                    {"name": f.name, "label": f.label, "type": f.type,
                     "required": f.required}
                    for f in template.fields
                ],
            })
        return Response({
            "templates": items,
            # P8 — L'écran doit savoir SOUS QUELLE IDENTITÉ il travaille, et
            # le dire. En mode consolidé, `academy` est nul : l'interface
            # exige alors un choix explicite avant toute production.
            "academy": {
                "code": academy.code if academy else None,
                "name": academy.name if academy else None,
                "short_name": academy.short_name if academy else None,
            } if academy else None,
            "consolidated": academy is None,
        })


class DocumentListCreateView(APIView):
    """
    GET  /api/documents/            — documents visibles par l'utilisateur
    POST /api/documents/            — produit un brouillon
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = _visible_documents(request.user, request)
        academy = get_request_school(request)
        if academy is not None:
            queryset = queryset.filter(academy=academy)

        student_id = request.query_params.get("student")
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        template_id = request.query_params.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)

        return Response([_serialize(doc, request) for doc in queryset[:300]])

    def post(self, request):
        user = request.user
        if user.role_level < ISSUER_ROLE_LEVEL:
            return Response(
                {"detail": "Seule l'administration peut produire un document officiel."},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = _visible_students(user, request).filter(
            pk=request.data.get("student"),
        ).first()
        if student is None:
            return Response({"detail": "Élève introuvable ou hors de votre périmètre."},
                            status=status.HTTP_404_NOT_FOUND)

        template_id = request.data.get("template")
        extra = request.data.get("values") or {}
        preview = bool(request.data.get("preview"))

        # P8 — L'ACADÉMIE EST CELLE DE L'ÉLÈVE, et le gabarit doit
        # l'autoriser. Sans ce contrôle, un super administrateur en mode
        # consolidé pouvait produire un diplôme au fond FEBA pour un élève
        # de l'académie en ligne : le document sortait complet, plausible,
        # et à l'effigie de la mauvaise académie.
        try:
            template = load_template(template_id)
        except TemplateError as exc:
            return Response({"detail": exc.messages[0] if exc.messages else str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        academy_blocker = template.academy_blocker(student.school)
        if academy_blocker:
            return Response({"detail": academy_blocker},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            document = create_document(
                template_id=template_id, student=student, user=user,
                extra_values=extra, preview=preview,
            )
        except (TemplateError, ValidationError) as exc:
            return Response({"detail": " ".join(exc.messages)},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize(document, request), status=status.HTTP_201_CREATED)


class DocumentIssueView(APIView):
    """POST /api/documents/<id>/issue/ — délivre le document."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role_level < ISSUER_ROLE_LEVEL:
            return Response({"detail": "Seule l'administration peut délivrer un document."},
                            status=status.HTTP_403_FORBIDDEN)

        document = _visible_documents(user, request).filter(pk=pk).first()
        if document is None:
            return Response({"detail": "Document introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            issue_document(document, user=user)
        except (TemplateError, ValidationError) as exc:
            return Response({"detail": " ".join(exc.messages)},
                            status=status.HTTP_409_CONFLICT)
        return Response(_serialize(document, request))


class DocumentRevokeView(APIView):
    """POST /api/documents/<id>/revoke/  {"reason": "…"}"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role_level < ISSUER_ROLE_LEVEL:
            return Response({"detail": "Seule l'administration peut révoquer un document."},
                            status=status.HTTP_403_FORBIDDEN)

        document = _visible_documents(user, request).filter(pk=pk).first()
        if document is None:
            return Response({"detail": "Document introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            document.transition_to(
                GeneratedDocument.REVOKED, user=user,
                reason=request.data.get("reason", ""),
            )
        except ValidationError as exc:
            return Response({"detail": " ".join(exc.messages)},
                            status=status.HTTP_409_CONFLICT)

        DocumentEvent.objects.create(
            document=document, action="revoked", to_status=document.status,
            performed_by=user, detail=document.revocation_reason,
        )
        return Response(_serialize(document, request))


class DocumentReplaceView(APIView):
    """POST /api/documents/<id>/replace/ — émet un remplaçant."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role_level < ISSUER_ROLE_LEVEL:
            return Response({"detail": "Seule l'administration peut remplacer un document."},
                            status=status.HTTP_403_FORBIDDEN)

        document = _visible_documents(user, request).filter(pk=pk).first()
        if document is None:
            return Response({"detail": "Document introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            replacement = replace_document(
                document, user=user, reason=request.data.get("reason", ""),
                extra_values=request.data.get("values") or {},
            )
        except (TemplateError, ValidationError) as exc:
            return Response({"detail": " ".join(exc.messages)},
                            status=status.HTTP_409_CONFLICT)
        return Response(_serialize(replacement, request), status=status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    """
    GET /api/documents/<id>/download/

    Diffuse le PDF depuis le stockage privé. C'est le seul chemin d'accès
    au fichier : il n'existe aucune URL directe.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        document = _visible_documents(request.user, request).filter(pk=pk).first()
        if document is None:
            # 404 et non 403 : confirmer l'existence d'un document qu'on
            # n'a pas le droit de voir est déjà une information.
            return Response({"detail": "Document introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        path = document.absolute_path
        if not path or not os.path.exists(path):
            return Response(
                {"detail": "Le fichier de ce document est absent du stockage."},
                status=status.HTTP_410_GONE,
            )

        filename = f"{document.number or document.template_id}-{document.pk}.pdf"
        response = FileResponse(open(path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        # Un document officiel ne doit pas rester dans un cache partagé :
        # un poste consulté par plusieurs familles servirait le diplôme
        # d'un autre élève.
        response["Cache-Control"] = "private, no-store"
        return response


class DocumentHistoryView(APIView):
    """GET /api/documents/<id>/history/ — journal des opérations."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        document = _visible_documents(request.user, request).filter(pk=pk).first()
        if document is None:
            return Response({"detail": "Document introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        return Response([
            {
                "action": event.action,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "performed_by": (event.performed_by.get_full_name()
                                 if event.performed_by else None),
                "detail": event.detail,
                "performed_at": event.performed_at,
            }
            for event in document.events.all()
        ])
