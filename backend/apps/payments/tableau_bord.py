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

Filtres (phase 5) : structure (année, cycle, niveau, classe, élève), nature,
mode, statut du paiement, statut d'échéance, solde de l'élève, tranches de
montant. Les mêmes filtres s'appliquent aux paiements, aux transactions carte
et aux échéances, pour que les indicateurs restent cohérents entre eux. La
structure d'un élève est sa classe actuelle (et l'année du paiement ou de
l'échéance pour le filtre d'année).

Les montants restent dans leur devise : les académies en XOF et en USD ne sont
jamais additionnées. Tout est calculé en base (agrégats SQL) sauf les
échéances, déjà calculées par élève par le module des relances.
"""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

PERIODES = ("7j", "30j", "3m", "6m", "12m", "annee", "civile", "perso")
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
    if periode == "civile":
        return date(aujourd_hui.year, 1, 1), date(aujourd_hui.year, 12, 31)
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



class FiltreInvalide(ValueError):
    def __init__(self, erreurs):
        super().__init__("Filtre invalide.")
        self.erreurs = erreurs


STATUTS = ("tous", "confirme", "annule", "rembourse")
SOLDES = ("tous", "du", "a_jour")


@dataclass(frozen=True)
class Filtres:
    annee: int = None
    cycle: str = None
    niveau: int = None
    classe: int = None
    eleve: int = None
    natures: tuple = ()
    modes: tuple = ()
    statut: str = "tous"
    statuts_echeance: tuple = ()
    solde: str = "tous"
    montant_min: Decimal = None
    montant_max: Decimal = None

    @property
    def structure(self):
        return any(v is not None for v in (self.annee, self.cycle, self.niveau, self.classe, self.eleve))

    def actifs(self):
        """Filtres actifs, pour l'affichage et l'export (clé : valeur brute)."""
        return {k: (list(v) if isinstance(v, tuple) else (str(v) if isinstance(v, Decimal) else v))
                for k, v in self.__dict__.items()
                if v not in (None, (), "tous")}


def lire_filtres(params):
    """Filtres de la requête. Valeur inconnue : erreur 400 explicite, jamais ignorée."""
    from apps.core.request_text import identifiant
    from apps.payments.models import Payment
    from apps.payments.reminders import STATUS_LABELS
    from apps.schools.models import Level

    erreurs, v = {}, {}
    for cle in ("annee", "niveau", "classe", "eleve"):
        brut = params.get(cle)
        if brut:
            v[cle] = identifiant(brut)
            if v[cle] is None:
                erreurs[cle] = "Identifiant invalide."
    if params.get("cycle"):
        if params["cycle"] not in dict(Level.CYCLE_CHOICES):
            erreurs["cycle"] = "Cycle inconnu."
        v["cycle"] = params["cycle"]

    def liste(cle, permis):
        valeurs = tuple(x for x in (params.get(cle) or "").split(",") if x)
        inconnues = [x for x in valeurs if x not in permis]
        if inconnues:
            erreurs[cle] = f"Valeur inconnue : {', '.join(inconnues)}."
        return valeurs
    v["natures"] = liste("nature", dict(Payment.PAYMENT_TYPES))
    v["modes"] = liste("mode", dict(Payment.PAYMENT_METHODS))
    v["statuts_echeance"] = liste("statut_echeance", STATUS_LABELS)
    for cle, permis in (("statut", STATUTS), ("solde", SOLDES)):
        valeur = params.get(cle) or "tous"
        if valeur not in permis:
            erreurs[cle] = f"Valeur attendue : {', '.join(permis)}."
        v[cle] = valeur
    for cle in ("montant_min", "montant_max"):
        brut = (params.get(cle) or "").strip().replace(",", ".")
        if brut:
            try:
                v[cle] = Decimal(brut)
                if v[cle] < 0 or not v[cle].is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                erreurs[cle] = "Montant invalide."
    if not erreurs and v.get("montant_min") is not None and v.get("montant_max") is not None \
            and v["montant_min"] > v["montant_max"]:
        erreurs["montant_max"] = "Le montant maximal doit être supérieur au minimal."
    if erreurs:
        raise FiltreInvalide(erreurs)
    return Filtres(**v)


def _mineur(montant, academie):
    from apps.core.currency import currency_for
    return int(montant * currency_for(academie).minor_units_per_unit)


def _structure(qs, f, prefixe="student__"):
    if f.cycle:
        qs = qs.filter(**{f"{prefixe}current_class__level__cycle": f.cycle})
    if f.niveau:
        qs = qs.filter(**{f"{prefixe}current_class__level_id": f.niveau})
    if f.classe:
        qs = qs.filter(**{f"{prefixe}current_class_id": f.classe})
    if f.eleve:
        qs = qs.filter(**{f"{prefixe}id" if prefixe else "id": f.eleve})
    return qs


def _montants(qs, f, academie):
    if f.montant_min is not None:
        qs = qs.filter(amount_minor__gte=_mineur(f.montant_min, academie))
    if f.montant_max is not None:
        qs = qs.filter(amount_minor__lte=_mineur(f.montant_max, academie))
    return qs


class _Contexte:
    """Calculs par académie partagés entre la période et la période précédente."""

    def __init__(self, academie, f, aujourd_hui):
        from apps.payments.models import FeeSchedule
        from apps.payments.reminders import compute_dues
        self.academie, self.f, self.aujourd_hui = academie, f, aujourd_hui
        self.a_tarifs = FeeSchedule.objects.filter(academy=academie, is_active=True,
                                                   installments__isnull=False).exists()
        items = compute_dues(academie, on_date=aujourd_hui).items if self.a_tarifs else []
        # Solde de l'élève : restant sur ses échéances passées (toutes natures, toutes années).
        self.eleves_dus = {i.student.pk for i in items
                           if i.installment.due_date <= aujourd_hui and i.outstanding > 0}
        self.eleves_avec_echeances = {i.student.pk for i in items}
        self.items = [i for i in items if self._garde(i)]

    def _garde(self, i):
        f, cls = self.f, i.student.current_class
        if f.annee and i.school_year_id != f.annee:
            return False
        if f.cycle and getattr(getattr(cls, "level", None), "cycle", None) != f.cycle:
            return False
        if f.niveau and getattr(cls, "level_id", None) != f.niveau:
            return False
        if f.classe and getattr(cls, "pk", None) != f.classe:
            return False
        if f.eleve and i.student.pk != f.eleve:
            return False
        if f.natures and i.fee.payment_type not in f.natures:
            return False
        if f.statuts_echeance and i.status not in f.statuts_echeance:
            return False
        if f.montant_min is not None and i.net < _mineur(f.montant_min, self.academie):
            return False
        if f.montant_max is not None and i.net > _mineur(f.montant_max, self.academie):
            return False
        return self._solde_ok(i.student.pk)

    def _solde_ok(self, eleve_id):
        if self.f.solde == "du":
            return eleve_id in self.eleves_dus
        if self.f.solde == "a_jour":
            return eleve_id in self.eleves_avec_echeances and eleve_id not in self.eleves_dus
        return True

    def paiements(self, debut, fin):
        """Paiements non supprimés de la période, filtrés (confirmés et annulés)."""
        from apps.payments.models import Payment
        f = self.f
        qs = Payment.objects.filter(student__school=self.academie, is_deleted=False,
                                    payment_date__gte=debut, payment_date__lte=fin)
        if f.annee:
            qs = qs.filter(school_year_id=f.annee)
        qs = _montants(_structure(qs, f), f, self.academie)
        if f.natures:
            qs = qs.filter(payment_type__in=f.natures)
        if f.modes:
            qs = qs.filter(payment_method__in=f.modes)
        if f.solde == "du":
            qs = qs.filter(student_id__in=self.eleves_dus)
        elif f.solde == "a_jour":
            qs = qs.filter(student_id__in=self.eleves_avec_echeances - self.eleves_dus)
        if f.statut == "annule":
            return qs.filter(is_confirmed=False)
        if f.statut in ("confirme", "rembourse"):
            qs = qs.filter(is_confirmed=True)
        if f.statut == "rembourse":
            qs = qs.filter(card_transaction__amount_refunded_minor__gt=0)
        return qs

    def transactions(self, debut, fin):
        """Transactions carte sans encaissement (en attente, échouées) : seulement en statut « tous »."""
        from apps.payments.transaction_models import PaymentTransaction
        f = self.f
        qs = PaymentTransaction.objects.filter(academy=self.academie, created_at__date__gte=debut,
                                               created_at__date__lte=fin)
        if f.statut != "tous" or (f.modes and "card" not in f.modes) or f.statuts_echeance:
            return qs.none()
        if f.annee:
            qs = qs.filter(school_year_id=f.annee)
        qs = _montants(_structure(qs, f), f, self.academie)
        if f.natures:
            qs = qs.filter(payment_type__in=f.natures)
        if f.solde == "du":
            qs = qs.filter(student_id__in=self.eleves_dus)
        elif f.solde == "a_jour":
            qs = qs.filter(student_id__in=self.eleves_avec_echeances - self.eleves_dus)
        return qs


def _indicateurs(ctx, debut, fin, par_jour, cases):
    """Indicateurs et série d'une académie sur [debut, fin]."""
    from apps.payments.transaction_models import PaymentTransaction
    payes = ctx.paiements(debut, fin)
    confirmes = payes.filter(is_confirmed=True)
    serie = {c: {"encaisse": 0, "attendu": 0} for c in cases}
    if par_jour:
        lignes = confirmes.values("payment_date").annotate(t=Sum("amount_minor"), n=Count("id"))
        brut = [(l["payment_date"], l["t"] or 0, l["n"]) for l in lignes]
    else:
        lignes = (confirmes.annotate(m=TruncMonth("payment_date")).values("m")
                  .annotate(t=Sum("amount_minor"), n=Count("id")))
        brut = [(l["m"], l["t"] or 0, l["n"]) for l in lignes]
    remb = (PaymentTransaction.objects.filter(payment__in=confirmes, amount_refunded_minor__gt=0)
            .values_list("payment__payment_date", "amount_refunded_minor"))
    total_brut = total_remb = nb = 0
    for jour, t, n in brut:
        jour = jour.date() if isinstance(jour, datetime) else jour
        serie[_case(jour, par_jour)]["encaisse"] += t
        total_brut += t
        nb += n
    for jour, r in remb:
        serie[_case(jour, par_jour)]["encaisse"] -= r
        total_remb += r
    annules = payes.filter(is_confirmed=False).aggregate(t=Sum("amount_minor"), n=Count("id"))
    transactions = ctx.transactions(debut, fin)
    attente = transactions.filter(status__in=PaymentTransaction.OPEN_STATUSES).aggregate(
        t=Sum("amount_minor"), n=Count("id"))
    echecs = transactions.filter(status__in=[PaymentTransaction.FAILED, PaymentTransaction.CANCELLED,
                                             PaymentTransaction.EXPIRED]).aggregate(t=Sum("amount_minor"), n=Count("id"))
    echeances = [i for i in ctx.items if debut <= i.installment.due_date <= fin]
    echues = [i for i in echeances if i.installment.due_date <= ctx.aujourd_hui]
    for i in echeances:
        serie[_case(i.installment.due_date, par_jour)]["attendu"] += i.net
    return {
        "encaisse_brut": total_brut, "rembourse": total_remb, "nb_paiements": nb,
        "annule": annules["t"] or 0, "nb_annules": annules["n"],
        "en_attente": attente["t"] or 0, "nb_en_attente": attente["n"],
        "echoue": echecs["t"] or 0, "nb_echoues": echecs["n"],
        "attendu": sum(i.net for i in echeances), "attendu_echu": sum(i.net for i in echues),
        "paye_echu": sum(min(i.paid, i.net) for i in echues),
        "restant": sum(max(i.outstanding, 0) for i in echues),
    }, serie


