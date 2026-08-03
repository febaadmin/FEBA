"""
Produit des documents d'exemple, avec des noms qui mettent le moteur à l'épreuve.

POURQUOI CINQ NOMS, ET CEUX-LÀ
------------------------------
Un diplôme se rend correctement pour « Awa Koffi ». Les erreurs se
déclarent ailleurs :

  · un nom LONG déborde de sa zone ou se fait tronquer ;
  · un nom COMPOSÉ contient un tiret qui peut servir de point de coupure ;
  · un nom ACCENTUÉ échoue si la police n'a pas les glyphes, ou si
    l'encodage se perd entre le gabarit et le PDF ;
  · une APOSTROPHE typographique (U+2019) n'est pas l'apostrophe droite,
    et certaines fontes n'ont que l'une des deux ;
  · un nom COURT révèle un centrage calculé sur la largeur de la zone
    plutôt que sur celle du texte.

Ces cinq cas ne sont pas décoratifs : chacun correspond à une manière
connue de produire un document faux qui a l'air correct.

LES DONNÉES SONT FICTIVES
-------------------------
Aucun nom d'élève réel n'apparaît dans les exemples livrés. Un document
d'exemple circule — dans une archive, un rapport, une capture — et
emporterait avec lui une donnée personnelle.
"""
import datetime
import os

from django.core.management.base import BaseCommand, CommandError

from apps.documents.renderer import RenderError, render_document, resolve_resource
from apps.schools.branding import get_branding_by_code
from apps.documents.templates_registry import (
    TemplateError, available_templates, load_template,
)

#: Noms FICTIFS, choisis pour ce qu'ils font au moteur.
SAMPLE_NAMES = [
    ("court", "Ana Ba"),
    ("long", "Marie-Christelle Adjovi Hounkpatin"),
    ("compose", "Jean-Baptiste N'Diaye-Sow"),
    ("accents", "Élisabeth Ahouéfa Gbêdjissi"),
    ("apostrophe", "N’Guessan D’Almeida"),
]


class Command(BaseCommand):
    help = "Génère des documents d'exemple couvrant les cas de nom difficiles."

    def add_arguments(self, parser):
        parser.add_argument("--template", required=True,
                            help=f"Gabarit ({', '.join(available_templates())}).")
        parser.add_argument("--output-dir", default="exemples")
        parser.add_argument("--date", default=None,
                            help="Date de délivrance (JJ/MM/AAAA). Défaut : aujourd'hui.")
        # P0 — un exemple est produit POUR une académie. Sans elle, on ne
        # saurait pas quel cachet apposer, et l'ancien moteur en choisissait
        # un au hasard des fichiers présents.
        parser.add_argument("--academy", default="FEBA",
                            help="Code interne de l'académie émettrice (FEBA, FEBA_FHA).")

    def handle(self, *args, **options):
        try:
            template = load_template(options["template"], use_cache=False)
        except TemplateError as exc:
            raise CommandError(exc.messages[0] if exc.messages else str(exc))

        blockers = template.issuance_blockers()
        if blockers:
            raise CommandError(
                "Ce gabarit ne peut pas produire de document :\n  - "
                + "\n  - ".join(blockers)
            )

        out = options["output_dir"]
        os.makedirs(out, exist_ok=True)
        issue_date = options["date"] or datetime.date.today().strftime("%d/%m/%Y")

        # Ce qui existe réellement dans les ressources du projet. Rien
        # n'est inventé : une signature absente reste absente.
        branding = get_branding_by_code(options["academy"])
        signature = resolve_resource("signature_director", branding)
        seal = resolve_resource("seal_official", branding)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nExemples — {template.label} (gabarit v{template.version})"
            f"\n  Académie émettrice : {branding.display_name} "
            f"[{branding.academy_code}]\n"
        ))
        variant = template.installed_variant
        if variant is not None:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ Fond : VARIANTE acceptée, pas le PNG d'origine.\n"
                f"    {variant.source} — {variant.reason[:110]}…\n"
            ))
        self.stdout.write(
            f"  Signature officielle : {'oui' if signature else 'AUCUNE'}\n"
            f"  Sceau officiel       : "
            f"{os.path.basename(seal) if seal else 'AUCUN'}\n"
        )

        produced, failed = [], []
        for key, name in SAMPLE_NAMES:
            values = {
                "student_name": name,
                "issue_date": issue_date,
                "document_number": f"{branding.document_prefix}-EXEMPLE-{key.upper()}",
            }
            # Champs propres à chaque gabarit, seulement s'ils existent.
            declared = {field.name for field in template.fields}
            if "diploma_label" in declared:
                values["diploma_label"] = "Diplôme de fin de cycle"
            if "achievement" in declared:
                values["achievement"] = "Mention Très Bien"
            # Un nom dactylographié n'est posé QUE faute de signature.
            if signature is None:
                if "director_name" in declared:
                    values["director_name"] = "(signature requise)"
                if "teacher_name" in declared:
                    values["teacher_name"] = "(signature requise)"
                if "signatory_name" in declared:
                    values["signatory_name"] = "(signature requise)"

            path = os.path.join(out, f"{template.id}_{key}.pdf")
            try:
                content = render_document(template.id, values,
                                          branding=branding)
            except RenderError as exc:
                failed.append((key, name, " ".join(exc.messages)))
                self.stdout.write(self.style.ERROR(f"  ✗ {key:11} {name}"))
                self.stdout.write(f"      {' '.join(exc.messages)[:150]}")
                continue

            with open(path, "wb") as handle:
                handle.write(content)
            produced.append(path)
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {key:11} {name:38} → {os.path.basename(path)} "
                f"({len(content) // 1024} Ko)"
            ))

        self.stdout.write(
            f"\n  {len(produced)} document(s) produit(s) dans {out}/\n"
        )
        if failed:
            raise CommandError(
                f"{len(failed)} cas en échec — voir ci-dessus. Un nom qui ne "
                f"tient pas n'est pas tronqué : le document n'est pas produit."
            )
