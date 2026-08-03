"""
apps/website/fha_enrollment.py — Ce qui se passe quand une famille envoie
sa fiche d'inscription FEBA FHA.

L'ORDRE DES OPÉRATIONS EST LE SUJET
-----------------------------------
Deux familles d'actions, séparées à dessein.

Ce qui DOIT être atomique : valider, numéroter, enregistrer. Si l'une
échoue, rien n'est écrit — une fiche à moitié enregistrée, sans numéro ou
sans consentements, est un dossier qu'on croira complet.

Ce qui NE DOIT PAS l'être : produire le PDF, notifier, envoyer l'accusé de
réception. Un serveur SMTP injoignable ne doit pas faire perdre une
inscription. Ces étapes se produisent APRÈS la validation de la
transaction, chacune consignée, chacune reprise possible.

CE QUE L'ÉCRAN PUBLIC A LE DROIT DE DIRE
----------------------------------------
Il annonçait « Vous recevrez un e-mail de confirmation » avant même que la
couche d'envoi ait répondu. Il ne le dit plus que si l'envoi a réellement
été accepté ; sinon il annonce le numéro de dossier — qui, lui, est acquis
— et invite à noter ce numéro. Une promesse non tenue coûte plus cher
qu'une information manquante.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("apps")

PURPOSE_PARENT_ACK = "fha_enrollment_ack"
PURPOSE_ADMIN_ALERT = "fha_enrollment_admin_alert"


# ── Destinataires internes ───────────────────────────────────────────────


def academy_admin_emails(entity):
    """Administrateurs de CETTE académie. Jamais ceux de l'autre."""
    from apps.accounts.models import CustomUser

    return list(
        CustomUser.objects
        .filter(school=entity, role="admin", is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def superadmin_emails():
    """
    Super administrateurs, quelle que soit leur académie de rattachement.

    Ils supervisent l'ensemble : une inscription qui n'arrive nulle part
    parce que l'académie concernée n'a pas encore d'administrateur doit
    tout de même être vue par quelqu'un.
    """
    from apps.accounts.models import CustomUser

    return list(
        CustomUser.objects
        .filter(role="superadmin", is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


# ── Fiche PDF ────────────────────────────────────────────────────────────


def generate_and_store_sheet(application):
    """
    Produit la fiche et la range dans le stockage privé.

    Ne lève pas : un échec de production ne doit pas effacer une
    inscription valide. Il est enregistré dans `sheet_error`, visible en
    administration, et la fiche est régénérable d'un clic.
    """
    from .fha_pdf import generate_enrollment_sheet

    try:
        content = generate_enrollment_sheet(application)
    except Exception as exc:
        application.sheet_error = f"{type(exc).__name__}: {exc}"[:2000]
        application.save(update_fields=["sheet_error", "updated_at"])
        logger.exception("FHA — fiche PDF non produite pour %s", application.reference)
        return None

    application.store_sheet(content)
    application.save(update_fields=[
        "sheet_path", "sheet_sha256", "sheet_size", "sheet_generated_at",
        "sheet_version", "sheet_error", "updated_at",
    ])
    logger.info(
        "FHA — fiche %s produite (%d octets, empreinte %s…)",
        application.reference, application.sheet_size,
        application.sheet_sha256[:16],
    )
    return content


# ── Corps des messages ───────────────────────────────────────────────────


def parent_ack_bodies(application):
    """
    Accusé de réception, en texte ET en HTML, dans la langue du parent.

    Les deux versions disent la même chose : un client de messagerie qui
    n'affiche pas le HTML ne doit pas recevoir un message vide.
    """
    from apps.schools.branding import get_branding

    brand = get_branding(application.entity)
    english = application.parent1_preferred_language != "fr"
    child = f"{application.child_first_name} {application.child_last_name}".strip()
    reference = application.reference

    if english:
        subject = f"[{brand.short_name}] Enrollment form received — file {reference}"
        greeting = f"Hello {application.parent1_first_name},"
        lines = [
            f"We have received the enrollment form for {child}.",
            f"Your file number is {reference}. Please keep it: it identifies "
            f"your application in every exchange with us.",
            "Next step: booking the French placement assessment "
            "(15 to 20 minutes, by video conference).",
            "The completed form is attached to this message.",
        ]
        closing = "Kind regards,"
    else:
        subject = f"[{brand.short_name}] Fiche d'inscription reçue — dossier {reference}"
        greeting = f"Bonjour {application.parent1_first_name},"
        lines = [
            f"Nous avons bien reçu la fiche de renseignements de {child}.",
            f"Votre numéro de dossier est {reference}. Conservez-le : il "
            f"identifie votre demande dans tous nos échanges.",
            "Prochaine étape : la réservation du test de placement "
            "(15 à 20 minutes, en visioconférence).",
            "La fiche complète est jointe à ce message.",
        ]
        closing = "Cordialement,"

    signature = brand.legal_name
    text = "\n\n".join([greeting, *lines, f"{closing}\n{signature}"])

    import html as html_module

    def esc(value):
        return html_module.escape(str(value), quote=False)

    paragraphs = "".join(
        f'<p style="margin:0 0 14px;line-height:1.55;">{esc(line)}</p>'
        for line in lines
    )
    html_body = f"""<!doctype html>
<html lang="{'en' if english else 'fr'}">
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:Helvetica,Arial,sans-serif;color:#1e293b;font-size:15px;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;">
    <div style="background:{esc(brand.primary_color)};padding:20px 24px;">
      <p style="margin:0;color:#ffffff;font-size:17px;font-weight:bold;">{esc(brand.display_name)}</p>
    </div>
    <div style="padding:24px;">
      <p style="margin:0 0 14px;">{esc(greeting)}</p>
      {paragraphs}
      <p style="margin:24px 0 0;">{esc(closing)}<br><strong>{esc(signature)}</strong></p>
    </div>
    <div style="padding:14px 24px;background:#f8fafc;color:#64748b;font-size:12px;">
      {esc(brand.address_line)}
    </div>
  </div>
</body>
</html>"""
    return subject, text, html_body


def admin_alert_bodies(application):
    """Notification interne : ce qu'un administrateur doit voir d'un coup d'œil."""
    from apps.schools.branding import get_branding

    brand = get_branding(application.entity)
    reference = application.reference
    subject = f"[{brand.short_name}] Nouvelle fiche d'inscription — {reference}"

    rows = [
        ("Dossier", reference),
        ("Académie", f"{brand.display_name} [{brand.academy_code}]"),
        ("Enfant", f"{application.child_first_name} {application.child_last_name}"),
        ("Âge", f"{application.child_age} ans" if application.child_age is not None else "—"),
        ("Pays", application.child_country or "—"),
        ("Groupe suggéré",
         dict(application.GROUP_CHOICES).get(application.suggested_group, "à déterminer")),
        ("Responsable",
         f"{application.parent1_first_name} {application.parent1_last_name}"),
        ("E-mail", application.parent1_email),
        ("Téléphone", application.parent1_phone or "—"),
        ("WhatsApp", application.parent1_whatsapp or "—"),
        ("Fuseau famille", application.family_timezone or "—"),
        ("Besoins particuliers signalés",
         "oui" if application.special_needs.strip() else "non"),
    ]
    text = "\n".join(f"{label} : {value}" for label, value in rows)

    import html as html_module

    def esc(value):
        return html_module.escape(str(value), quote=False)

    cells = "".join(
        f'<tr><td style="padding:6px 10px;color:#64748b;">{esc(label)}</td>'
        f'<td style="padding:6px 10px;font-weight:600;">{esc(value)}</td></tr>'
        for label, value in rows
    )
    html_body = f"""<!doctype html>
<html lang="fr">
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:Helvetica,Arial,sans-serif;color:#1e293b;font-size:14px;">
  <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;">
    <div style="background:{esc(brand.primary_color)};padding:18px 22px;">
      <p style="margin:0;color:#ffffff;font-weight:bold;">Nouvelle fiche d'inscription — {esc(reference)}</p>
    </div>
    <table style="width:100%;border-collapse:collapse;">{cells}</table>
    <div style="padding:14px 22px;background:#f8fafc;color:#64748b;font-size:12px;">
      La fiche complète est jointe. Elle contient des données personnelles
      d'un mineur : ne pas la rediffuser.
    </div>
  </div>
</body>
</html>"""
    return subject, text, html_body


# ── Orchestration ────────────────────────────────────────────────────────


def process_submission(application):
    """
    Étapes qui suivent l'enregistrement de la fiche.

    Appelée APRÈS la validation de la transaction : le dossier existe déjà
    et ne peut plus être perdu par ce qui suit.

    Renvoie un état lisible par la vue, pour qu'elle n'annonce que ce qui
    s'est réellement produit.
    """
    from apps.notifications.email_models import EmailDelivery
    from apps.notifications.mailer import send_tracked_email

    content = generate_and_store_sheet(application)
    attachments = []
    if content:
        from .fha_pdf import sheet_filename
        attachments = [(sheet_filename(application), content, "application/pdf")]

    # ── Accusé de réception au parent ─────────────────────────────────
    subject, text, html_body = parent_ack_bodies(application)
    parent_delivery = send_tracked_email(
        purpose=PURPOSE_PARENT_ACK,
        to_email=application.parent1_email,
        subject=subject,
        text_body=text,
        html_body=html_body,
        entity=application.entity,
        reference=application.reference,
        language=application.parent1_preferred_language,
        attachments=attachments,
    )

    # ── Notification interne : admins de l'académie + super admins ────
    recipients = academy_admin_emails(application.entity)
    supers = [e for e in superadmin_emails() if e not in recipients]
    admin_subject, admin_text, admin_html = admin_alert_bodies(application)

    admin_deliveries = []
    for address in recipients + supers:
        admin_deliveries.append(send_tracked_email(
            purpose=PURPOSE_ADMIN_ALERT,
            to_email=address,
            subject=admin_subject,
            text_body=admin_text,
            html_body=admin_html,
            entity=application.entity,
            reference=application.reference,
            language="fr",
            attachments=attachments,
        ))

    if not recipients and not supers:
        # Personne à prévenir : ce n'est pas un détail. Une inscription qui
        # n'arrive dans aucune boîte attend indéfiniment.
        logger.warning(
            "FHA — dossier %s : AUCUN destinataire interne (ni administrateur "
            "de l'académie, ni super administrateur avec une adresse).",
            application.reference,
        )

    # ── Notifications dans l'application ──────────────────────────────
    _create_in_app_notifications(application)

    return {
        "reference": application.reference,
        "sheet_generated": bool(content),
        "sheet_error": application.sheet_error,
        "parent_email_status": parent_delivery.status,
        "parent_email_tracking_id": str(parent_delivery.tracking_id),
        "parent_email_accepted": parent_delivery.is_delivered_to_provider,
        "admin_recipients": len(admin_deliveries),
        "admin_email_failures": sum(
            1 for d in admin_deliveries if d.status == EmailDelivery.FAILED
        ),
    }


def _create_in_app_notifications(application):
    """
    Notification dans l'application, pour les comptes concernés.

    Un e-mail peut se perdre, être filtré, ou partir vers une adresse
    inactive. La notification interne, elle, attend l'administrateur à sa
    prochaine connexion.
    """
    from apps.accounts.models import CustomUser
    from apps.notifications.models import Notification

    recipients = list(
        CustomUser.objects.filter(
            school=application.entity, role="admin", is_active=True,
        )
    ) + list(CustomUser.objects.filter(role="superadmin", is_active=True))

    seen = set()
    title = f"Nouvelle fiche d'inscription — {application.reference}"
    message = (
        f"{application.child_first_name} {application.child_last_name} "
        f"({application.child_age} ans) — déposée par "
        f"{application.parent1_first_name} {application.parent1_last_name}."
    )
    for user in recipients:
        if user.pk in seen:
            continue
        seen.add(user.pk)
        Notification.objects.create(
            user=user, type="message", title=title, message=message,
            related_url=f"/admin/fha-admissions?reference={application.reference}",
        )


def resend_parent_acknowledgement(application, user=None):
    """
    Relance l'accusé de réception depuis l'administration.

    Régénère la fiche si elle manque : relancer un e-mail en promettant une
    pièce jointe absente reproduirait le défaut qu'on corrige.
    """
    from apps.notifications.email_models import EmailDelivery
    from apps.notifications.mailer import resend, send_tracked_email

    from .fha_pdf import sheet_filename

    content = None
    if application.has_sheet:
        with open(application.sheet_absolute_path, "rb") as handle:
            content = handle.read()
    else:
        content = generate_and_store_sheet(application)

    attachments = (
        [(sheet_filename(application), content, "application/pdf")]
        if content else []
    )
    subject, text, html_body = parent_ack_bodies(application)

    existing = (
        EmailDelivery.objects
        .filter(purpose=PURPOSE_PARENT_ACK, subject_reference=application.reference,
                to_email=application.parent1_email)
        .order_by("-created_at").first()
    )
    if existing is not None:
        delivery = resend(existing, text, html_body, attachments)
    else:
        delivery = send_tracked_email(
            purpose=PURPOSE_PARENT_ACK,
            to_email=application.parent1_email,
            subject=subject, text_body=text, html_body=html_body,
            entity=application.entity, reference=application.reference,
            language=application.parent1_preferred_language,
            attachments=attachments,
        )

    logger.info(
        "FHA — accusé de réception relancé pour %s par %s : %s",
        application.reference, getattr(user, "email", "système"), delivery.status,
    )
    return delivery


@transaction.atomic
def create_application(serializer):
    """
    Enregistrement ATOMIQUE de la fiche.

    Tout ce qui est ici est indissociable : numéro, champs, consentements
    datés, première ligne d'historique. Un dossier sans numéro ou sans
    historique d'état n'est pas un dossier à moitié créé — c'est un dossier
    dont on ne pourra rien dire.

    Les envois et la production du PDF sont VOLONTAIREMENT dehors : voir
    `process_submission`.
    """
    return serializer.save()