CLES = ("encaisse_brut", "rembourse", "nb_paiements", "annule", "nb_annules", "en_attente", "nb_en_attente",
        "echoue", "nb_echoues", "attendu", "attendu_echu", "paye_echu", "restant")


def _sortie(d, echeancier):
    return {
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
    }


def _decaler(jour, mois):
    """Même jour `mois` mois plus tôt (borné à la fin du mois : 31/03 → 28/02)."""
    import calendar
    annee, m = jour.year, jour.month - mois
    while m <= 0:
        m += 12
        annee -= 1
    return date(annee, m, min(jour.day, calendar.monthrange(annee, m)[1]))


def periode_precedente(periode, debut, fin):
    """Période de comparaison.

    - périodes en mois (3, 6, 12 mois) : les mêmes dates N mois plus tôt ;
    - année scolaire et année civile : les mêmes dates un an plus tôt ;
    - 7 jours, 30 jours, personnalisée : même durée, juste avant.
    """
    if periode in ("3m", "6m", "12m"):
        n = int(periode[:-1])
        return _decaler(debut, n), _decaler(fin, n)
    if periode in ("annee", "civile"):
        return _decaler(debut, 12), _decaler(fin, 12)
    p_fin = debut - timedelta(days=1)
    return p_fin - (fin - debut), p_fin


