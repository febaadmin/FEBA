"""
Installe le fond verrouillé d'un gabarit, après vérification.

POURQUOI UNE COMMANDE PLUTÔT QU'UNE COPIE MANUELLE
--------------------------------------------------
Un `cp` réussit toujours. Il réussit avec le bon fichier, avec un
ré-export, avec une version recadrée de trois pixels, avec le fichier du
mauvais document. Aucune de ces erreurs ne produit de message : elles se
découvrent à l'impression du premier diplôme, ou jamais.

Cette commande refuse tout ce qui n'est pas exactement le fichier décrit
par le gabarit — dimensions ET empreinte SHA-256.
"""
import os
import shutil

from django.core.management.base import BaseCommand, CommandError

from apps.documents.templates_registry import (
    ORIGINALS_DIR, TemplateError, available_templates, load_template, sha256_of,
)


class Command(BaseCommand):
    help = "Installe le fond original d'un gabarit après vérification d'empreinte."

    def register_variant(self, template, digest, image_format, options):
        """
        Inscrit la variante dans le gabarit, avec sa provenance.

        Écrit dans le JSON, et non dans un fichier annexe : le gabarit est
        ce qu'on lit pour savoir sur quoi un document a été produit.
        """
        import datetime
        import json

        from apps.documents.templates_registry import BackgroundVariant

        entry = {
            "sha256": digest,
            "source": f"fichier {image_format} fourni à l'installation",
            "reason": options["reason"].strip(),
            "accepted_by": options["accepted_by"].strip() or "non précisé",
            "accepted_at": datetime.date.today().isoformat(),
            "lossy": image_format not in ("PNG", "TIFF", "BMP"),
        }
        with open(template.path, encoding="utf-8") as handle:
            data = json.load(handle)
        data["background"].setdefault("accepted_variants", []).append(entry)
        with open(template.path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return BackgroundVariant(entry)

    def add_arguments(self, parser):
        parser.add_argument("--template", required=True,
                            help=f"Identifiant du gabarit ({', '.join(available_templates())}).")
        parser.add_argument("--file", required=True,
                            help="Chemin du fichier PNG original.")
        parser.add_argument("--force", action="store_true",
                            help="Remplace un fond déjà installé (conforme ou non).")
        parser.add_argument(
            "--accept-variant", action="store_true",
            help="Accepte un fichier dont l'empreinte diffère de l'original "
                 "(canal qui ré-encode). Exige --reason.",
        )
        parser.add_argument("--reason", default="",
                            help="Motif d'acceptation de la variante — obligatoire.")
        parser.add_argument("--accepted-by", default="",
                            help="Qui accepte la variante et en répond.")

    def handle(self, *args, **options):
        try:
            template = load_template(options["template"], use_cache=False)
        except TemplateError as exc:
            raise CommandError(exc.messages[0] if exc.messages else str(exc))

        source = options["file"]
        if not os.path.exists(source):
            raise CommandError(f"Fichier introuvable : {source}")

        # ── Dimensions ────────────────────────────────────────────────
        try:
            from PIL import Image

            with Image.open(source) as image:
                width, height = image.size
                image_format = image.format
        except Exception as exc:
            raise CommandError(f"Ce fichier n'est pas une image lisible : {exc}")

        expected = (template.background_width_px, template.background_height_px)
        if (width, height) != expected:
            raise CommandError(
                f"Dimensions incorrectes : {width}×{height} px, attendu "
                f"{expected[0]}×{expected[1]} px.\n"
                f"Un recadrage de quelques pixels déplace tous les éléments du "
                f"document ; le calibrage millimétré serait faux sans que rien "
                f"ne le signale."
            )

        # ── Empreinte ─────────────────────────────────────────────────
        digest = sha256_of(source)
        variant = None
        if digest != template.background_sha256:
            known = template.variant_for(digest)
            if known is not None:
                variant = known
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ Variante déjà acceptée : {known.source}"
                ))
            elif not options["accept_variant"]:
                raise CommandError(
                    f"Empreinte incorrecte.\n"
                    f"  Fichier fourni : {digest}\n"
                    f"  Attendue       : {template.background_sha256}\n"
                    f"\n"
                    f"Les dimensions correspondent, mais ce n'est pas le même "
                    f"fichier. Un ré-export du même visuel change la "
                    f"compression et peut décaler les ornements de un ou deux "
                    f"pixels. Sur un document officiel, ce décalage ne se voit "
                    f"pas et ne se corrige jamais.\n"
                    f"\n"
                    f"Si ce fichier provient d'un canal qui ré-encode "
                    f"(messagerie, export), il peut être accepté NOMMÉMENT :\n"
                    f"  --accept-variant --reason « … » --accepted-by « … »"
                )
            else:
                if not options["reason"].strip():
                    raise CommandError(
                        "--accept-variant exige --reason. Une variante acceptée "
                        "sans motif est indistinguable d'une erreur : personne "
                        "ne saura, dans six mois, pourquoi ce fichier a été "
                        "retenu à la place de l'original."
                    )
                variant = self.register_variant(
                    template, digest, image_format, options,
                )

        destination = os.path.join(ORIGINALS_DIR, template.background_file)
        if os.path.exists(destination) and not options["force"]:
            existing = sha256_of(destination)
            if existing == digest:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Le fond « {template.background_file} » est déjà "
                    f"installé et conforme. Rien à faire."
                ))
                return
            raise CommandError(
                f"Un fond différent est déjà installé ({existing}). "
                f"Utilisez --force pour le remplacer."
            )

        os.makedirs(ORIGINALS_DIR, exist_ok=True)
        shutil.copy2(source, destination)

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✓ Fond installé : {destination}"
        ))
        if variant is None:
            self.stdout.write(
                f"    Format {image_format}, {width}×{height} px, "
                f"empreinte conforme à l'original.\n"
            )
        else:
            self.stdout.write(self.style.WARNING(
                f"    Format {image_format}, {width}×{height} px.\n"
                f"    ⚠ VARIANTE, pas l'original.\n"
                f"      empreinte : {digest}\n"
                f"      provenance : {variant.source}\n"
                f"      motif      : {variant.reason}\n"
                f"      Chaque document produit sur ce fond le mentionnera, "
                f"et le rapport\n      de fidélité aussi.\n"
            ))
        if not template.calibrated:
            self.stdout.write(self.style.WARNING(
                "  ⚠ Le gabarit n'est pas encore calibré : aucun document ne "
                "sera émis.\n"
                f"    Étape suivante : manage.py document_calibrate "
                f"--template {template.id}\n"
            ))
