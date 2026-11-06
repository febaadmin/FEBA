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

PERIODES = ("jour", "hier", "semaine", "semaine_prec", "mois", "mois_prec",
            "7j", "30j", "3m", "6m", "12m", "annee", "civile", "perso")
MAX_JOURS_PERSO = 3 * 366
GRANULARITES = ("auto", "heure", "jour", "semaine", "mois")


class PeriodeInvalide(ValueError):
    pass


def _mois_avant(jour, n):
    annee, mois = jour.year, jour.month - n
    while mois <= 0:
        mois += 12
        annee -= 1
    return date(annee, mois, 1)


def _fin_de_mois(jour):
    import calendar
    return date(jour.year, jour.month, calendar.monthrange(jour.year, jour.month)[1])


def bornes(periode, aujourd_hui, academies, du=None, au=None):
    """(début, fin) inclus, d'après le choix de période.

    Semaines du lundi au dimanche ; « ce mois » et « cette semaine » couvrent la
    période calendaire entière (les échéances à venir y figurent, les jours futurs
    restent vides d'encaissements).
    """
    if periode not in PERIODES:
        raise PeriodeInvalide("Période inconnue.")
    if periode == "jour":
        return aujourd_hui, aujourd_hui
    if periode == "hier":
        hier = aujourd_hui - timedelta(days=1)
        return hier, hier
    if periode in ("semaine", "semaine_prec"):
        lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        if periode == "semaine_prec":
            lundi -= timedelta(days=7)
        return lundi, lundi + timedelta(days=6)
    if periode in ("mois", "mois_prec"):
        premier = _mois_avant(aujourd_hui, 1 if periode == "mois_prec" else 0)
        return premier, _fin_de_mois(premier)
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


def granularites_possibles(debut, fin):
    """Granularités qui ont un sens pour la durée : jamais de découpage artificiel.

    - heure : une seule journée ;
    - jour : jusqu'à 92 jours ;
    - semaine : de 8 jours à deux ans ;
    - mois : au-delà d'un mois.
    """
    jours = (fin - debut).days + 1
    possibles = []
    if jours == 1:
        possibles.append("heure")
    if jours <= 92:
        possibles.append("jour")
    if 8 <= jours <= 731:
        possibles.append("semaine")
    if jours > 31:
        possibles.append("mois")
    return possibles


def choisir_granularite(debut, fin, demandee="auto"):
    if demandee not in GRANULARITES:
        raise PeriodeInvalide("Granularité inconnue.")
    possibles = granularites_possibles(debut, fin)
    if demandee == "auto":
        jours = (fin - debut).days + 1
        return "heure" if jours == 1 else "jour" if jours <= 31 else "semaine" if jours <= 92 else "mois"
    if demandee not in possibles:
        raise PeriodeInvalide(
            f"Granularité « {demandee} » inadaptée à cette période ; possibles : {', '.join(possibles)}.")
    return demandee


def _cases(debut, fin, grain):
    """Toutes les cases de la période (cases vides comprises).

    Une case est une date (jour, lundi de la semaine, 1er du mois) ou, pour la
    granularité horaire, un entier 0-23.
    """
    if grain == "heure":
        return list(range(24))
    cases = []
    if grain == "jour":
        j = debut
        while j <= fin:
            cases.append(j)
            j += timedelta(days=1)
    elif grain == "semaine":
        j = debut - timedelta(days=debut.weekday())
        while j <= fin:
            cases.append(j)
            j += timedelta(days=7)
    else:
        j = date(debut.year, debut.month, 1)
        while j <= fin:
            cases.append(j)
            j = date(j.year + (j.month == 12), j.month % 12 + 1, 1)
    return cases


def _case(jour, grain):
    if grain == "jour":
        return jour
    if grain == "semaine":
        return jour - timedelta(days=jour.weekday())
    return date(jour.year, jour.month, 1)


def _fin_case(case, grain):
    if grain == "jour":
        return case
    if grain == "semaine":
        return case + timedelta(days=6)
    return _fin_de_mois(case)


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
        from apps.students.models import Student
        # Couverture de l'échéancier (académie entière) : élèves actifs sans aucun tarif applicable.
        self.eleves_actifs = Student.objects.filter(school=academie, is_active=True).count()
        self.items = [i for i in items if self._garde(i)]

    def _garde(self, i):
        # Classe DE L'ANNÉE de l'échéance (inscription), pas la classe actuelle de l'élève.
        f, cls = self.f, getattr(i, "classe", None) or i.student.current_class
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


