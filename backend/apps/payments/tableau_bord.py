"""
Indicateurs financiers du tableau de bord super administrateur.

Règles (une seule source de vérité par notion, aucune double comptabilisation) :

- **Encaissé** : paiements confirmés et non supprimés (`Payment`), à leur date
  de paiement, MOINS les remboursements des transactions carte qui les ont
  produits. Une transaction carte réussie crée elle-même son `Payment` : elle
  n'est jamais additionnée une seconde fois.
- **Remboursé** : `PaymentTransaction.amount_refunded_minor` des paiements
  encaissés de la période (déjà déduit de l'encaissé, affiché à part).
- **Annulé** : paiements annulés (`is_confirmed=False`), non supprimés.
- **En attente** / **échoué** : transactions carte ouvertes / échouées,
  annulées ou expirées, créées dans la période (aucun `Payment` n'existe).
- **Attendu**, **restant à payer**, **taux de recouvrement** : échéances
  calculées par `reminders.compute_dues` (tarifs, échéancier, réductions,
  exonérations, imputation des paiements), pour les échéances dont la date
  tombe dans la période. Sans échéancier configuré, ces valeurs sont `None`
  (« non calculable ») et jamais 0.

Les montants restent dans leur devise : les académies en XOF et en USD ne sont
jamais additionnées. Tout est calculé en base (agrégats SQL) sauf les
échéances, déjà calculées par élève par le module des relances.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

PERIODES = ("7j", "30j", "3m", "6m", "12m", "annee", "perso")
MAX_JOURS_PERSO = 3 * 366


class PeriodeInvalide(ValueError):
    pass


def _mois_avant(jour, n):
    annee, mois = jour.year, jour.month - n
    while mois <= 0:
        mois += 12
        annee -= 1
    return date(annee, mois, 1)


def bornes(periode, aujourd_hui, academies, du=None, au=None):
    """(début, fin) inclus, d'après le choix de période."""
    if periode not in PERIODES:
        raise PeriodeInvalide("Période inconnue.")
    if periode == "7j":
        return aujourd_hui - timedelta(days=6), aujourd_hui
    if periode == "30j":
        return aujourd_hui - timedelta(days=29), aujourd_hui
    if periode in ("3m", "6m", "12m"):
        return _mois_avant(aujourd_hui, int(periode[:-1]) - 1), aujourd_hui
    if periode == "annee":
        from apps.schools.models import SchoolYear
        annees = SchoolYear.objects.filter(school__in=academies, is_current=True)
        if not annees:
            raise PeriodeInvalide("Aucune année scolaire active pour cette sélection.")
        return min(a.start_date for a in annees), max(a.end_date for a in annees)
    if not du or not au:
        raise PeriodeInvalide("Indiquez les deux dates de la période personnalisée.")
    if du > au:
        raise PeriodeInvalide("La date de début doit précéder la date de fin.")
    if (au - du).days > MAX_JOURS_PERSO:
        raise PeriodeInvalide("Période personnalisée limitée à trois ans.")
    return du, au


def _cases(debut, fin, par_jour):
    """Toutes les dates de case de la période (cases vides comprises)."""
    cases = []
    if par_jour:
        j = debut
        while j <= fin:
            cases.append(j)
            j += timedelta(days=1)
    else:
        j = date(debut.year, debut.month, 1)
        while j <= fin:
            cases.append(j)
            j = date(j.year + (j.month == 12), j.month % 12 + 1, 1)
    return cases


def _case(jour, par_jour):
    return jour if par_jour else date(jour.year, jour.month, 1)


