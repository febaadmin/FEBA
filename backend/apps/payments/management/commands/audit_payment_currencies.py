"""
Audit des devises des opérations financières.

POURQUOI CETTE COMMANDE EXISTE
------------------------------
Avant l'introduction du champ `currency`, un paiement n'était qu'un
montant. L'interface affichait « FCFA » en dur : un encaissement de FEBA
French Heritage Academy — académie qui facture en dollars — s'affichait
donc dans la mauvaise unité. Le nombre était juste, la monnaie fausse, et
rien à l'écran ne le signalait.

Cette commande dresse l'état réel de la base AVANT toute correction, et
distingue quatre situations qui n'appellent pas le même traitement :

  1. CONFORME          la devise correspond à l'académie ;
  2. AFFICHAGE         la valeur est bonne, seul le code était absent ou
                       incorrect — corrigeable sans risque ;
  3. AMBIGU            le montant lui-même pourrait avoir été saisi dans
                       une autre monnaie — NON corrigeable automatiquement ;
  4. ORPHELIN          aucune académie rattachée — à traiter à la main.

Le cas 3 est le seul qui compte vraiment. Convertir un montant historique
« au cas où » reviendrait à réécrire une somme réellement encaissée. La
commande refuse de le faire et se contente de le signaler.

Usage :
    python manage.py audit_payment_currencies
    python manage.py audit_payment_currencies --format=csv > audit.csv
"""
import csv
import sys

from django.core.management.base import BaseCommand

from apps.core.currency import DEFAULT_CURRENCY, Money, get_currency

CONFORME = "conforme"
AFFICHAGE = "affichage"
AMBIGU = "ambigu"
ORPHELIN = "orphelin"

LABELS = {
    CONFORME: "Conforme",
    AFFICHAGE: "Code de devise à corriger (valeur correcte)",
    AMBIGU: "Montant potentiellement saisi dans une autre devise",
    ORPHELIN: "Aucune académie rattachée",
}


def classify(payment):
    """
    Situation d'un paiement vis-à-vis de la devise attendue.

    Un paiement est jugé AMBIGU lorsque sa devise enregistrée diffère de
    celle de son académie ET que la conversion changerait la valeur — donc
    quand les deux monnaies n'ont pas le même nombre de décimales. C'est le
    seul cas où l'on ne peut pas trancher sans connaître l'intention de la
    personne qui a saisi le montant.
    """
    academy = getattr(getattr(payment, "student", None), "school", None)
    if academy is None:
        return ORPHELIN, None

    expected = (getattr(academy, "currency_code", None) or DEFAULT_CURRENCY).upper()
    actual = (payment.currency or "").upper()

    if actual == expected:
        return CONFORME, expected
    if not actual:
        # Jamais renseignée : il n'y a rien à contredire, seulement à poser.
        return AFFICHAGE, expected

    try:
        same_scale = get_currency(actual).decimal_places == get_currency(expected).decimal_places
    except Exception:
        return AMBIGU, expected
    return (AFFICHAGE if same_scale else AMBIGU), expected


def collect():
    """Toutes les anomalies, groupées par situation."""
    from apps.payments.models import Payment

    buckets = {CONFORME: [], AFFICHAGE: [], AMBIGU: [], ORPHELIN: []}
    payments = Payment.objects.select_related("student__school").order_by("id")
    for payment in payments.iterator():
        situation, expected = classify(payment)
        buckets[situation].append((payment, expected))
    return buckets


class Command(BaseCommand):
    help = "Inventorie les devises des paiements et signale les anomalies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format", choices=["table", "csv"], default="table",
            help="table (lisible) ou csv (exploitable dans un tableur).",
        )

    def handle(self, *args, **options):
        buckets = collect()
        total = sum(len(rows) for rows in buckets.values())

        if options["format"] == "csv":
            self._write_csv(buckets)
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Audit des devises — {total} paiement(s)"
        ))

        for situation in (ORPHELIN, AMBIGU, AFFICHAGE, CONFORME):
            rows = buckets[situation]
            if not rows:
                continue
            style = {
                ORPHELIN: self.style.ERROR,
                AMBIGU: self.style.WARNING,
                AFFICHAGE: self.style.WARNING,
                CONFORME: self.style.SUCCESS,
            }[situation]
            self.stdout.write("")
            self.stdout.write(style(f"{LABELS[situation]} : {len(rows)}"))
            if situation == CONFORME:
                continue
            self.stdout.write(
                "  ID    Académie     Montant            Devise actuelle  "
                "Devise attendue  Correction automatique"
            )
            for payment, expected in rows[:50]:
                academy = getattr(getattr(payment, "student", None), "school", None)
                money = Money(payment.amount_minor, payment.currency or DEFAULT_CURRENCY)
                auto = "oui" if situation == AFFICHAGE else "NON — revue manuelle"
                self.stdout.write(
                    f"  {payment.pk:<5} {(academy.code if academy else '—'):<12} "
                    f"{money.formatted():<18} {(payment.currency or '—'):<16} "
                    f"{(expected or '—'):<16} {auto}"
                )
            if len(rows) > 50:
                self.stdout.write(f"  … et {len(rows) - 50} de plus (utilisez --format=csv)")

        self.stdout.write("")
        self.stdout.write("Totaux par académie et par devise :")
        for line in self._totals():
            self.stdout.write(f"  {line}")

        self.stdout.write("")
        if buckets[AMBIGU] or buckets[ORPHELIN]:
            self.stdout.write(self.style.WARNING(
                f"{len(buckets[AMBIGU])} cas ambigu(s) et {len(buckets[ORPHELIN])} orphelin(s) "
                "nécessitent une revue humaine : aucune conversion automatique ne sera "
                "appliquée à un montant réellement encaissé."
            ))
        if buckets[AFFICHAGE]:
            self.stdout.write(
                f"{len(buckets[AFFICHAGE])} correction(s) sûre(s) applicable(s) : "
                "python manage.py repair_payment_currencies --dry-run"
            )
        if not (buckets[AMBIGU] or buckets[ORPHELIN] or buckets[AFFICHAGE]):
            self.stdout.write(self.style.SUCCESS("Aucune anomalie de devise."))

    def _totals(self):
        from apps.payments.models import Payment
        from apps.schools.models import School
        from apps.core.currency import format_totals, totals_by_currency

        lines = []
        for school in School.objects.order_by("code"):
            rows = list(Payment.objects.filter(student__school=school))
            if not rows:
                lines.append(f"{school.code:<12} aucun paiement")
                continue
            totals = totals_by_currency(rows)
            lines.append(f"{school.code:<12} " + " · ".join(format_totals(totals)))
        return lines

    def _write_csv(self, buckets):
        writer = csv.writer(sys.stdout)
        writer.writerow([
            "id", "academie", "montant_unite_mineure", "montant_affiche",
            "devise_actuelle", "devise_attendue", "situation", "correction_automatique",
        ])
        for situation, rows in buckets.items():
            for payment, expected in rows:
                academy = getattr(getattr(payment, "student", None), "school", None)
                money = Money(payment.amount_minor, payment.currency or DEFAULT_CURRENCY)
                writer.writerow([
                    payment.pk,
                    academy.code if academy else "",
                    payment.amount_minor,
                    money.formatted(),
                    payment.currency or "",
                    expected or "",
                    LABELS[situation],
                    "oui" if situation == AFFICHAGE else "non",
                ])
