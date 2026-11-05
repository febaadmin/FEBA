"""
apps/payments/recherche.py — Recherche et filtres de la page « Paiements ».

Les filtres sont ceux du graphique du tableau de bord (`tableau_bord.lire_filtres`
et `tableau_bord.bornes`) : un même paiement est sélectionné de la même façon
sur les deux écrans. Les montants filtrés sont exprimés dans l'unité de la
devise du paiement (`amount`), ce qui reste juste en « Toutes les Académies »
où XOF et USD coexistent.

Recherche (paramètre `q`) : insensible à la casse et aux accents. Chaque mot
doit correspondre à au moins un des critères :
nom, prénom, matricule, référence, classe, type, mode, statut, montant, date.
"""
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import CharField, Count, F, Func, Q, Sum, Value
from django.db.models.functions import Lower

from .tableau_bord import FiltreInvalide, PeriodeInvalide, bornes, lire_filtres

# Correspondances un caractère pour un caractère (minuscules ET majuscules : lower() de
# SQLite ne traite que l'ASCII).
ACCENTS = "àâäáãåçéèêëíìîïñóòôöõúùûüýÿœæÀÂÄÁÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝŸŒÆ"
SANS = "aaaaaaceeeeiiiinooooouuuuyyoaaaaaaaceeeeiiiinooooouuuuyyoa"


class SansAccents(Func):
    """Texte en minuscules sans accents, pour comparer sans extension de base de données.

    PostgreSQL : translate(lower(x), …). SQLite (suite de tests) : replace() imbriqués.
    """
    function = "translate"
    output_field = CharField()

    def __init__(self, expression):
        super().__init__(Lower(expression), Value(ACCENTS), Value(SANS))

    def as_sqlite(self, compiler, connection, **extra_context):
        sql, params = compiler.compile(self.source_expressions[0])
        for a, b in zip(ACCENTS, SANS):
            sql = f"replace({sql}, %s, %s)"
            params = [*params, a, b]
        return f"lower({sql})", params


def normaliser(texte):
    texte = unicodedata.normalize("NFD", (texte or "").lower())
    return "".join(c for c in texte if not unicodedata.combining(c)).replace("œ", "o").replace("æ", "a")


TRI = {
    "date": ("payment_date", "paid_at"),
    "montant": ("amount",),
    "eleve": ("_tri_nom", "_tri_prenom"),
    "type": ("payment_type",),
    "statut": ("is_confirmed",),
    "mode": ("payment_method",),
}


def ordonner(qs, tri):
    """Tri stable : clé demandée puis identifiant (une page ne « saute » jamais)."""
    tri = tri or "-date"
    desc = tri.startswith("-")
    cle = tri.lstrip("-")
    if cle not in TRI:
        raise FiltreInvalide({"tri": f"Tri inconnu ; possibles : {', '.join(TRI)}."})
    if cle == "eleve":
        # Ordre alphabétique sans accents : « Ébène » avant « Élève », quelle que soit la collation.
        qs = qs.annotate(_tri_nom=SansAccents("student__last_name"), _tri_prenom=SansAccents("student__first_name"))
    champs = [F(c).desc(nulls_last=True) if desc else F(c).asc(nulls_first=True) for c in TRI[cle]]
    return qs.order_by(*champs, "-pk" if desc else "pk")


def _date_de(terme):
    """Date complète (31/10/2026, 2026-10-31) ou partielle (31/10) ; None sinon."""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", terme)
    if m:
        a, mo, j = map(int, m.groups())
        return {"y": a, "m": mo, "d": j}
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", terme)
    if m:
        j, mo, a = m.groups()
        r = {"d": int(j), "m": int(mo)}
        if a:
            r["y"] = int(a) + (2000 if len(a) == 2 else 0)
        return r
    return None


def rechercher(qs, q):
    from .models import Payment
    termes = [t for t in normaliser(q).split() if t]
    if not termes:
        return qs
    qs = qs.annotate(
        _nom=SansAccents("student__last_name"), _prenom=SansAccents("student__first_name"),
        _classe=SansAccents("enrollment__class_obj__name"), _classe_actuelle=SansAccents("student__current_class__name"),
    )
    natures = {k: normaliser(v) for k, v in Payment.PAYMENT_TYPES}
    modes = {k: normaliser(v) for k, v in Payment.PAYMENT_METHODS}
    for t in termes:
        cond = (Q(_nom__contains=t) | Q(_prenom__contains=t) | Q(student__matricule__icontains=t)
                | Q(reference_number__icontains=t) | Q(_classe__contains=t)
                | (Q(enrollment__class_obj__isnull=True) & Q(_classe_actuelle__contains=t)))
        codes_nature = [k for k, v in natures.items() if t in v or t == k]
        if codes_nature:
            cond |= Q(payment_type__in=codes_nature)
        codes_mode = [k for k, v in modes.items() if t in v or t == k]
        if codes_mode:
            cond |= Q(payment_method__in=codes_mode)
        if t in ("confirme", "confirmes", "confirmé"):
            cond |= Q(is_confirmed=True)
        if t in ("annule", "annules", "annulé"):
            cond |= Q(is_confirmed=False)
        chiffres = t.replace(" ", "").replace(",", ".")
        if re.fullmatch(r"\d+(\.\d+)?", chiffres):
            try:
                cond |= Q(amount=Decimal(chiffres))
            except InvalidOperation:
                pass
        d = _date_de(t)
        if d:
            try:
                if "y" in d:
                    cond |= Q(payment_date=date(d["y"], d["m"], d["d"]))
                else:
                    date(2000, d["m"], d["d"])          # valide le jour et le mois
                    cond |= Q(payment_date__day=d["d"], payment_date__month=d["m"])
            except ValueError:
                pass
        qs = qs.filter(cond)
    return qs