def calculer(academies, periode="12m", du=None, au=None, aujourd_hui=None):
    from apps.payments.models import Payment
    from apps.payments.reminders import compute_dues
    from apps.payments.transaction_models import PaymentTransaction

    academies = list(academies)
    aujourd_hui = aujourd_hui or timezone.localdate()
    debut, fin = bornes(periode, aujourd_hui, academies, du, au)
    par_jour = (fin - debut).days <= 31
    cases = _cases(debut, fin, par_jour)

    devises = defaultdict(lambda: {
        "academies": [], "encaisse_brut": 0, "rembourse": 0, "nb_paiements": 0,
        "annule": 0, "nb_annules": 0, "en_attente": 0, "nb_en_attente": 0,
        "echoue": 0, "nb_echoues": 0,
        "attendu": 0, "attendu_echu": 0, "paye_echu": 0, "restant": 0, "echeancier": False,
        "serie": {c: {"encaisse": 0, "attendu": 0} for c in cases},
    })
    par_academie = []

    for academie in academies:
        code = academie.currency_code
        d = devises[code]
        d["academies"].append({"id": academie.pk, "nom": academie.name})
        payes = Payment.objects.filter(student__school=academie, is_deleted=False,
                                       payment_date__gte=debut, payment_date__lte=fin)
        confirmes = payes.filter(is_confirmed=True)

        # Encaissé brut, par case : un seul agrégat SQL.
        if par_jour:
            lignes = confirmes.values("payment_date").annotate(t=Sum("amount_minor"), n=Count("id"))
            brut = [(l["payment_date"], l["t"] or 0, l["n"]) for l in lignes]
        else:
            lignes = (confirmes.annotate(m=TruncMonth("payment_date")).values("m")
                      .annotate(t=Sum("amount_minor"), n=Count("id")))
            brut = [(l["m"], l["t"] or 0, l["n"]) for l in lignes]
        # Remboursements des transactions carte qui ont produit ces paiements.
        remb = (PaymentTransaction.objects.filter(payment__in=confirmes, amount_refunded_minor__gt=0)
                .values_list("payment__payment_date", "amount_refunded_minor"))

        total_brut = total_remb = nb = 0
        for jour, t, n in brut:
            jour = jour.date() if isinstance(jour, datetime) else jour
            d["serie"][_case(jour, par_jour)]["encaisse"] += t
            total_brut += t
            nb += n
        for jour, r in remb:
            d["serie"][_case(jour, par_jour)]["encaisse"] -= r
            total_remb += r

        annules = payes.filter(is_confirmed=False).aggregate(t=Sum("amount_minor"), n=Count("id"))
        transactions = PaymentTransaction.objects.filter(
            academy=academie, created_at__date__gte=debut, created_at__date__lte=fin)
        attente = transactions.filter(status__in=PaymentTransaction.OPEN_STATUSES).aggregate(
            t=Sum("amount_minor"), n=Count("id"))
        echecs = transactions.filter(status__in=[PaymentTransaction.FAILED, PaymentTransaction.CANCELLED,
                                                 PaymentTransaction.EXPIRED]).aggregate(
            t=Sum("amount_minor"), n=Count("id"))

        # Échéances (module des relances) : attendu, payé, restant.
        echeances = [i for i in compute_dues(academie, on_date=aujourd_hui).items
                     if debut <= i.installment.due_date <= fin]
        attendu = sum(i.net for i in echeances)
        echues = [i for i in echeances if i.installment.due_date <= aujourd_hui]
        attendu_echu = sum(i.net for i in echues)
        paye_echu = sum(min(i.paid, i.net) for i in echues)
        restant = sum(i.outstanding for i in echues)
        for i in echeances:
            d["serie"][_case(i.installment.due_date, par_jour)]["attendu"] += i.net
        # Calculable dès que l'académie a un tarif actif avec échéances : sinon la valeur
        # est inconnue (« non calculable »). S'il y en a, une période sans échéance vaut 0.
        from apps.payments.models import FeeSchedule
        a_tarifs = FeeSchedule.objects.filter(academy=academie, is_active=True, installments__isnull=False).exists()
        d["echeancier"] = d["echeancier"] or a_tarifs

        for cle, valeur in (("encaisse_brut", total_brut), ("rembourse", total_remb), ("nb_paiements", nb),
                            ("annule", annules["t"] or 0), ("nb_annules", annules["n"]),
                            ("en_attente", attente["t"] or 0), ("nb_en_attente", attente["n"]),
                            ("echoue", echecs["t"] or 0), ("nb_echoues", echecs["n"]),
                            ("attendu", attendu), ("attendu_echu", attendu_echu),
                            ("paye_echu", paye_echu), ("restant", restant)):
            d[cle] += valeur
        par_academie.append({
            "id": academie.pk, "nom": academie.name, "devise": code,
            "encaisse_minor": total_brut - total_remb, "nb_paiements": nb,
            "attendu_minor": attendu if a_tarifs else None,
            "restant_minor": restant if a_tarifs else None,
        })

    resultat = []
    for code, d in sorted(devises.items()):
        echeancier = d["echeancier"]
        resultat.append({
            "devise": code,
            "academies": d["academies"],
            "echeancier_configure": echeancier,
            "indicateurs": {
                "encaisse_minor": d["encaisse_brut"] - d["rembourse"],
                "rembourse_minor": d["rembourse"],
                "nb_paiements": d["nb_paiements"],
                "annule_minor": d["annule"], "nb_annules": d["nb_annules"],
                "en_attente_minor": d["en_attente"], "nb_en_attente": d["nb_en_attente"],
                "echoue_minor": d["echoue"], "nb_echoues": d["nb_echoues"],
                "attendu_minor": d["attendu"] if echeancier else None,
                "restant_minor": d["restant"] if echeancier else None,
                "taux_recouvrement": (round(100 * d["paye_echu"] / d["attendu_echu"], 1)
                                      if echeancier and d["attendu_echu"] else None),
            },
            "serie": [{"date": c.isoformat(), "encaisse_minor": v["encaisse"],
                       "attendu_minor": v["attendu"] if echeancier else None}
                      for c, v in sorted(d["serie"].items())],
        })
    return {
        "periode": {"code": periode, "du": debut.isoformat(), "au": fin.isoformat(),
                    "granularite": "jour" if par_jour else "mois"},
        "devises": resultat,
        "par_academie": par_academie,
    }


# ── Vue ───────────────────────────────────────────────────────────────

from rest_framework.permissions import IsAuthenticated  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

from apps.accounts.permissions import IsSuperAdmin  # noqa: E402


class TableauBordPaiementsView(APIView):
    """GET /api/payments/tableau-de-bord/?periode=12m[&du=AAAA-MM-JJ&au=AAAA-MM-JJ]

    Super administrateur seulement. L'académie suit le sélecteur (en-tête de
    portée) : une académie précise, ou toutes en mode « Toutes les Académies ».
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from django.utils.dateparse import parse_date
        from apps.core.tenancy import get_request_school
        from apps.schools.models import School

        ecole = get_request_school(request)
        academies = [ecole] if ecole is not None else list(School.objects.order_by("name"))
        p = request.query_params
        try:
            du = parse_date(p["du"]) if p.get("du") else None
            au = parse_date(p["au"]) if p.get("au") else None
        except ValueError:
            du = au = None
        if (p.get("du") and du is None) or (p.get("au") and au is None):
            return Response({"detail": "Date invalide : format attendu AAAA-MM-JJ."}, status=400)
        try:
            return Response(calculer(academies, p.get("periode", "12m"), du, au))
        except PeriodeInvalide as exc:
            return Response({"detail": str(exc)}, status=400)
