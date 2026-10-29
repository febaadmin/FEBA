"""
API du barème d'appréciations (écran « Appréciations »).

  GET  /api/grades/appreciations/?cycle=college   barème de l'académie (+ effectif)
  PUT  /api/grades/appreciations/                 remplace le barème (atomique)
  POST /api/grades/appreciations/preview/         appréciation d'une note (barème
                                                  enregistré, ou brouillon fourni)
  POST /api/grades/appreciations/reset/           barème par défaut (confirmation)

L'académie est TOUJOURS celle de la requête (apps.core.tenancy) : un
administrateur ne lit et ne modifie que la sienne, quel que soit le
paramètre envoyé ; le super administrateur doit avoir choisi une académie.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove, IsTeacherOrAbove
from apps.core.tenancy import get_request_school

from . import appreciations as svc
from .models import AppreciationRule

NO_ACADEMY = {"detail": (
    "Sélectionnez d'abord une académie : chaque académie a son propre barème "
    "d'appréciations.")}


def _academy_or_none(request):
    return get_request_school(request)


def _cycle(request, source):
    cycle = (source.get("cycle") or "").strip()
    if cycle and cycle not in svc.CYCLES:
        return None, Response({"cycle": f"Cycle inconnu : {cycle!r}."}, status=400)
    return cycle, None


def _serialize(rule):
    return {
        "id": rule.id,
        "cycle": rule.cycle,
        "min_percent": str(rule.min_percent),
        "label_fr": rule.label_fr,
        "label_en": rule.label_en,
        "is_active": rule.is_active,
        "updated_at": rule.updated_at,
    }


def _scale_payload(academy, cycle):
    rules = list(AppreciationRule.objects.filter(school=academy, cycle=cycle)
                 .order_by("-is_active", "-min_percent"))
    effective, origin = svc.effective_scale(academy, cycle or None)
    usage = {r.label_fr: svc.label_usage(academy, r.label_fr) for r in rules}
    return {
        "academy": {"id": academy.id, "name": academy.name, "code": academy.code,
                    "academy_type": academy.academy_type},
        "cycle": cycle,
        "rules": [dict(_serialize(r), used_by_bulletins=usage.get(r.label_fr, 0)) for r in rules],
        "effective_origin": origin,
        "effective": [{"min_percent": str(p), "label_fr": fr, "label_en": en}
                      for p, fr, en in effective],
        "cycles_with_override": sorted(set(
            AppreciationRule.objects.filter(school=academy).exclude(cycle="")
            .values_list("cycle", flat=True))),
        "representation": (
            "Seuil bas inclusif en % de la note maximale : une note n sur m reçoit "
            "l'appréciation du palier actif le plus élevé tel que n/m × 100 ≥ seuil."),
    }


class AppreciationScaleView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            # Les enseignants lisent le barème (aperçu pendant la saisie des notes).
            return [IsAuthenticated(), IsTeacherOrAbove()]
        return [IsAuthenticated(), IsAdminOrAbove()]

    def get(self, request):
        academy = _academy_or_none(request)
        if academy is None:
            return Response(NO_ACADEMY, status=400)
        cycle, error = _cycle(request, request.query_params)
        if error:
            return error
        return Response(_scale_payload(academy, cycle))

    def put(self, request):
        academy = _academy_or_none(request)
        if academy is None:
            return Response(NO_ACADEMY, status=400)
        cycle, error = _cycle(request, request.data)
        if error:
            return error
        rows = request.data.get("rules")
        if not isinstance(rows, list):
            return Response({"rules": "Format attendu : liste de paliers."}, status=400)
        try:
            svc.save_scale(academy, cycle, rows, user=request.user)
        except svc.ScaleError as exc:
            return Response({"errors": exc.errors}, status=exc.status)
        return Response(_scale_payload(academy, cycle))


class AppreciationPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherOrAbove]

    def post(self, request):
        academy = _academy_or_none(request)
        if academy is None:
            return Response(NO_ACADEMY, status=400)
        cycle, error = _cycle(request, request.data)
        if error:
            return error
        try:
            value = Decimal(str(request.data.get("value")))
            max_value = Decimal(str(request.data.get("max_value", 20)))
        except (InvalidOperation, ValueError, TypeError):
            return Response({"value": "Note ou barème non numérique."}, status=400)
        draft = request.data.get("rules")
        if draft is not None:
            # Aperçu d'un barème NON ENREGISTRÉ : validé de la même façon.
            if not isinstance(draft, list):
                return Response({"rules": "Format attendu : liste de paliers."}, status=400)
            errors = svc.validate_scale(draft)
            if errors:
                return Response({"errors": errors}, status=400)
            scale = sorted(
                ((Decimal(str(r["min_percent"])), str(r.get("label_fr", "")).strip(),
                  str(r.get("label_en", "")).strip())
                 for r in draft if r.get("is_active", True)),
                key=lambda item: -item[0])
            cache = {(academy.pk, cycle or ""): scale}
        else:
            cache = None
        try:
            fr = svc.appreciation_for(value, max_value, academy=academy, cycle=cycle or None, cache=cache)
            en = svc.appreciation_for(value, max_value, academy=academy, cycle=cycle or None,
                                      language="en", cache=cache)
        except ValueError as exc:
            return Response({"value": str(exc)}, status=400)
        percent = (value * 100 / max_value).quantize(Decimal("0.01"))
        return Response({"value": str(value), "max_value": str(max_value),
                         "percent": str(percent), "label_fr": fr, "label_en": en})


class AppreciationResetView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def post(self, request):
        academy = _academy_or_none(request)
        if academy is None:
            return Response(NO_ACADEMY, status=400)
        if request.data.get("confirm") is not True:
            return Response({"confirm": (
                "Confirmation explicite requise (« confirm »: true) : le barème actuel "
                "sera remplacé.")}, status=400)
        cycle, error = _cycle(request, request.data)
        if error:
            return error
        svc.reset_to_defaults(academy, cycle, user=request.user)
        return Response(_scale_payload(academy, cycle), status=status.HTTP_200_OK)
