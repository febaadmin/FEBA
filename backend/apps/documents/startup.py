"""
apps/documents/startup.py — Contrôle d'aptitude des documents officiels.

P7 — POURQUOI CE CONTRÔLE EXISTE
--------------------------------
L'application était livrée avec son diplôme bloqué. L'écran affichait :

    « Le gabarit déclare 1 mention(s) d'exemple à neutraliser, mais le fond
      dérivé n'existe pas encore. Lancez : manage.py document_neutralize »

Demander à l'utilisateur d'une application finie de lancer une commande
d'atelier n'est pas une dégradation acceptable : c'est un défaut
d'installation déguisé en message d'aide.

Le fond neutralisé est désormais VERSIONNÉ, empreint dans le gabarit, et
vérifié ici. Le contrôle porte sur tout ce dont dépend une émission :
l'original, le dérivé et son empreinte, le calibrage, les polices, le
stockage, et la capacité réelle à produire un PDF.

Il est appelé au démarrage (voir `DocumentsConfig.ready`) et par
`manage.py documents_ready`. Au démarrage il n'interrompt jamais le
serveur : une école dont le diplôme n'est pas prêt doit pouvoir faire
l'appel et saisir des notes. Le défaut est journalisé, exposé à
l'administration, et bloque l'émission — pas le reste.
"""
import logging
import os

logger = logging.getLogger("apps")


class CheckResult:
    """Résultat d'un contrôle unitaire."""

    __slots__ = ("name", "ok", "detail")

    def __init__(self, name, ok, detail=""):
        self.name = name
        self.ok = bool(ok)
        self.detail = detail

    def __repr__(self):  # pragma: no cover - confort de débogage
        return f"<{self.name}: {'ok' if self.ok else 'ÉCHEC'} {self.detail}>"


def _check_fonts():
    from apps.documents.renderer import EMBEDDED_FONTS, FONTS_DIR

    missing = [
        filename for filename in EMBEDDED_FONTS.values()
        if not os.path.exists(os.path.join(FONTS_DIR, filename))
    ]
    if missing:
        return CheckResult(
            "polices", False,
            f"absentes : {', '.join(sorted(missing))}. Une police substituée "
            f"par le système changerait la mise en page sans prévenir.",
        )
    return CheckResult("polices", True, f"{len(EMBEDDED_FONTS)} embarquées")


def _check_storage():
    from django.conf import settings

    root = getattr(settings, "PRIVATE_MEDIA_ROOT", None) or os.path.join(
        settings.BASE_DIR, "private_media",
    )
    try:
        os.makedirs(root, exist_ok=True)
        probe = os.path.join(root, ".ecriture_test")
        with open(probe, "wb") as handle:
            handle.write(b"1")
        os.remove(probe)
    except OSError as exc:
        return CheckResult(
            "stockage privé", False,
            f"{root} n'est pas inscriptible ({exc}). Les documents produits "
            f"ne pourraient pas être conservés.",
        )
    return CheckResult("stockage privé", True, root)


def check_template(template):
    """Contrôles portant sur un gabarit : fond, dérivé, calibrage."""
    from apps.documents.templates_registry import TemplateError

    results = []

    if not template.background_installed:
        results.append(CheckResult(
            f"{template.id} · fond original", False,
            f"{template.background_file} absent de document_templates/originals/.",
        ))
    else:
        try:
            template.verify_background()
            variant = template.installed_variant
            results.append(CheckResult(
                f"{template.id} · fond original", True,
                "variante acceptée" if variant is not None else "empreinte conforme",
            ))
        except TemplateError as exc:
            results.append(CheckResult(
                f"{template.id} · fond original", False,
                exc.messages[0] if exc.messages else str(exc),
            ))

    if template.masks:
        problem = template.derived_problem()
        results.append(CheckResult(
            f"{template.id} · fond neutralisé", problem is None,
            problem or f"empreinte {template.derived_sha256[:16]}… conforme",
        ))

    results.append(CheckResult(
        f"{template.id} · calibrage", template.calibrated,
        f"tolérance {template.tolerance_mm} mm" if template.calibrated
        else "jamais confronté à l'image réelle",
    ))

    return results


def _sample_values(template):
    """Valeurs fictives couvrant tous les champs déclarés d'un gabarit."""
    import datetime

    values = {}
    for field in template.fields:
        if field.type == "date":
            values[field.name] = datetime.date(2026, 1, 1)
        elif field.name == "student_name":
            values[field.name] = "Contrôle Démarrage"
        else:
            values[field.name] = "—"
    return values


def _check_render(template):
    from apps.documents.renderer import render_document

    try:
        content = render_document(template.id, _sample_values(template))
    except Exception as exc:
        return CheckResult(f"{template.id} · rendu", False, str(exc)[:300])
    if not content.startswith(b"%PDF"):
        return CheckResult(f"{template.id} · rendu", False,
                           "la sortie n'est pas un PDF")
    return CheckResult(f"{template.id} · rendu", True,
                       f"{len(content) // 1024} Ko produits")


def run_checks(include_render=True):
    """
    Exécute tous les contrôles et renvoie la liste des résultats.

    Ne lève jamais : c'est un diagnostic, pas une barrière. La barrière est
    `issuance_blockers()`, appliquée au moment d'émettre.
    """
    from apps.documents.templates_registry import (
        TemplateError, available_templates, load_template,
    )

    results = [_check_fonts(), _check_storage()]

    for template_id in available_templates():
        try:
            template = load_template(template_id, use_cache=False)
        except TemplateError as exc:
            results.append(CheckResult(
                f"{template_id} · gabarit", False,
                exc.messages[0] if exc.messages else str(exc),
            ))
            continue

        results.extend(check_template(template))
        if include_render and template.can_issue:
            results.append(_check_render(template))

    return results


def log_startup_report():
    """
    Journalise l'aptitude des documents au démarrage.

    Volontairement NON bloquant : une école dont le diplôme n'est pas prêt
    doit pouvoir faire l'appel, saisir des notes et encaisser. Ce qui est
    interdit, c'est d'émettre un document faux — et cela, c'est
    `issuance_blockers()` qui l'empêche, au moment précis où ça compte.
    """
    try:
        results = run_checks(include_render=False)
    except Exception as exc:  # pragma: no cover - diagnostic best effort
        logger.warning("Contrôle des documents officiels impossible : %s", exc)
        return []

    failures = [r for r in results if not r.ok]
    if failures:
        logger.warning(
            "Documents officiels — %d contrôle(s) en échec : %s",
            len(failures),
            " | ".join(f"{r.name} : {r.detail}" for r in failures),
        )
    else:
        logger.info(
            "Documents officiels — %d contrôles passés, émission possible.",
            len(results),
        )
    return results