def _variation(actuel, precedent):
    """Variation en % ; None si la base est nulle ou inconnue (jamais une division par zéro)."""
    if actuel is None or precedent is None or precedent == 0:
        return None
    return round(100 * (actuel - precedent) / abs(precedent), 1)


def calculer(academies, periode="12m", du=None, au=None, aujourd_hui=None, filtres=None, comparer=False):
    academies = list(academies)
    filtres = filtres or Filtres()
    if filtres.structure and len(academies) != 1:
        raise FiltreInvalide({"academie": "Les filtres de structure s'appliquent à une seule académie : choisissez-la."})
    aujourd_hui = aujourd_hui or timezone.localdate()
    debut, fin = bornes(periode, aujourd_hui, academies, du, au)
    par_jour = (fin - debut).days <= 31
    cases = _cases(debut, fin, par_jour)
    p_debut, p_fin = periode_precedente(periode, debut, fin)
    p_cases = _cases(p_debut, p_fin, par_jour)

    devises = defaultdict(lambda: {"academies": [], "echeancier": False, "serie": {c: {"encaisse": 0, "attendu": 0} for c in cases},
                                   **{k: 0 for k in CLES}, "precedent": {k: 0 for k in CLES}})
    par_academie = []
    for academie in academies:
        ctx = _Contexte(academie, filtres, aujourd_hui)
        d = devises[academie.currency_code]
        d["academies"].append({"id": academie.pk, "nom": academie.name})
        d["echeancier"] = d["echeancier"] or ctx.a_tarifs
        valeurs, serie = _indicateurs(ctx, debut, fin, par_jour, cases)
        for k in CLES:
            d[k] += valeurs[k]
        for c, v in serie.items():
            d["serie"][c]["encaisse"] += v["encaisse"]
            d["serie"][c]["attendu"] += v["attendu"]
        if comparer:
            prec, _ = _indicateurs(ctx, p_debut, p_fin, par_jour, p_cases)
            for k in CLES:
                d["precedent"][k] += prec[k]
        par_academie.append({
            "id": academie.pk, "nom": academie.name, "devise": academie.currency_code,
            "encaisse_minor": valeurs["encaisse_brut"] - valeurs["rembourse"], "nb_paiements": valeurs["nb_paiements"],
            "attendu_minor": valeurs["attendu"] if ctx.a_tarifs else None,
            "restant_minor": valeurs["restant"] if ctx.a_tarifs else None,
        })

    resultat = []
    for code, d in sorted(devises.items()):
        echeancier = d["echeancier"]
        entree = {
            "devise": code, "academies": d["academies"], "echeancier_configure": echeancier,
            "indicateurs": _sortie(d, echeancier),
            "serie": [{"date": c.isoformat(), "encaisse_minor": v["encaisse"],
                       "attendu_minor": v["attendu"] if echeancier else None}
                      for c, v in sorted(d["serie"].items())],
        }
        if comparer:
            prec = _sortie(d["precedent"], echeancier)
            entree["precedent"] = prec
            entree["variations"] = {k: _variation(entree["indicateurs"][k], prec[k])
                                    for k in ("encaisse_minor", "nb_paiements", "attendu_minor", "restant_minor")}
        resultat.append(entree)
    reponse = {
        "periode": {"code": periode, "du": debut.isoformat(), "au": fin.isoformat(),
                    "granularite": "jour" if par_jour else "mois"},
        "filtres": filtres.actifs(),
        "devises": resultat,
        "par_academie": par_academie,
    }
    if comparer:
        reponse["periode_precedente"] = {"du": p_debut.isoformat(), "au": p_fin.isoformat()}
    return reponse


