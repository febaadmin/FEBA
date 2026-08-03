"""
P2 — Orchestration d'une demande de préinscription FEBA.

LE DÉFAUT CORRIGÉ
-----------------
Une demande était enregistrée en base et c'était tout. Aucune fiche
officielle n'était produite, aucun numéro de dossier n'était donné à la
famille, et le back-office n'affichait que six colonnes : ni courriel, ni
WhatsApp, ni âge, ni année scolaire, ni message, ni adresse. Les champs
étaient collectés depuis des mois et n'apparaissaient nulle part.

LA RÈGLE DE COHÉRENCE
---------------------
La demande et sa fiche sont produites dans la MÊME transaction, mais la
fiche n'est pas une condition de survie de la demande : si le PDF échoue,
la demande reste enregistrée — la famille a rempli le formulaire, sa
demande existe — et l'échec est écrit dans `sheet_error`, remonté au
super administrateur, régénérable d'un clic.

Ce qui est interdit, et que ce module empêche : marquer la demande comme
traitée alors que la fiche n'a jamais existé. Un dossier « complet » sans
pièce est plus dangereux qu'un dossier visiblement incomplet.
"""
import logging

logger = logging.getLogger("apps")


def generate_and_store_prereg_sheet(demande):
    """
    Produit la fiche et la range dans le stockage privé.

    Ne lève jamais : un échec de production ne doit pas effacer une
    demande valide. Renvoie les octets produits, ou `None` en cas
    d'échec — l'appelant peut ainsi distinguer les deux issues sans
    interpréter un booléen ambigu.
    """
    from .feba_prereg_pdf import generate_prereg_sheet

    try:
        content = generate_prereg_sheet(demande)
    except Exception as exc:
        demande.sheet_error = f"{type(exc).__name__}: {exc}"[:2000]
        demande.save(update_fields=["sheet_error"])
        logger.exception("FEBA — fiche de préinscription non produite pour %s",
                         demande.reference)
        return None

    demande.store_sheet(content)
    demande.save(update_fields=[
        "sheet_path", "sheet_sha256", "sheet_generated_at", "sheet_error",
    ])
    logger.info("FEBA — fiche %s produite (%d octets, empreinte %s…)",
                demande.reference, len(content), demande.sheet_sha256[:16])
    return content


def notify_sheet_failure(demande):
    """
    Signale au super administrateur qu'une fiche n'a pas pu être produite.

    Une erreur consignée dans une colonne que personne ne regarde n'est
    pas signalée : elle est archivée. La notification est ce qui
    transforme la trace en information.
    """
    from apps.accounts.models import CustomUser
    from apps.notifications.models import Notification

    # Le super administrateur, et les administrateurs de l'académie
    # concernée — pas ceux de l'autre : une alerte hors périmètre est du
    # bruit, et le bruit finit par masquer les alertes utiles.
    destinataires = list(CustomUser.objects.filter(role="superadmin", is_active=True))
    if demande.entity_id:
        destinataires += list(CustomUser.objects.filter(
            role="admin", is_active=True, school_id=demande.entity_id))

    created = 0
    for user in {u.pk: u for u in destinataires}.values():
        Notification.objects.create(
            user=user,
            # `announcement` est le canal interne existant (la cloche).
            # Le modèle n'a pas de type « erreur » ; en inventer un
            # obligerait à une migration pour un gain nul.
            type="announcement",
            title=f"Fiche de préinscription non produite — {demande.reference}",
            message=(
                f"La fiche PDF du dossier {demande.reference} "
                f"({demande.child_name}) n'a pas pu être produite.\n\n"
                f"Motif : {demande.sheet_error or 'inconnu'}\n\n"
                f"La demande reste enregistrée et la fiche est "
                f"régénérable depuis l'écran des préinscriptions."
            ),
            related_url=f"/admin/website?tab=prereg&reference={demande.reference}",
        )
        created += 1
    return created


def process_submission(demande):
    """
    Tout ce qui suit l'enregistrement d'une demande.

    Renvoie un état explicite plutôt qu'un booléen : l'écran doit pouvoir
    dire à l'administrateur ce qui s'est réellement passé, et non pas
    « ok » pour deux situations différentes.
    """
    content = generate_and_store_prereg_sheet(demande)
    if content is None:
        try:
            notify_sheet_failure(demande)
        except Exception:  # pragma: no cover — la notification est secondaire
            logger.exception("FEBA — alerte de fiche non produite non envoyée")
        return {"sheet_generated": False, "sheet_error": demande.sheet_error}

    return {"sheet_generated": True, "sheet_error": ""}
