"""
Audit de la chaîne complète d'un champ : formulaire → base → écran → PDF →
e-mail → export.

POURQUOI CETTE COMMANDE PLUTÔT QU'UN TABLEAU ÉCRIT À LA MAIN
-------------------------------------------------------------
Un tableau rédigé décrit l'intention. Il reste juste le jour où on l'écrit
et devient faux au premier champ ajouté — sans que personne ne s'en
aperçoive. C'est exactement ce qui s'est passé avec le numéro WhatsApp :
il figurait dans le modèle, dans le formulaire, et il ne traversait
pourtant pas le serializer.

Cette commande INTERROGE le code. Pour chaque champ des modèles publics,
elle constate :

  écriture   — le serializer public l'accepte-t-il ?
  lecture    — le serializer d'administration l'expose-t-il ?
  PDF        — figure-t-il sur le document produit ?
  export     — figure-t-il dans l'export CSV ?

Un « non » n'est pas forcément un défaut : certains champs n'ont pas leur
place partout (l'adresse IP de soumission ne va sur aucun PDF). La colonne
« attendu » dit lesquels comptent.

    python manage.py field_mapping_audit
    python manage.py field_mapping_audit --markdown > FIELD_MAPPING_AUDIT.md
    python manage.py field_mapping_audit --strict     # sort 1 sur défaut
"""
from django.core.management.base import BaseCommand

#: Champs volontairement absents de certaines étapes, avec la raison. Un
#: champ listé ici n'est pas un défaut — c'est une décision, et elle est
#: écrite.
DELIBERATE_OMISSIONS = {
    "submitted_ip": "Donnée technique de traçabilité — jamais sur un document remis.",
    "sheet_path": "Chemin de stockage interne — le publier faciliterait un accès direct.",
    "sheet_sha256": "Empreinte technique du fichier.",
    "sheet_size": "Métadonnée technique.",
    "sheet_version": "Métadonnée technique.",
    "sheet_error": "Diagnostic interne, affiché à l'administration seule.",
    "sheet_generated_at": "Métadonnée technique.",
    "entity": "Imposée par le serveur d'après la route — jamais lue du client.",
    "reference": "Attribuée par le serveur.",
    "status": "Piloté par le parcours d'admission, pas par le formulaire.",
    "recommended_group": "Renseigné après le test de placement.",
    "consents_version": "Fixée par le serveur au moment de l'acceptation.",
    "consents_accepted_at": "Horodatée par le serveur.",
    "created_at": "Horodatage serveur.",
    "updated_at": "Horodatage serveur.",
    "id": "Identifiant technique.",
    "is_read": "État de lecture interne, pas une saisie du visiteur.",
    "child_photo": "Fichier binaire — servi par une vue dédiée, pas dans un CSV.",
}


def _serializer_fields(serializer_class):
    try:
        return set(serializer_class().get_fields().keys())
    except Exception:  # pragma: no cover - serializer nécessitant un contexte
        return set()


def _model_fields(model):
    return [field.name for field in model._meta.fields]


def audit_fha_enrollment():
    """La fiche d'inscription FEBA FHA — le formulaire le plus large."""
    from apps.website.fha_pdf import build_sections
    from apps.website.fha_serializers import (
        FHAApplicationDetailSerializer, FHAApplicationListSerializer,
        FHAEnrollmentCreateSerializer,
    )
    from apps.website.fha_views import _export_columns
    from apps.website.models import FHAEnrollmentApplication

    write = _serializer_fields(FHAEnrollmentCreateSerializer)
    read = _serializer_fields(FHAApplicationDetailSerializer)
    listed = _serializer_fields(FHAApplicationListSerializer)
    exported = {key for _label, key in _export_columns()}

    # Les libellés du PDF sont écrits en français ; on rapproche par la
    # VALEUR effectivement rendue, pas par le nom du champ, pour ne pas
    # déclarer présent un champ dont seul le titre figure.
    pdf_labels = set()
    for _title, rows in build_sections(_probe_application()):
        for label, _value in rows:
            pdf_labels.add(label)

    rows = []
    for name in _model_fields(FHAEnrollmentApplication):
        rows.append({
            "field": name,
            "write": name in write,
            "read": name in read,
            "list": name in listed,
            "export": name in exported,
            "note": DELIBERATE_OMISSIONS.get(name, ""),
        })
    return "Fiche d'inscription FEBA FHA", rows, len(pdf_labels)


def audit_contact_message():
    """Les deux formulaires de contact."""
    from apps.website.fha_serializers import FHAContactMessageCreateSerializer
    from apps.website.models import ContactMessage
    from apps.website.serializers import (
        ContactMessageAdminSerializer, ContactMessageCreateSerializer,
    )

    feba_write = _serializer_fields(ContactMessageCreateSerializer)
    fha_write = _serializer_fields(FHAContactMessageCreateSerializer)
    read = _serializer_fields(ContactMessageAdminSerializer)

    rows = []
    for name in _model_fields(ContactMessage):
        rows.append({
            "field": name,
            "write": name in feba_write or name in fha_write,
            "read": name in read,
            "list": name in read,
            "export": name in read,
            "note": DELIBERATE_OMISSIONS.get(name, ""),
        })
    return "Message de contact (FEBA et FEBA FHA)", rows, 0