def detail(academies, periode="12m", du=None, au=None, aujourd_hui=None, filtres=None, case=None, limite=500):
    """Paiements derrière un indicateur ou une barre : mêmes filtres, même période (bornée à la case)."""
    from apps.payments.transaction_models import PaymentTransaction
    academies = list(academies)
    filtres = filtres or Filtres()
    if filtres.structure and len(academies) != 1:
        raise FiltreInvalide({"academie": "Les filtres de structure s'appliquent à une seule académie : choisissez-la."})
    aujourd_hui = aujourd_hui or timezone.localdate()
    debut, fin = bornes(periode, aujourd_hui, academies, du, au)
    if case is not None:
        par_jour = (fin - debut).days <= 31
        c_fin = case if par_jour else date(case.year + (case.month == 12), case.month % 12 + 1, 1) - timedelta(days=1)
        debut, fin = max(debut, case), min(fin, c_fin)
    lignes, total = [], 0
    for academie in academies:
        ctx = _Contexte(academie, filtres, aujourd_hui)
        qs = (ctx.paiements(debut, fin).select_related("student__current_class__level", "school_year")
              .order_by("-payment_date", "-pk"))
        total += qs.count()
        reste = max(limite - len(lignes), 0)
        paiements = list(qs[:reste])
        remb = dict(PaymentTransaction.objects.filter(payment__in=paiements, amount_refunded_minor__gt=0)
                    .values_list("payment_id", "amount_refunded_minor"))
        for p in paiements:
            cls = p.student.current_class
            lignes.append({
                "id": p.pk, "reference": p.reference_number, "date": p.payment_date.isoformat(),
                "academie": academie.name, "devise": p.currency or academie.currency_code,
                "eleve_id": p.student_id, "eleve": p.student.get_full_name(),
                "classe": getattr(cls, "name", None), "niveau": getattr(getattr(cls, "level", None), "name", None),
                "annee": getattr(p.school_year, "name", None),
                "nature": p.payment_type, "nature_libelle": p.get_payment_type_display(),
                "mode": p.payment_method, "mode_libelle": p.get_payment_method_display(),
                "montant_minor": p.amount_minor, "rembourse_minor": remb.get(p.pk, 0),
                "statut": "confirme" if p.is_confirmed else "annule",
            })
    return {"du": debut.isoformat(), "au": fin.isoformat(), "total": total, "tronque": total > len(lignes),
            "filtres": filtres.actifs(), "paiements": lignes}


