"""
apps/documents/services.py — Production d'un document officiel

Un seul point d'entrée pour créer un document : les vues, les commandes
et les tests passent tous par ici. Dupliquer cette logique dans une vue
finirait par produire des documents dont la traçabilité diverge.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.documents.models import DocumentEvent, GeneratedDocument
from apps.documents.renderer import render_document
from apps.documents.templates_registry import load_template
from apps.schools.branding import get_branding


def build_values(template, student, extra=None):
    """
    Valeurs des champs variables, à partir des données réelles de l'élève.

    Le nom est repris tel qu'il est enregistré. Il n'est ni normalisé, ni
    raccourci, ni complété : un diplôme porte le nom de l'élève, pas une
    version arrangée pour tenir dans la maquette.
    """
    values = {
        "student_name": student.get_full_name(),
        "issue_date": timezone.now().date(),
    }
    values.update(extra or {})

    missing = [
        field.label for field in template.fields
        if field.required and not str(values.get(field.name) or "").strip()
    ]
    if missing:
        raise ValidationError(
            f"Champs obligatoires sans valeur : {', '.join(missing)}. "
            f"Le document n'est pas produit : il sortirait avec des blancs."
        )
    return values


def create_document(*, template_id, student, user=None, school_year=None,
                    extra_values=None, preview=False):
    """
    Produit un document à l'état « brouillon » et écrit son PDF.

    L'émission est une étape SÉPARÉE (`transition_to(ISSUED)`) : produire
    et délivrer sont deux décisions distinctes, et la seconde attribue un
    numéro officiel.
    """
    template = load_template(template_id)
    academy = student.school
    if academy is None:
        raise ValidationError(
            "Cet élève n'est rattaché à aucune académie : aucun "
            "établissement ne peut donc délivrer ce document."
        )

    # P8 — LA RÈGLE EST APPLIQUÉE ICI, pas seulement dans la vue.
    #
    # Le contrôle n'existait que dans `DocumentListCreateView.post` : une
    # requête HTTP était bien refusée, mais une commande de gestion, un
    # script d'import ou un test produisait sans rien signaler un diplôme
    # au fond d'une académie pour l'élève d'une autre. Une règle posée à la
    # porte d'entrée HTTP n'est pas une règle : c'est un filtre que le
    # prochain appelant contournera sans le savoir.
    #
    # `create_document` est le point d'entrée unique documenté de ce
    # module. C'est donc ici que la garantie doit vivre.
    academy_blocker = template.academy_blocker(academy)
    if academy_blocker:
        raise ValidationError(academy_blocker)

    values = build_values(template, student, extra_values)
    # Le numéro n'existe qu'à l'émission. L'afficher plus tôt laisserait
    # croire qu'un brouillon est un document délivré.
    values.setdefault("document_number", "")

    document = GeneratedDocument(
        academy=academy,
        student=student,
        school_year=school_year or academy.years.filter(is_current=True).first(),
        template_id=template.id,
        template_version=template.version,
        template_fingerprint=template.fingerprint(),
        background_sha256=template.background_sha256,
        values={
            key: (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in values.items()
        },
        created_by=user,
    )
    document.full_clean(exclude=["number", "file_path", "file_sha256"])
    document.save()

    # P0 — le document est rendu SOUS L'IDENTITÉ de l'académie de l'élève :
    # son cachet, sa signature, jamais ceux d'une autre.
    content = render_document(
        template.id, values, branding=get_branding(academy), preview=preview,
    )
    document.store_pdf(content)
    document.save(update_fields=["file_path", "file_sha256", "file_size", "updated_at"])

    DocumentEvent.objects.create(
        document=document, action="created", to_status=document.status,
        performed_by=user,
        detail=f"Gabarit {template.id} v{template.version}"
               + (" - aperçu non calibré" if preview else ""),
    )
    return document


def issue_document(document, user=None):
    """
    Émet un document : lui attribue son numéro et regénère le PDF.

    Le PDF est refait parce que le numéro en fait partie. Le tamponner
    après coup sur le fichier du brouillon donnerait deux fichiers dont un
    seul porte le numéro — et l'empreinte conservée ne vaudrait plus rien.
    """
    if document.academy_template_id:
        return _issue_uploaded(document, user)

    template = load_template(document.template_id)
    blockers = template.issuance_blockers()
    if blockers:
        raise ValidationError(
            "Émission impossible :\n  - " + "\n  - ".join(blockers)
        )

    previous_status = document.status
    if document.status == GeneratedDocument.DRAFT:
        document.transition_to(GeneratedDocument.VALIDATED, user=user)

    number = document.number or None
    if number is None:
        from apps.documents.models import DocumentNumberSequence

        number = DocumentNumberSequence.next_number(
            document.academy, document.template_id,
        )
        document.number = number

    values = dict(document.values)
    values["document_number"] = number
    content = render_document(
        document.template_id, values,
        branding=get_branding(document.academy), preview=False,
    )
    document.store_pdf(content)
    document.values = values
    document.save(update_fields=[
        "number", "values", "file_path", "file_sha256", "file_size", "updated_at",
    ])

    document.transition_to(GeneratedDocument.ISSUED, user=user)
    DocumentEvent.objects.create(
        document=document, action="issued", from_status=previous_status,
        to_status=document.status, performed_by=user,
        detail=f"Numéro {document.number} - empreinte {document.file_sha256[:16]}…",
    )
    return document


def replace_document(document, user=None, reason="", extra_values=None):
    """
    Remplace un document émis par un nouveau.

    L'ancien n'est ni modifié ni supprimé : il passe à « remplacé ». Une
    copie imprimée en circule peut-être, et l'historique doit permettre de
    dire ce qu'elle est devenue.
    """
    if document.status != GeneratedDocument.ISSUED:
        raise ValidationError(
            "Seul un document émis peut être remplacé. Un brouillon se "
            "corrige directement."
        )

    if document.academy_template_id:
        # Le remplaçant est produit sur la version ACTIVE aujourd'hui : c'est
        # elle que l'académie a mise en service. L'ancien document garde la
        # sienne, et son fichier.
        replacement = create_for_kind(
            kind=document.academy_template.kind, student=document.student, user=user,
            school_year=document.school_year,
            extra_values=extra_values or {
                key: document.values.get(key)
                for key in ("award_date", "certificate_purpose") if document.values.get(key)
            },
        )
    else:
        replacement = create_document(
            template_id=document.template_id, student=document.student, user=user,
            school_year=document.school_year, extra_values=extra_values,
        )
    replacement.replaces = document
    replacement.save(update_fields=["replaces"])
    issue_document(replacement, user=user)

    document.transition_to(GeneratedDocument.REPLACED, user=user)
    DocumentEvent.objects.create(
        document=document, action="replaced", to_status=document.status,
        performed_by=user,
        detail=f"Remplacé par {replacement.number}. {reason}".strip(),
    )
    return replacement


# ── Gabarits téléversés par l'académie ────────────────────────────────

def prepare_uploaded(template, student, *, school_year=None, extra_values=None):
    """
    Données, manques et motifs de refus pour cet élève sur cette version.

    Partagé par la vérification, l'aperçu, la production et la délivrance :
    les quatre disent la même chose parce qu'ils calculent la même chose.
    """
    from apps.documents import academy_templates as uploads

    if student.school_id is None or student.school_id != template.academy_id:
        raise ValidationError(
            "Cet élève n'appartient pas à l'académie de ce gabarit : un document ne "
            "franchit jamais la frontière entre deux académies."
        )
    values, missing, warnings, year, facts = uploads.build_values(
        template, student, school_year=school_year, extra=extra_values,
    )
    blockers = uploads.eligibility_blockers(template, student, year, facts)
    return {"values": values, "missing": missing, "warnings": warnings,
            "blockers": blockers, "year": year}


def create_for_kind(*, kind, student, user=None, school_year=None, extra_values=None):
    """
    Produit un brouillon du type demandé avec LE gabarit de l'académie de
    l'élève (règle unique : `academy_templates.resolve_template`).
    """
    from apps.documents import academy_templates as uploads

    if student.school is None:
        raise ValidationError("Cet élève n'est rattaché à aucune académie.")
    source, template = uploads.resolve_template(student.school, kind)
    if source is None:
        raise ValidationError(
            f"Aucun gabarit de {dict(uploads.AcademyDocumentTemplate.KIND_CHOICES)[kind].lower()} "
            f"actif pour « {student.school.name} ». Téléversez-le et activez-le dans "
            f"« Gabarits des documents »."
        )
    if source == "builtin":
        return create_document(template_id=template.id, student=student, user=user,
                               school_year=school_year, extra_values=extra_values)
    return create_from_academy_template(
        template=template, student=student, user=user, school_year=school_year,
        extra_values=extra_values,
    )


def create_from_academy_template(*, template, student, user=None, school_year=None,
                                 extra_values=None):
    from apps.documents import academy_templates as uploads
    from apps.documents.models import AcademyDocumentTemplate

    if template.status != AcademyDocumentTemplate.ACTIVE:
        raise ValidationError("Ce gabarit n'est pas la version active de l'académie.")
    prepared = prepare_uploaded(template, student, school_year=school_year,
                                extra_values=extra_values)
    if prepared["missing"]:
        raise ValidationError(
            "Données obligatoires manquantes : " + ", ".join(prepared["missing"])
            + ". Complétez la fiche de l'élève ou la saisie avant de produire."
        )
    if prepared["blockers"]:
        raise ValidationError("Document non délivrable : " + " ".join(prepared["blockers"]))

    values = prepared["values"]
    # Rendu AVANT l'enregistrement : un document dont le rendu échoue
    # n'existe pas, plutôt que d'exister sans fichier.
    content = uploads.render(template, values)
    document = GeneratedDocument(
        academy=student.school, student=student, school_year=prepared["year"],
        template_id=template.template_id, template_version=template.version,
        template_fingerprint=template.fingerprint(),
        background_sha256=template.file_sha256, academy_template=template,
        values=values, created_by=user,
    )
    document.full_clean(exclude=["number", "file_path", "file_sha256"])
    document.save()
    document.store_pdf(content)
    document.save(update_fields=["file_path", "file_sha256", "file_size", "updated_at"])
    DocumentEvent.objects.create(
        document=document, action="created", to_status=document.status,
        performed_by=user,
        detail=f"Gabarit téléversé {template.get_kind_display()} v{template.version} "
               f"(empreinte {template.file_sha256[:16]}…)",
    )
    return document


def _issue_uploaded(document, user=None):
    """
    Délivrance sur la version qui a produit le brouillon — à condition
    qu'elle soit toujours en service et que la règle soit toujours remplie.
    """
    from apps.documents import academy_templates as uploads
    from apps.documents.models import AcademyDocumentTemplate, DocumentNumberSequence

    template = document.academy_template
    if template.status != AcademyDocumentTemplate.ACTIVE:
        raise ValidationError(
            f"La version {template.version} du gabarit n'est plus en service "
            f"({template.get_status_display().lower()}). Produisez un nouveau brouillon "
            f"avec la version active."
        )
    prepared = prepare_uploaded(template, document.student,
                                school_year=document.school_year,
                                extra_values=document.values)
    if prepared["blockers"]:
        raise ValidationError("Délivrance refusée : " + " ".join(prepared["blockers"]))

    previous_status = document.status
    if document.status == GeneratedDocument.DRAFT:
        document.transition_to(GeneratedDocument.VALIDATED, user=user)
    number = document.number or DocumentNumberSequence.next_number(
        document.academy, template.sequence_key,
    )
    document.number = number
    values = dict(document.values)
    values["document_number"] = number
    content = uploads.render(template, values)
    document.store_pdf(content)
    document.values = values
    document.save(update_fields=[
        "number", "values", "file_path", "file_sha256", "file_size", "updated_at",
    ])
    document.transition_to(GeneratedDocument.ISSUED, user=user)
    DocumentEvent.objects.create(
        document=document, action="issued", from_status=previous_status,
        to_status=document.status, performed_by=user,
        detail=f"Numéro {document.number} - gabarit v{template.version} - "
               f"empreinte {document.file_sha256[:16]}…",
    )
    return document
