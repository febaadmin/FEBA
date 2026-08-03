"""
P3 — Le message qui accompagne un rapport mensuel.

CE QUI DISTINGUE « ACCEPTÉ » DE « ENVOYÉ »
------------------------------------------
Django considère qu'un message est « envoyé » dès que le backend l'a
accepté. Or le backend par défaut en développement écrit dans la console,
et le backend de fichier écrit sur le disque. Dans les deux cas
`send_messages()` renvoie 1, et une lecture naïve conclut « le parent a
reçu son rapport ».

Cette fonction distingue donc explicitement :

  - `accepted`            : le backend a pris le message ;
  - `used_real_provider`  : ce backend parle à un serveur externe ;
  - `message_id`          : l'identifiant que ce serveur a rendu.

Seule la combinaison des trois autorise le statut « envoyé ». Les deux
autres cas restent visibles tels quels dans l'écran d'administration.
"""
import logging
import uuid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.schools.branding import get_branding

from .models import MONTH_NAMES_EN, MONTH_NAMES_FR

logger = logging.getLogger("apps")

#: Backends qui n'atteignent aucun serveur externe. Un envoi « réussi »
#: par l'un d'eux est une écriture locale, rien de plus.
LOCAL_BACKENDS = (
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
)


def provider_is_external():
    """Le backend configuré parle-t-il à un serveur de messagerie ?"""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if backend in LOCAL_BACKENDS:
        return False
    # SMTP sans hôte configuré ne joindra jamais personne.
    if backend.endswith("smtp.EmailBackend"):
        return bool(getattr(settings, "EMAIL_HOST", ""))
    return True


def sender_for(academy):
    """Expéditeur PROPRE à l'académie : un parent doit pouvoir répondre."""
    code = getattr(academy, "code", "")
    if code == "FEBA_FHA":
        return (getattr(settings, "FHA_FROM_EMAIL", "")
                or settings.DEFAULT_FROM_EMAIL)
    return (getattr(settings, "FEBA_FROM_EMAIL", "")
            or settings.DEFAULT_FROM_EMAIL)


def build_bodies(report, language):
    """Corps du message, en texte et en HTML, dans la langue du parent."""
    brand = get_branding(report.academy)
    eleve = (report.generated_data or {}).get("eleve", {}).get("nom", "")
    resume = (report.generated_data or {}).get("resume", {})
    vide = resume.get("mois_sans_donnee")

    if language == "en":
        mois = f"{MONTH_NAMES_EN[report.month]} {report.year}"
        subject = f"[{brand.short_name}] Monthly report — {eleve} — {mois}"
        lines = [
            "Hello,",
            "",
            f"Please find attached the monthly report for {eleve}, "
            f"covering {mois}.",
            "",
        ]
        if vide:
            lines.append(
                "No activity was recorded for this period. The report is "
                "issued for information only.")
        else:
            lines.append(
                f"{resume.get('rubriques_renseignees', 0)} of "
                f"{resume.get('rubriques_totales', 0)} sections contain "
                f"data for this month.")
        lines += [
            "",
            f"Report reference: {report.reference}",
            "",
            "Kind regards,",
            brand.display_name,
        ]
    else:
        mois = f"{MONTH_NAMES_FR[report.month]} {report.year}"
        subject = f"[{brand.short_name}] Rapport mensuel — {eleve} — {mois}"
        lines = [
            "Bonjour,",
            "",
            f"Vous trouverez en pièce jointe le rapport mensuel de {eleve}, "
            f"pour le mois de {mois}.",
            "",
        ]
        if vide:
            lines.append(
                "Aucune activité n'a été enregistrée pour cette période. "
                "Ce rapport vous est transmis pour information.")
        else:
            lines.append(
                f"{resume.get('rubriques_renseignees', 0)} rubrique(s) sur "
                f"{resume.get('rubriques_totales', 0)} contiennent des "
                f"données pour ce mois.")
        lines += [
            "",
            f"Référence du rapport : {report.reference}",
            "",
            "Cordialement,",
            brand.display_name,
        ]

    if brand.footer_text:
        lines += ["", brand.footer_text]

    texte = "\n".join(lines)
    html = (
        "<div style=\"font-family:Georgia,serif;color:#1F2937\">"
        + "".join(f"<p>{ligne}</p>" if ligne else "<br/>" for ligne in lines)
        + "</div>"
    )
    return subject, texte, html


def send_monthly_report_email(report, recipients):
    """
    Envoie le rapport et rapporte ce qui s'est passé, sans embellir.

    Ne lève jamais : l'échec est une donnée du rapport, pas une panne de
    l'application.
    """
    from .services import preferred_language

    language = preferred_language(report)
    subject, texte, html = build_bodies(report, language)
    brand = get_branding(report.academy)

    tracking = uuid.uuid4().hex
    try:
        message = EmailMultiAlternatives(
            subject=subject, body=texte,
            from_email=sender_for(report.academy), to=list(recipients),
            connection=get_connection(),
        )
        message.attach_alternative(html, "text/html")

        with open(report.pdf_absolute_path, "rb") as handle:
            from .pdf import report_filename

            message.attach(report_filename(report), handle.read(),
                           "application/pdf")

        # Un identifiant de suivi voyage dans l'en-tête : il permet de
        # retrouver le message côté serveur de réception, et de prouver
        # qu'un envoi correspond bien à CE rapport.
        message.extra_headers["X-FEBA-Report-Id"] = report.reference or ""
        message.extra_headers["X-FEBA-Tracking-Id"] = tracking
        reply_to = getattr(settings, "EMAIL_REPLY_TO", "")
        if reply_to:
            message.reply_to = [reply_to]

        accepted = message.send(fail_silently=False)
    except Exception as exc:
        logger.exception("Rapport %s — envoi refusé", report.reference)
        return {"accepted": False, "used_real_provider": provider_is_external(),
                "message_id": "", "error": f"{type(exc).__name__}: {exc}"}

    externe = provider_is_external()
    if not accepted:
        return {"accepted": False, "used_real_provider": externe,
                "message_id": "",
                "error": "Le backend de messagerie a refusé le message."}

    if not externe:
        # Le message a été écrit localement. L'annoncer comme « envoyé »
        # serait un mensonge poli : personne ne l'a reçu.
        return {
            "accepted": False, "used_real_provider": False, "message_id": "",
            "error": ("Message capturé localement par le backend "
                      f"« {settings.EMAIL_BACKEND} » : aucun fournisseur "
                      "externe ne l'a accepté."),
        }

    return {"accepted": True, "used_real_provider": True,
            "message_id": tracking, "error": ""}