def options(academie, f):
    """Choix des filtres de structure, chacun limité par ceux déjà choisis (filtres dépendants)."""
    from apps.classes.models import Class
    from apps.payments.models import Payment
    from apps.schools.models import Level, SchoolYear
    from apps.students.models import Student
    annees = SchoolYear.objects.filter(school=academie).order_by("-start_date")
    niveaux = Level.objects.filter(school=academie).order_by("order", "name")
    if f.cycle:
        niveaux = niveaux.filter(cycle=f.cycle)
    classes = Class.objects.filter(level__school=academie).select_related("level").order_by("level__order", "name")
    if f.annee:
        classes = classes.filter(school_year_id=f.annee)
    if f.cycle:
        classes = classes.filter(level__cycle=f.cycle)
    if f.niveau:
        classes = classes.filter(level_id=f.niveau)
    eleves = []
    if f.classe:
        eleves = [{"id": e.pk, "nom": e.get_full_name()} for e in
                  Student.objects.filter(school=academie, current_class_id=f.classe).order_by("last_name", "first_name")]
    cycles_presents = set(Level.objects.filter(school=academie).values_list("cycle", flat=True))
    return {
        "annees": [{"id": a.pk, "nom": a.name, "en_cours": a.is_current} for a in annees],
        "cycles": [{"id": c, "nom": n} for c, n in Level.CYCLE_CHOICES if c in cycles_presents],
        "niveaux": [{"id": n.pk, "nom": n.name, "cycle": n.cycle} for n in niveaux],
        "classes": [{"id": c.pk, "nom": c.name, "niveau_id": c.level_id} for c in classes],
        "eleves": eleves,
        "natures": [{"id": k, "nom": v} for k, v in Payment.PAYMENT_TYPES],
        "modes": [{"id": k, "nom": v} for k, v in Payment.PAYMENT_METHODS],
    }


# ── Vues ──────────────────────────────────────────────────────────────

from rest_framework.permissions import IsAuthenticated  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

from apps.accounts.permissions import IsSuperAdmin  # noqa: E402


