"""
Barèmes officiels (fichiers `fee_plans/*.json`) : aperçu et import par l'administration.

Le fichier porte les montants et les dates ; les points que la source ne précise
pas sont listés dans « a_confirmer » et montrés AVANT tout import. L'import ne
crée que les tarifs absents (jamais de remplacement), dans une transaction, et
trace chaque création au journal des tarifs. Aucun tarif n'est importé sans
action explicite d'un administrateur.
"""
import json
from datetime import date
from pathlib import Path

from django.db import transaction

from .management.commands.load_fee_plan import monthly_installments, norm

DOSSIER = Path(__file__).resolve().parent / "fee_plans"


def baremes_pour(academie):
    """Barèmes disponibles pour cette académie (code et devise identiques)."""
    out = []
    for f in sorted(DOSSIER.glob("*.json")):
        try:
            plan = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if plan.get("academy_code") == academie.code and plan.get("currency", academie.currency_code) == academie.currency_code:
            out.append((f.name, plan))
    return out


def apercu(academie, nom):
    from apps.core.currency import Money, get_currency
    from apps.payments.models import FeeSchedule
    from apps.schools.models import Level, SchoolYear
    plan = dict(baremes_pour(academie)).get(nom)
    if plan is None:
        return None
    annee = SchoolYear.objects.filter(school=academie, name=plan["school_year"]).first()
    niveaux = {norm(n.name): n for n in Level.objects.filter(school=academie)}
    devise = get_currency(academie.currency_code)
    lignes, reconnus = [], set()
    for spec in plan["fees"]:
        rows = spec.get("installments") or monthly_installments(spec["monthly"])
        cibles = [None]
        if spec.get("levels"):
            cibles = [niveaux[norm(n)] for n in spec["levels"] if norm(n) in niveaux]
            reconnus.update(n.pk for n in cibles)
        for niveau in cibles:
            existe = annee is not None and FeeSchedule.objects.filter(
                academy=academie, payment_type=spec["payment_type"], school_year=annee, level=niveau).exists()
            lignes.append({
                "nature": spec["payment_type"], "libelle": spec["label"], "niveau": getattr(niveau, "name", None),
                "niveau_id": getattr(niveau, "pk", None), "montant": Money(devise.to_minor(spec["amount"]), academie.currency_code).formatted(),
                "obligatoire": spec.get("mandatory", True), "mode": spec.get("mode", "split"),
                "echeances": [{"label": r["label"], "date": r["due_date"],
                               "montant": Money(devise.to_minor(r["amount"]), academie.currency_code).formatted()} for r in rows],
                "action": "existe" if existe else "creer", "_spec": spec, "_rows": rows,
            })
    return {
        "fichier": nom, "source": plan.get("source", ""), "annee": plan["school_year"], "annee_trouvee": annee is not None,
        "a_confirmer": plan.get("a_confirmer", []), "lignes": lignes,
        "niveaux_sans_tarif": [n.name for n in Level.objects.filter(school=academie).order_by("order") if n.pk not in reconnus],
    }


@transaction.atomic
def importer(academie, nom, utilisateur):
    from apps.core.currency import get_currency
    from apps.payments.models import FeeInstallment, FeeSchedule, FeeScheduleChange
    from apps.payments.reminder_views import decrire_tarif
    from apps.schools.models import SchoolYear
    a = apercu(academie, nom)
    if a is None or not a["annee_trouvee"]:
        return None
    annee = SchoolYear.objects.get(school=academie, name=a["annee"])
    devise = get_currency(academie.currency_code)
    crees = 0
    for l in a["lignes"]:
        if l["action"] != "creer":
            continue
        spec, rows = l["_spec"], l["_rows"]
        fee = FeeSchedule(academy=academie, payment_type=spec["payment_type"], school_year=annee,
                          level_id=l["niveau_id"], label=spec["label"][:120], amount_minor=devise.to_minor(spec["amount"]),
                          is_mandatory=spec.get("mandatory", True), installment_mode=spec.get("mode", "split"), is_active=True)
        fee.save()
        for ordre, r in enumerate(rows):
            FeeInstallment.objects.create(fee_schedule=fee, label=r["label"], due_date=date.fromisoformat(r["due_date"]),
                                          amount_minor=devise.to_minor(r["amount"]), order=ordre)
        FeeScheduleChange.objects.create(
            academy=academie, fee_schedule=fee, fee_description=decrire_tarif(fee), action="creation",
            new_amount_minor=fee.amount_minor, currency=fee.currency, reason=f"Import du barème {nom}"[:255],
            changed_by=utilisateur, changed_by_email=utilisateur.email)
        crees += 1
    return crees