def _zone(academie):
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(academie.timezone or "UTC")
    except Exception:
        return timezone.get_current_timezone()


def _indicateurs(ctx, debut, fin, grain, cases):
    """Indicateurs, série et répartitions d'une académie sur [debut, fin].

    Un paiement est compté une seule fois, à sa date de paiement, pour son montant
    confirmé ; un remboursement carte est déduit à la date du paiement remboursé.
    En granularité horaire, seuls les paiements dont l'heure a été enregistrée
    peuvent être placés : les autres sont comptés à part (« sans heure »).
    """
    from django.db.models.functions import ExtractHour
    from apps.payments.models import Payment
    from apps.payments.transaction_models import PaymentTransaction
    payes = ctx.paiements(debut, fin)
    confirmes = payes.filter(is_confirmed=True)
    serie = {c: {"encaisse": 0, "attendu": 0, "nb": 0} for c in cases}
    remb_par_paiement = dict(PaymentTransaction.objects.filter(payment__in=confirmes, amount_refunded_minor__gt=0)
                             .values_list("payment_id", "amount_refunded_minor"))
    total_brut = total_remb = nb = sans_heure = 0
    if grain == "heure":
        heures = dict(confirmes.filter(paid_at__isnull=False)
                      .annotate(h=ExtractHour("paid_at", tzinfo=_zone(ctx.academie)))
                      .values_list("id", "h"))
        for pid, montant in confirmes.values_list("id", "amount_minor"):
            remb = remb_par_paiement.get(pid, 0)
            total_brut += montant
            total_remb += remb
            nb += 1
            if pid in heures:
                serie[heures[pid]]["encaisse"] += montant - remb
                serie[heures[pid]]["nb"] += 1
            else:
                sans_heure += 1
    else:
        lignes = confirmes.values("payment_date").annotate(t=Sum("amount_minor"), n=Count("id"))
        for l in lignes:
            c = serie[_case(l["payment_date"], grain)]
            c["encaisse"] += l["t"] or 0
            c["nb"] += l["n"]
            total_brut += l["t"] or 0
            nb += l["n"]
        if remb_par_paiement:
            for pid, jour in confirmes.filter(pk__in=remb_par_paiement).values_list("id", "payment_date"):
                serie[_case(jour, grain)]["encaisse"] -= remb_par_paiement[pid]
                total_remb += remb_par_paiement[pid]

    # Répartitions par nature et par mode (montants nets des remboursements).
    natures, modes = dict(Payment.PAYMENT_TYPES), dict(Payment.PAYMENT_METHODS)
    par_nature, par_mode = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for pid, nature, mode, montant in confirmes.values_list("id", "payment_type", "payment_method", "amount_minor"):
        net = montant - remb_par_paiement.get(pid, 0)
        par_nature[nature][0] += net
        par_nature[nature][1] += 1
        par_mode[mode][0] += net
        par_mode[mode][1] += 1
    nb_eleves = confirmes.values("student_id").distinct().count()

    annules = payes.filter(is_confirmed=False).aggregate(t=Sum("amount_minor"), n=Count("id"))
    transactions = ctx.transactions(debut, fin)
    attente = transactions.filter(status__in=PaymentTransaction.OPEN_STATUSES).aggregate(
        t=Sum("amount_minor"), n=Count("id"))
    echecs = transactions.filter(status__in=[PaymentTransaction.FAILED, PaymentTransaction.CANCELLED,
                                             PaymentTransaction.EXPIRED]).aggregate(t=Sum("amount_minor"), n=Count("id"))
    echeances = [i for i in ctx.items if debut <= i.installment.due_date <= fin]
    echues = [i for i in echeances if i.installment.due_date <= ctx.aujourd_hui]
    if grain != "heure":
        for i in echeances:
            serie[_case(i.installment.due_date, grain)]["attendu"] += i.net
    exoneres = [i for i in echeances if getattr(i, "status", None) == "exempted"]
    return {
        "encaisse_brut": total_brut, "rembourse": total_remb, "nb_paiements": nb, "nb_eleves": nb_eleves,
        "sans_heure": sans_heure,
        "annule": annules["t"] or 0, "nb_annules": annules["n"],
        "en_attente": attente["t"] or 0, "nb_en_attente": attente["n"],
        "echoue": echecs["t"] or 0, "nb_echoues": echecs["n"],
        "attendu": sum(i.net for i in echeances), "attendu_echu": sum(i.net for i in echues),
        "paye_echu": sum(min(i.paid, i.net) for i in echues),
        "restant": sum(max(i.outstanding, 0) for i in echues),
        "nb_exonerees": len(exoneres),
        "par_nature": {k: v for k, v in par_nature.items()},
        "par_mode": {k: v for k, v in par_mode.items()},
        "libelles": {"nature": natures, "mode": modes},
    }, serie