def filtrer(qs, params, academies, aujourd_hui=None):
    """Applique période, filtres partagés, montant exact, remboursés et recherche.

    Lève FiltreInvalide / PeriodeInvalide (réponses 400 explicites).
    """
    from django.utils import timezone
    f = lire_filtres(params)
    if f.structure and len(academies) != 1:
        raise FiltreInvalide({"academie": "Les filtres de structure s'appliquent à une seule académie : choisissez-la."})
    periode = params.get("periode")
    if periode:
        from django.utils.dateparse import parse_date
        try:
            du = parse_date(params.get("du") or "") if params.get("du") else None
            au = parse_date(params.get("au") or "") if params.get("au") else None
        except ValueError:
            du = au = None
        debut, fin = bornes(periode, aujourd_hui or timezone.localdate(), academies, du, au)
        qs = qs.filter(payment_date__gte=debut, payment_date__lte=fin)
    if f.annee:
        qs = qs.filter(school_year_id=f.annee)
    # Classe de l'année : celle de l'inscription du paiement, sinon la classe actuelle.
    if f.classe:
        qs = qs.filter(Q(enrollment__class_obj_id=f.classe)
                       | Q(enrollment__class_obj__isnull=True, student__current_class_id=f.classe))
    if f.niveau:
        qs = qs.filter(Q(enrollment__class_obj__level_id=f.niveau)
                       | Q(enrollment__class_obj__isnull=True, student__current_class__level_id=f.niveau))
    if f.cycle:
        qs = qs.filter(Q(enrollment__class_obj__level__cycle=f.cycle)
                       | Q(enrollment__class_obj__isnull=True, student__current_class__level__cycle=f.cycle))
    if f.eleve:
        qs = qs.filter(student_id=f.eleve)
    if f.natures:
        qs = qs.filter(payment_type__in=f.natures)
    if f.modes:
        qs = qs.filter(payment_method__in=f.modes)
    if f.montant_min is not None:
        qs = qs.filter(amount__gte=f.montant_min)
    if f.montant_max is not None:
        qs = qs.filter(amount__lte=f.montant_max)
    exact = (params.get("montant") or "").strip().replace(",", ".")
    if exact:
        try:
            qs = qs.filter(amount=Decimal(exact))
        except InvalidOperation:
            raise FiltreInvalide({"montant": "Montant invalide."})
    if f.statut == "confirme":
        qs = qs.filter(is_confirmed=True)
    elif f.statut == "annule":
        qs = qs.filter(is_confirmed=False)
    elif f.statut == "rembourse":
        qs = qs.filter(is_confirmed=True, card_transaction__amount_refunded_minor__gt=0)
    if params.get("q"):
        qs = rechercher(qs, params["q"][:100])
    return qs


def totaux(qs):
    """Récapitulatif des paiements sélectionnés, par devise (jamais additionnées entre elles)."""
    from .transaction_models import PaymentTransaction
    lignes = (qs.order_by().values("currency", "is_confirmed")
              .annotate(t=Sum("amount_minor"), n=Count("id")))
    par_devise = {}
    for l in lignes:
        d = par_devise.setdefault(l["currency"], {"devise": l["currency"], "confirme_minor": 0, "nb_confirmes": 0,
                                                  "annule_minor": 0, "nb_annules": 0, "rembourse_minor": 0})
        if l["is_confirmed"]:
            d["confirme_minor"] += l["t"] or 0
            d["nb_confirmes"] += l["n"]
        else:
            d["annule_minor"] += l["t"] or 0
            d["nb_annules"] += l["n"]
    remb = (PaymentTransaction.objects.filter(payment__in=qs.filter(is_confirmed=True), amount_refunded_minor__gt=0)
            .values("payment__currency").annotate(t=Sum("amount_refunded_minor")))
    for r in remb:
        if r["payment__currency"] in par_devise:
            par_devise[r["payment__currency"]]["rembourse_minor"] += r["t"] or 0
    for d in par_devise.values():
        d["net_minor"] = d["confirme_minor"] - d["rembourse_minor"]
    return sorted(par_devise.values(), key=lambda d: d["devise"])


__all__ = ["filtrer", "ordonner", "rechercher", "totaux", "FiltreInvalide", "PeriodeInvalide", "TRI"]
