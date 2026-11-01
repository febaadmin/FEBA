"""
Charge un échéancier (tarifs + tranches) depuis un fichier JSON.

    python manage.py load_fee_plan apps/payments/fee_plans/feba_2026_2027.json
    python manage.py load_fee_plan <fichier> --apply            # écrit
    python manage.py load_fee_plan <fichier> --apply --update   # remplace des tarifs existants

SIMULATION PAR DÉFAUT : sans `--apply`, rien n'est écrit ; la commande dit
ce qu'elle ferait, quels niveaux elle a reconnus et lesquels restent sans
tarif. Un tarif déjà présent n'est jamais modifié sans `--update`.

Le fichier porte les montants et les dates — rien n'est codé ici. Les
points que la source ne précise pas sont listés dans « a_confirmer » et
réaffichés à chaque exécution.
"""
import calendar
import json
import unicodedata
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(text.lower().replace("&", " ").split())


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def monthly_installments(spec):
    y1, m1 = map(int, spec["from"].split("-"))
    y2, m2 = map(int, spec["to"].split("-"))
    rows, y, m = [], y1, m1
    labels = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
              "septembre", "octobre", "novembre", "décembre"]
    while (y, m) <= (y2, m2):
        due = month_end(y, m) if spec.get("due_day", "last") == "last" else date(y, m, int(spec["due_day"]))
        rows.append({"label": f"{labels[m - 1].capitalize()} {y}", "due_date": due.isoformat(),
                     "amount": spec["amount"]})
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return rows


class Command(BaseCommand):
    help = "Charge un échéancier de frais depuis un fichier JSON (simulation par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--apply", action="store_true", help="Écrire réellement en base.")
        parser.add_argument("--update", action="store_true",
                            help="Remplacer montants et tranches des tarifs déjà existants.")

    def handle(self, path, apply=False, update=False, **options):
        from apps.core.currency import get_currency
        from apps.payments.models import FeeInstallment, FeeSchedule
        from apps.schools.models import Level, School, SchoolYear

        try:
            with open(path, encoding="utf-8") as handle:
                plan = json.load(handle)
        except (OSError, ValueError) as exc:
            raise CommandError(f"Fichier illisible : {exc}")

        academy = School.objects.filter(code=plan["academy_code"]).first()
        if academy is None:
            raise CommandError(f"Académie {plan['academy_code']} introuvable.")
        if academy.currency_code != plan.get("currency", academy.currency_code):
            raise CommandError(
                f"Devise du fichier ({plan['currency']}) ≠ devise de l'académie ({academy.currency_code})."
            )
        year = SchoolYear.objects.filter(school=academy, name=plan["school_year"]).first()
        if year is None:
            raise CommandError(f"Année {plan['school_year']} introuvable pour {academy.code}.")

        currency = get_currency(academy.currency_code)
        levels = {norm(level.name): level for level in Level.objects.filter(school=academy)}
        matched_levels = set()
        actions = []

        for spec in plan["fees"]:
            rows = spec.get("installments") or monthly_installments(spec["monthly"])
            if spec.get("mode", "split") == "split" and sum(r["amount"] for r in rows) != spec["amount"]:
                raise CommandError(f"« {spec['label']} » : la somme des tranches ≠ montant total.")
            targets = [None]
            if spec.get("levels"):
                targets = [levels[norm(n)] for n in spec["levels"] if norm(n) in levels]
                matched_levels.update(level.pk for level in targets)
                if not targets:
                    self.stdout.write(self.style.WARNING(
                        f"  ! « {spec['label']} » : aucun niveau reconnu parmi {spec['levels']} - ignoré."
                    ))
                    continue
            for level in targets:
                actions.append((spec, level, rows))

        self.stdout.write(f"Académie : {academy.name} - année {year.name} - devise {academy.currency_code}")
        for spec, level, rows in actions:
            existing = FeeSchedule.objects.filter(
                academy=academy, payment_type=spec["payment_type"], school_year=year, level=level,
            ).first()
            verb = "créer" if existing is None else ("remplacer" if update else "ignorer (existe déjà)")
            self.stdout.write(
                f"  · {verb} : {spec['label']} [{level.name if level else 'tous niveaux'}] "
                f"{len(rows)} échéance(s), total {spec['amount']}"
            )
        unmatched = [lv.name for lv in Level.objects.filter(school=academy) if lv.pk not in matched_levels]
        if unmatched:
            self.stdout.write(self.style.WARNING(
                "  Niveaux sans tarif de scolarité dans ce fichier : " + ", ".join(unmatched)
            ))
        for note in plan.get("a_confirmer", []):
            self.stdout.write(self.style.WARNING(f"  À CONFIRMER : {note}"))

        if not apply:
            self.stdout.write(self.style.NOTICE("Simulation : rien n'a été écrit. Relancez avec --apply."))
            return

        created = replaced = 0
        with transaction.atomic():
            for spec, level, rows in actions:
                fee = FeeSchedule.objects.filter(
                    academy=academy, payment_type=spec["payment_type"], school_year=year, level=level,
                ).first()
                if fee is not None and not update:
                    continue
                if fee is None:
                    fee = FeeSchedule(academy=academy, payment_type=spec["payment_type"],
                                      school_year=year, level=level)
                    created += 1
                else:
                    replaced += 1
                fee.label = spec["label"][:120]
                fee.amount_minor = currency.to_minor(spec["amount"])
                fee.is_mandatory = spec.get("mandatory", True)
                fee.installment_mode = spec.get("mode", "split")
                fee.is_active = True
                fee.save()
                fee.installments.all().delete()
                for order, row in enumerate(rows):
                    FeeInstallment.objects.create(
                        fee_schedule=fee, label=row["label"], due_date=date.fromisoformat(row["due_date"]),
                        amount_minor=currency.to_minor(row["amount"]), order=order,
                    )
        self.stdout.write(self.style.SUCCESS(f"{created} tarif(s) créé(s), {replaced} remplacé(s)."))