CLES = ("encaisse_brut", "rembourse", "nb_paiements", "nb_eleves", "sans_heure", "annule", "nb_annules",
        "en_attente", "nb_en_attente", "echoue", "nb_echoues", "attendu", "attendu_echu", "paye_echu", "restant",
        "nb_exonerees")


def _sortie(d, echeancier):
    net = d["encaisse_brut"] - d["rembourse"]
    return {
        "encaisse_minor": net,
        "encaisse_brut_minor": d["encaisse_brut"],
        "rembourse_minor": d["rembourse"],
        "nb_paiements": d["nb_paiements"],
        # Moyenne par paiement confirmé (net des remboursements) ; inconnue sans paiement.
        "moyenne_minor": round(net / d["nb_paiements"]) if d["nb_paiements"] else None,
        "nb_eleves_payeurs": d["nb_eleves"],
        "nb_sans_heure": d["sans_heure"],
        "nb_echeances_exonerees": d["nb_exonerees"] if echeancier else None,
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
    - ce mois, mois précédent : le mois calendaire d'avant, en entier ;
    - jour, hier, semaines, 7 jours, 30 jours, personnalisée : même durée, juste avant.
    """
    if periode in ("mois", "mois_prec"):
        premier = _mois_avant(debut, 1)
        return premier, _fin_de_mois(premier)
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


def calculer(academies, periode="12m", du=None, au=None, aujourd_hui=None, filtres=None, comparer=False,
             granularite="auto"):
    academies = list(academies)
    filtres = filtres or Filtres()
    if filtres.structure and len(academies) != 1:
        raise FiltreInvalide({"academie": "Les filtres de structure s'appliquent à une seule académie : choisissez-la."})
    aujourd_hui = aujourd_hui or timezone.localdate()
    debut, fin = bornes(periode, aujourd_hui, academies, du, au)
    grain = choisir_granularite(debut, fin, granularite)
    cases = _cases(debut, fin, grain)
    p_debut, p_fin = periode_precedente(periode, debut, fin)
    p_grain = grain if grain in granularites_possibles(p_debut, p_fin) else choisir_granularite(p_debut, p_fin)
    p_cases = _cases(p_debut, p_fin, p_grain)

    devises = defaultdict(lambda: {"academies": [], "echeancier": False, "eleves_actifs": 0, "eleves_avec_echeances": 0, "serie": {c: {"encaisse": 0, "attendu": 0, "nb": 0} for c in cases},
                                   "par_nature": defaultdict(lambda: [0, 0]), "par_mode": defaultdict(lambda: [0, 0]),
                                   **{k: 0 for k in CLES}, "precedent": {k: 0 for k in CLES}})
    par_academie = []
    for academie in academies:
        ctx = _Contexte(academie, filtres, aujourd_hui)
        d = devises[academie.currency_code]
        d["academies"].append({"id": academie.pk, "nom": academie.name})
        d["echeancier"] = d["echeancier"] or ctx.a_tarifs
        d["eleves_actifs"] += ctx.eleves_actifs
        d["eleves_avec_echeances"] += len(ctx.eleves_avec_echeances)
        valeurs, serie = _indicateurs(ctx, debut, fin, grain, cases)
        libelles = valeurs["libelles"]
        for k in CLES:
            d[k] += valeurs[k]
        for c, v in serie.items():
            for k in ("encaisse", "attendu", "nb"):
                d["serie"][c][k] += v[k]
        for cle in ("par_nature", "par_mode"):
            for code, (montant, n) in valeurs[cle].items():
                d[cle][code][0] += montant
                d[cle][code][1] += n
        if comparer:
            prec, _ = _indicateurs(ctx, p_debut, p_fin, p_grain, p_cases)
            for k in CLES:
                d["precedent"][k] += prec[k]
        par_academie.append({
            "id": academie.pk, "nom": academie.name, "devise": academie.currency_code,
            "encaisse_minor": valeurs["encaisse_brut"] - valeurs["rembourse"], "nb_paiements": valeurs["nb_paiements"],
            "attendu_minor": valeurs["attendu"] if ctx.a_tarifs else None,
            "restant_minor": valeurs["restant"] if ctx.a_tarifs else None,
            "echeancier_configure": ctx.a_tarifs,
            "eleves_actifs": ctx.eleves_actifs,
            "eleves_sans_tarif": ctx.eleves_actifs - len(ctx.eleves_avec_echeances) if ctx.a_tarifs else ctx.eleves_actifs,
        })

    resultat = []
    for code, d in sorted(devises.items()):
        echeancier = d["echeancier"]
        entree = {
            "devise": code, "academies": d["academies"], "echeancier_configure": echeancier,
            # Situation 2 (données partielles) : combien d'élèves actifs n'ont aucun tarif applicable.
            "couverture": {"eleves_actifs": d["eleves_actifs"], "eleves_avec_echeances": d["eleves_avec_echeances"],
                           "eleves_sans_tarif": d["eleves_actifs"] - d["eleves_avec_echeances"],
                           "academies_sans_tarif": [a["nom"] for a in par_academie
                                                    if a["devise"] == code and not a["echeancier_configure"]]},
            "indicateurs": _sortie(d, echeancier),
            "serie": [{"date": c if isinstance(c, int) else c.isoformat(),
                       "fin": None if isinstance(c, int) else _fin_case(c, grain).isoformat(),
                       "encaisse_minor": v["encaisse"], "nb_paiements": v["nb"],
                       "attendu_minor": (v["attendu"] if echeancier else None) if grain != "heure" else None}
                      for c, v in sorted(d["serie"].items())],
            "par_nature": [{"code": k, "libelle": libelles["nature"].get(k, k), "montant_minor": m, "nb": n}
                           for k, (m, n) in sorted(d["par_nature"].items(), key=lambda x: -x[1][0])],
            "par_mode": [{"code": k, "libelle": libelles["mode"].get(k, k), "montant_minor": m, "nb": n}
                         for k, (m, n) in sorted(d["par_mode"].items(), key=lambda x: -x[1][0])],
        }
        if comparer:
            prec = _sortie(d["precedent"], echeancier)
            entree["precedent"] = prec
            entree["variations"] = {k: _variation(entree["indicateurs"][k], prec[k])
                                    for k in ("encaisse_minor", "nb_paiements", "attendu_minor", "restant_minor",
                                              "moyenne_minor", "nb_eleves_payeurs")}
        resultat.append(entree)
    reponse = {
        "periode": {"code": periode, "du": debut.isoformat(), "au": fin.isoformat(),
                    "granularite": grain, "granularites_possibles": granularites_possibles(debut, fin)},
        "filtres": filtres.actifs(),
        "devises": resultat,
        "par_academie": par_academie,
    }
    if comparer:
        reponse["periode_precedente"] = {"du": p_debut.isoformat(), "au": p_fin.isoformat()}
    return reponse


def detail(academies, periode="12m", du=None, au=None, aujourd_hui=None, filtres=None, case=None, limite=500,
           granularite="auto", heure=None):
    """Paiements derrière un indicateur ou une barre : mêmes filtres, même période (bornée à la case)."""
    from apps.payments.transaction_models import PaymentTransaction
    academies = list(academies)
    filtres = filtres or Filtres()
    if filtres.structure and len(academies) != 1:
        raise FiltreInvalide({"academie": "Les filtres de structure s'appliquent à une seule académie : choisissez-la."})
    aujourd_hui = aujourd_hui or timezone.localdate()
    debut, fin = bornes(periode, aujourd_hui, academies, du, au)
    grain = choisir_granularite(debut, fin, granularite)
    if case is not None and grain != "heure":
        debut, fin = max(debut, case), min(fin, _fin_case(case, grain))
    lignes, total = [], 0
    for academie in academies:
        ctx = _Contexte(academie, filtres, aujourd_hui)
        qs = (ctx.paiements(debut, fin).select_related("student__current_class__level", "school_year")
              .order_by("-payment_date", "-pk"))
        if heure is not None:
            from django.db.models.functions import ExtractHour
            qs = qs.annotate(h=ExtractHour("paid_at", tzinfo=_zone(academie))).filter(h=heure)
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
        **natures_et_modes([academie]),
    }


def natures_et_modes(academies):
    """Natures et modes proposés aux filtres : ceux qui existent réellement.

    - natures : présentes dans les paiements ou publiées dans les tarifs ;
    - modes : présents dans les paiements, plus la carte si le paiement en ligne
      est configuré. Un mode jamais utilisé et non opérationnel n'est pas proposé.
    Chaque choix porte le nombre de paiements (non supprimés) concernés.
    """
    from apps.payments.fee_models import FeeSchedule
    from apps.payments.models import Payment
    from apps.payments.providers import get_provider, PaymentProviderError
    paiements = Payment.objects.filter(student__school__in=academies, is_deleted=False)
    n_nature = dict(paiements.values_list("payment_type").annotate(n=Count("id")).order_by())
    n_mode = dict(paiements.values_list("payment_method").annotate(n=Count("id")).order_by())
    tarifs = set(FeeSchedule.objects.filter(academy__in=academies, is_active=True)
                 .values_list("payment_type", flat=True))
    try:
        carte = get_provider().is_configured()
    except PaymentProviderError:
        carte = False
    natures = [{"id": k, "nom": v, "nb": n_nature.get(k, 0)} for k, v in Payment.PAYMENT_TYPES
               if k in n_nature or k in tarifs]
    modes = [{"id": k, "nom": v, "nb": n_mode.get(k, 0)} for k, v in Payment.PAYMENT_METHODS
             if k in n_mode or (k == "card" and carte)]
    return {"natures": natures, "modes": modes}


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
    heure = None
    if p.get("heure") not in (None, ""):
        try:
            heure = int(p["heure"])
            if not 0 <= heure <= 23:
                raise ValueError
        except ValueError:
            return None, Response({"detail": "Heure invalide (0 à 23).", "heure": "Heure invalide."}, status=400)
    return {"academies": academies, "periode": p.get("periode", "12m"), "du": dates["du"], "au": dates["au"],
            "case": dates["case"], "filtres": filtres, "granularite": p.get("granularite") or "auto",
            "heure": heure}, None


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
                                     comparer=request.query_params.get("comparer") in ("1", "true"),
                                     granularite=q["granularite"]))
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
                       limite=10000 if en_csv else 500, granularite=q["granularite"], heure=q["heure"])
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
        ecole = get_request_school(request)
        try:
            f = lire_filtres(request.query_params)
        except FiltreInvalide as exc:
            return Response({"detail": "Filtre invalide.", **exc.erreurs}, status=400)
        if ecole is None:
            from apps.schools.models import School
            return Response({"structure_disponible": False, "annees": [], "cycles": [], "niveaux": [], "classes": [],
                             "eleves": [], **natures_et_modes(list(School.objects.all()))})
        return Response({"structure_disponible": True, **options(ecole, f)})


class OptionsPaiementsView(APIView):
    """GET /api/payments/filtres/?annee=&cycle=&niveau=&classe=

    Choix des filtres de la page « Paiements » (administration de l'académie et
    super administrateur) : mêmes listes que le graphique, limitées à l'académie
    de l'utilisateur. Natures et modes : ceux réellement utilisés ou configurés.
    """
    from apps.accounts.permissions import IsAdminOrAbove
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from apps.core.tenancy import get_request_school
        from apps.schools.models import School
        ecole = get_request_school(request)
        try:
            f = lire_filtres(request.query_params)
        except FiltreInvalide as exc:
            return Response({"detail": "Filtre invalide.", **exc.erreurs}, status=400)
        if ecole is None:
            if not request.user.is_superadmin():
                return Response({"detail": "Aucune académie."}, status=403)
            return Response({"structure_disponible": False, "annees": [], "cycles": [], "niveaux": [], "classes": [],
                             "eleves": [], **natures_et_modes(list(School.objects.all()))})
        return Response({"structure_disponible": True, **options(ecole, f)})