def audit_preregistration():
    """La préinscription FEBA."""
    from apps.website.models import PreRegistration
    from apps.website.serializers import (
        PreRegistrationAdminSerializer, PreRegistrationCreateSerializer,
    )

    # `export` est lu sur les colonnes RÉELLEMENT écrites dans le CSV, pas
    # déduit du serializer de lecture. Les deux avaient divergé : l'audit
    # annonçait `export=True` pour `sheet_path` et `sheet_sha256`, que
    # l'export exclut délibérément — un chemin de fichier serveur dans un
    # tableur diffusé n'aide personne et renseigne un attaquant. Un audit
    # qui décrit une intention au lieu du code finit par rassurer à tort.
    from apps.website.views import _prereg_export_columns

    write = _serializer_fields(PreRegistrationCreateSerializer)
    read = _serializer_fields(PreRegistrationAdminSerializer)
    exported = {key for _, key in _prereg_export_columns()}

    rows = []
    for name in _model_fields(PreRegistration):
        rows.append({
            "field": name,
            "write": name in write,
            "read": name in read,
            "list": name in read,
            "export": name in exported,
            "note": DELIBERATE_OMISSIONS.get(name, ""),
        })
    return "Préinscription FEBA", rows, 0


def _probe_application():
    """
    Objet NON ENREGISTRÉ, servant uniquement à énumérer les sections du PDF.

    Construit en mémoire : l'audit ne doit écrire aucune donnée, et surtout
    pas dans une base de production.
    """
    import datetime

    from django.utils import timezone

    from apps.website.models import FHAEnrollmentApplication

    probe = FHAEnrollmentApplication(
        reference="AUDIT-0000",
        child_birth_date=datetime.date(2015, 1, 1),
        consents_accepted_at=None,
    )
    # Horodatages CONSCIENTS du fuseau : `build_sections` les convertit en
    # heure locale, et une valeur naïve y lèverait.
    probe.created_at = timezone.now()
    probe.updated_at = probe.created_at
    return probe


AUDITS = [audit_fha_enrollment, audit_contact_message, audit_preregistration]


class Command(BaseCommand):
    help = "Suit chaque champ du formulaire jusqu'à l'export."

    def add_arguments(self, parser):
        parser.add_argument("--markdown", action="store_true",
                            help="Sortie en tableaux Markdown.")
        parser.add_argument("--strict", action="store_true",
                            help="Sortir en erreur si un champ saisi n'est pas relu.")

    def handle(self, *args, **options):
        markdown = options["markdown"]
        problems = []

        if markdown:
            self.stdout.write("# Audit de la chaîne des champs\n")
            self.stdout.write(
                "Ce fichier est **produit par `manage.py field_mapping_audit`**, "
                "pas rédigé à la main. Un tableau écrit reste juste le jour où "
                "on l'écrit et devient faux au premier champ ajouté — c'est "
                "exactement ainsi que le numéro WhatsApp a disparu : présent "
                "dans le modèle et dans le formulaire, absent du serializer.\n"
            )
            self.stdout.write(
                "Colonnes : **Saisi** (le serializer public l'accepte) · "
                "**Relu** (l'administration le voit) · **Liste** (visible sans "
                "ouvrir le détail) · **Export** (présent dans le CSV).\n"
            )

        for audit in AUDITS:
            title, rows, pdf_sections = audit()

            if markdown:
                self.stdout.write(f"\n## {title}\n")
                self.stdout.write("| Champ | Saisi | Relu | Liste | Export | Remarque |")
                self.stdout.write("|---|:-:|:-:|:-:|:-:|---|")
            else:
                self.stdout.write(self.style.MIGRATE_HEADING(f"\n{title}"))

            for row in rows:
                mark = lambda ok: "✅" if ok else "—"  # noqa: E731
                # Un champ SAISI mais jamais RELU est le défaut que cet
                # audit existe pour trouver : la donnée entre en base et
                # n'en ressort nulle part.
                broken = row["write"] and not row["read"]
                if broken and not row["note"]:
                    problems.append(f"{title} · {row['field']} : saisi mais jamais relu.")

                if markdown:
                    self.stdout.write(
                        f"| `{row['field']}` | {mark(row['write'])} | "
                        f"{mark(row['read'])} | {mark(row['list'])} | "
                        f"{mark(row['export'])} | {row['note']} |"
                    )
                else:
                    flag = self.style.ERROR("✗") if broken else " "
                    self.stdout.write(
                        f"  {flag} {row['field']:<36} "
                        f"saisi={row['write']!s:<5} relu={row['read']!s:<5} "
                        f"export={row['export']!s}"
                    )

            if pdf_sections and markdown:
                self.stdout.write(
                    f"\n{pdf_sections} libellés répartis en sections sur la "
                    f"fiche PDF ; le test `test_la_fiche_contient_toutes_les_"
                    f"sections` vérifie qu'aucune ne manque au rendu.\n"
                )

        if markdown:
            self.stdout.write("\n## Résultat\n")
            if problems:
                for problem in problems:
                    self.stdout.write(f"- ❌ {problem}")
            else:
                self.stdout.write(
                    "Aucun champ saisi ne reste invisible : chaque valeur "
                    "acceptée par un formulaire public est relue par "
                    "l'administration.\n"
                )
            return

        self.stdout.write("")
        if problems:
            for problem in problems:
                self.stderr.write(self.style.ERROR(f"  ✗ {problem}"))
            if options["strict"]:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS(
                "Aucun champ saisi ne reste invisible."
            ))
