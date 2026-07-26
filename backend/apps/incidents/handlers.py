"""
Gestionnaire d'exceptions DRF (V8).

- Les erreurs MÉTIER (400/403/404/409…) sont laissées telles quelles : elles ne
  créent PAS d'incident (sinon la table serait noyée sous les erreurs de
  saisie).
- Les erreurs INATTENDUES (500) créent un incident technique, notifient les
  super administrateurs, puis renvoient un message honnête à l'utilisateur :
  la référence n'est annoncée que si l'incident a réellement été enregistré.
- Aucun traceback ni détail interne n'est exposé au client.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .services import report_incident

MESSAGE_WITH_REFERENCE = (
    "Une erreur interne est survenue. L'incident a été transmis à l'équipe "
    "technique sous la référence {reference}."
)
MESSAGE_WITHOUT_REFERENCE = (
    "Une erreur interne est survenue. Veuillez réessayer ou contacter "
    "l'assistance."
)


def feba_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    # Erreur déjà traduite par DRF (validation, permission, 404…) : on n'y
    # touche pas et on ne crée aucun incident.
    if response is not None:
        return response

    request = context.get("request")
    view = context.get("view")
    module = ""
    if view is not None:
        module = getattr(view, "basename", "") or type(view).__name__

    incident = report_incident(
        exc,
        request=request,
        module=module,
        attempted_action=f"{getattr(request, 'method', '')} {getattr(request, 'path', '')}".strip(),
        severity="high",
        status_code=500,
    )

    if incident is not None:
        detail = MESSAGE_WITH_REFERENCE.format(reference=incident.reference)
        payload = {"detail": detail, "incident_reference": incident.reference}
    else:
        payload = {"detail": MESSAGE_WITHOUT_REFERENCE}

    return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