def _requete(request):
    """Académies, période et filtres de la requête ; Response 400 en cas d'erreur."""
    from django.utils.dateparse import parse_date
    from apps.core.tenancy import get_request_school
    from apps.schools.models import School

    ecole = get_request_school(request)
    academies = [ecole] if ecole is not None else list(School.objects.order_by("name"))
    p = request.query_params
    dates = {}
    for cle in ("du", "au", "case"):
        try:
            dates[cle] = parse_date(p[cle]) if p.get(cle) else None
        except ValueError:
            dates[cle] = None
        if p.get(cle) and dates[cle] is None:
            return None, Response({"detail": "Date invalide : format attendu AAAA-MM-JJ.", cle: "Date invalide."}, status=400)
    try:
        filtres = lire_filtres(p)
    except FiltreInvalide as exc:
        return None, Response({"detail": "Filtre invalide.", **exc.erreurs}, status=400)
    return {"academies": academies, "periode": p.get("periode", "12m"), "du": dates["du"], "au": dates["au"],
            "case": dates["case"], "filtres": filtres}, None


class TableauBordPaiementsView(APIView):
    """GET /api/payments/tableau-de-bord/?periode=12m[&du=&au=][&comparer=1][&filtres…]

    Super administrateur seulement. L'académie suit le sélecteur (en-tête de
    portée) : une académie précise, ou toutes en mode « Toutes les Académies ».
    Filtres : annee, cycle, niveau, classe, eleve, nature, mode (listes séparées
    par des virgules), statut, statut_echeance, solde, montant_min, montant_max.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        q, erreur = _requete(request)
        if erreur:
            return erreur
        try:
            return Response(calculer(q["academies"], q["periode"], q["du"], q["au"], filtres=q["filtres"],
                                     comparer=request.query_params.get("comparer") in ("1", "true")))
        except (PeriodeInvalide, FiltreInvalide) as exc:
            return Response({"detail": str(exc), **getattr(exc, "erreurs", {})}, status=400)


class DetailPaiementsView(APIView):
    """GET /api/payments/tableau-de-bord/detail/?…mêmes paramètres…[&case=AAAA-MM-JJ][&format=csv]

    Les paiements derrière le graphique (une barre si `case` est donnée). CSV :
    toute la sélection, jusqu'à 10 000 lignes, montants en unité de la devise.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        import csv
        from django.http import HttpResponse
        from apps.core.currency import get_currency
        q, erreur = _requete(request)
        if erreur:
            return erreur
        en_csv = request.query_params.get("export") == "csv"
        try:
            r = detail(q["academies"], q["periode"], q["du"], q["au"], filtres=q["filtres"], case=q["case"],
                       limite=10000 if en_csv else 500)
        except (PeriodeInvalide, FiltreInvalide) as exc:
            return Response({"detail": str(exc), **getattr(exc, "erreurs", {})}, status=400)
        if not en_csv:
            return Response(r)
        reponse = HttpResponse(content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = f'attachment; filename="paiements_{r["du"]}_{r["au"]}.csv"'
        reponse.write("﻿")
        w = csv.writer(reponse, delimiter=";")
        w.writerow(["Date", "Référence", "Académie", "Élève", "Classe", "Niveau", "Année", "Nature", "Mode",
                    "Montant", "Remboursé", "Devise", "Statut"])
        for l in r["paiements"]:
            unite = get_currency(l["devise"]).minor_units_per_unit
            w.writerow([l["date"], l["reference"], l["academie"], l["eleve"], l["classe"] or "", l["niveau"] or "",
                        l["annee"] or "", l["nature_libelle"], l["mode_libelle"],
                        str(Decimal(l["montant_minor"]) / unite), str(Decimal(l["rembourse_minor"]) / unite),
                        l["devise"], "Confirmé" if l["statut"] == "confirme" else "Annulé"])
        return reponse


class OptionsFiltresView(APIView):
    """GET /api/payments/tableau-de-bord/filtres/?annee=&cycle=&niveau=&classe=

    Choix proposés pour les filtres de structure de l'académie sélectionnée.
    En « Toutes les Académies », seuls les filtres financiers sont proposés.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.core.tenancy import get_request_school
        from apps.payments.models import Payment
        ecole = get_request_school(request)
        try:
            f = lire_filtres(request.query_params)
        except FiltreInvalide as exc:
            return Response({"detail": "Filtre invalide.", **exc.erreurs}, status=400)
        if ecole is None:
            return Response({"structure_disponible": False, "annees": [], "cycles": [], "niveaux": [], "classes": [],
                             "eleves": [], "natures": [{"id": k, "nom": v} for k, v in Payment.PAYMENT_TYPES],
                             "modes": [{"id": k, "nom": v} for k, v in Payment.PAYMENT_METHODS]})
        return Response({"structure_disponible": True, **options(ecole, f)})
