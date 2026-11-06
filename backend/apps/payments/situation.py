"""
Situation financière : académie, classe, niveau et élève — avec filtres, KPI,
graphiques et export.

UNE SEULE RÈGLE DE CALCUL : `reminders.compute_dues` (tarifs résolus par année et
niveau, échéanciers standard ou personnels, exonérations, remises, abonnements,
imputation des paiements confirmés nets des remboursements). Ce module ne fait
qu'agréger et filtrer : il ne réinvente aucun montant.

SOURCES DE VÉRITÉ (documentées dans RAPPORT_SITUATION_FINANCIERE.md)
- frais théoriques  : somme des échéances (montant avant toute réduction) ;
- exonérations      : part exonérée (motif, période, traçabilité : RegleRemise / disposition) ;
- remises           : part remisée, après exonération ;
- net attendu       : théorique − exonérations − remises (jamais négatif) ;
- encaissé          : part des paiements CONFIRMÉS, non supprimés, nette des
                      remboursements, IMPUTÉE sur ces échéances. Annulés, en
                      attente (carte), supprimés : exclus ;
- hors échéancier   : paiements confirmés non imputés (nature sans tarif,
                      trop-perçu) : affichés à part, jamais perdus ;
- restant           : net attendu − encaissé (toutes échéances de la période) ;
- en retard         : restant des échéances dont la date est passée ;
- taux de recouvrement       : encaissé ÷ net attendu × 100 ;
- taux de recouvrement échu  : encaissé sur échéances passées ÷ net échu × 100.
Quand aucun tarif n'est configuré, les montants attendus ne sont PAS zéro : ils
sont « non calculables » (`calculable` = false, avec la raison).
"""
import csv
from collections import defaultdict
from datetime import date

from django.http import HttpResponse

from apps.core.age import academy_today
from apps.core.currency import Money
from apps.payments.reminders import type_label

STATUTS_ELEVE = {
    "solde": "Soldé",
    "partiel": "Paiement partiel",
    "aucun": "Aucun paiement",
    "exonere": "Exonéré",
}


class Filtres:
    """Filtres communs (tableaux, KPI, graphiques, export) : mêmes règles partout."""

    CHAMPS_ID = ("annee", "niveau", "classe", "eleve")

    def __init__(self, params):
        from apps.core.request_text import date_field, identifiant
        self.annee = identifiant(params.get("annee")) if params.get("annee") else None
        self.niveau = identifiant(params.get("niveau")) if params.get("niveau") else None
        self.classe = identifiant(params.get("classe")) if params.get("classe") else None
        self.eleve = identifiant(params.get("eleve")) if params.get("eleve") else None
        self.cycle = (params.get("cycle") or "").strip()[:20] or None
        self.nature = (params.get("nature") or "").strip()[:15] or None
        self.statut = (params.get("statut") or "").strip()[:12] or None
        self.q = (params.get("q") or "").strip()[:80].lower() or None
        self.debut = date_field(params.get("debut"), "debut")
        self.fin = date_field(params.get("fin"), "fin")

    def garde_item(self, i):
        cls = getattr(i, "classe", None)
        if self.annee and i.school_year_id != self.annee:
            return False
        if self.nature and i.fee.payment_type != self.nature:
            return False
        if self.niveau and getattr(cls, "level_id", None) != self.niveau:
            return False
        if self.classe and getattr(cls, "pk", None) != self.classe:
            return False
        if self.cycle and getattr(getattr(cls, "level", None), "cycle", None) != self.cycle:
            return False
        if self.eleve and i.student.pk != self.eleve:
            return False
        if self.debut and i.installment.due_date < self.debut:
            return False
        if self.fin and i.installment.due_date > self.fin:
            return False
        if self.q:
            s = i.student
            texte = " ".join(filter(None, [s.first_name, s.last_name, s.matricule or "",
                                           getattr(cls, "name", "") or "", getattr(getattr(cls, "level", None), "name", "") or ""])).lower()
            if self.q not in texte:
                return False
        return True


def _items(academie, aujourd_hui, filtres):
    from apps.payments.reminders import compute_dues
    calcul = compute_dues(academie, on_date=aujourd_hui)
    return [i for i in calcul.items if filtres.garde_item(i)], calcul.anomalies, bool(calcul.items)


def _totaux(items, aujourd_hui):
    theorique = sum(i.expected for i in items)
    exo = sum(i.exemption for i in items)
    remises = sum(i.discount for i in items)
    net = sum(i.net for i in items)
    paye = sum(min(i.paid, i.net) for i in items)
    restant = sum(max(i.outstanding, 0) for i in items)
    echus = [i for i in items if i.installment.due_date < aujourd_hui]
    retard = sum(max(i.outstanding, 0) for i in echus)
    net_echu = sum(i.net for i in echus)
    paye_echu = sum(min(i.paid, i.net) for i in echus)
    return {
        "theorique_minor": theorique, "exonerations_minor": exo, "remises_minor": remises,
        # `attendu` = net attendu (nom conservé pour la compatibilité des écrans existants).
        "attendu_minor": net, "net_minor": net, "paye_minor": paye, "restant_minor": restant, "retard_minor": retard,
        "taux_recouvrement": round(100 * paye / net, 1) if net else None,
        "taux_recouvrement_echu": round(100 * paye_echu / net_echu, 1) if net_echu else None,
    }


def _formater(totaux, devise):
    return {**totaux, **{k.replace("_minor", "_affiche"): Money(v, devise).formatted()
                         for k, v in totaux.items() if k.endswith("_minor")}}


def _statut_eleve(t):
    if t["net_minor"] == 0:
        return "exonere" if t["exonerations_minor"] else "solde"
    if t["restant_minor"] <= 0:
        return "solde"
    return "partiel" if t["paye_minor"] > 0 else "aucun"


def _ligne_eleve(lignes, aujourd_hui, devise):
    t = _totaux(lignes, aujourd_hui)
    e = lignes[0].student
    cls = getattr(lignes[0], "classe", None) or e.current_class
    a_venir = sorted((i for i in lignes if i.outstanding > 0 and i.installment.due_date >= aujourd_hui),
                     key=lambda i: i.installment.due_date)
    jours = max((i.days_overdue for i in lignes if i.outstanding > 0 and i.installment.due_date < aujourd_hui), default=0)
    statut = _statut_eleve(t)
    return {
        "id": e.pk, "matricule": e.matricule or "", "nom": e.get_full_name(),
        "classe": getattr(cls, "name", None), "classe_id": getattr(cls, "pk", None),
        "niveau": getattr(getattr(cls, "level", None), "name", None), "niveau_id": getattr(cls, "level_id", None),
        "statut": statut, "statut_libelle": STATUTS_ELEVE[statut], "en_retard": t["retard_minor"] > 0,
        "jours_retard": jours,
        "prochaine_echeance": ({"date": a_venir[0].installment.due_date, "montant_minor": a_venir[0].outstanding,
                                "montant": Money(a_venir[0].outstanding, devise).formatted()} if a_venir else None),
        **_formater(t, devise),
    }


def _garde_statut(ligne, statut):
    if not statut:
        return True
    if statut == "en_retard":
        return ligne["en_retard"]
    if statut == "a_jour":
        return not ligne["en_retard"]
    return ligne["statut"] == statut


def _encaissements(academie, filtres, eleves_ids, devise):
    """Encaissements confirmés nets par mois (date de paiement), mêmes filtres."""
    from apps.payments.models import Payment
    from apps.payments.transaction_models import PaymentTransaction
    qs = Payment.objects.filter(student__school=academie, is_confirmed=True, is_deleted=False, student_id__in=eleves_ids)
    if filtres.annee:
        qs = qs.filter(school_year_id=filtres.annee)
    if filtres.nature:
        qs = qs.filter(payment_type=filtres.nature)
    if filtres.debut:
        qs = qs.filter(payment_date__gte=filtres.debut)
    if filtres.fin:
        qs = qs.filter(payment_date__lte=filtres.fin)
    rembourse = dict(PaymentTransaction.objects.filter(payment__in=qs, amount_refunded_minor__gt=0)
                     .values_list("payment_id", "amount_refunded_minor"))
    mois = defaultdict(int)
    total = 0
    for pk, d, m in qs.values_list("pk", "payment_date", "amount_minor"):
        net = max(m - rembourse.get(pk, 0), 0)
        mois[date(d.year, d.month, 1)] += net
        total += net
    return [{"mois": k.isoformat()[:7], "montant_minor": v, "montant": Money(v, devise).formatted()}
            for k, v in sorted(mois.items())], total


def _eleves_selection(academie, filtres):
    from django.db.models import Q
    from apps.students.models import Student
    qs = Student.objects.filter(school=academie, is_active=True)
    if filtres.classe:
        qs = qs.filter(current_class_id=filtres.classe)
    if filtres.niveau:
        qs = qs.filter(current_class__level_id=filtres.niveau)
    if filtres.cycle:
        qs = qs.filter(current_class__level__cycle=filtres.cycle)
    if filtres.eleve:
        qs = qs.filter(pk=filtres.eleve)
    if filtres.q:
        qs = qs.filter(Q(first_name__icontains=filtres.q) | Q(last_name__icontains=filtres.q) | Q(matricule__icontains=filtres.q))
    return set(qs.values_list("pk", flat=True))


def situation_groupee(academie, groupe="classe", annee_id=None, aujourd_hui=None, filtres=None,
                      page=1, par_page=50, tri="retard", ordre="desc"):
    """Totaux, KPI et graphiques de l'académie, groupes (classe / niveau) et élèves, filtrés."""
    from apps.students.models import Student
    aujourd_hui = aujourd_hui or academy_today(academie)
    devise = academie.currency_code
    filtres = filtres or Filtres({})
    if annee_id and not filtres.annee:
        filtres.annee = annee_id
    items, anomalies, configure = _items(academie, aujourd_hui, filtres)

    par_eleve = defaultdict(list)
    for i in items:
        par_eleve[i.student.pk].append(i)
    eleves = [_ligne_eleve(l, aujourd_hui, devise) for l in par_eleve.values()]
    eleves = [e for e in eleves if _garde_statut(e, filtres.statut)]
    retenus = {e["id"] for e in eleves}
    items = [i for i in items if i.student.pk in retenus]

    # Groupes (classe ou niveau de l'ANNÉE de l'échéance, pas la classe actuelle).
    par_groupe = defaultdict(list)
    for i in items:
        cls = getattr(i, "classe", None)
        cle = ((getattr(cls, "level_id", None), getattr(getattr(cls, "level", None), "name", None)) if groupe == "niveau"
               else (getattr(cls, "pk", None), getattr(cls, "name", None)))
        par_groupe[cle].append(i)
    index_eleves = {e["id"]: e for e in eleves}
    groupes = []
    for (gid, nom), lignes in par_groupe.items():
        t = _totaux(lignes, aujourd_hui)
        ids = {i.student.pk for i in lignes}
        en_retard = {s for s in ids if index_eleves[s]["en_retard"]}
        cls = getattr(lignes[0], "classe", None)
        groupes.append({"id": gid, "nom": nom or "Sans classe", "eleves": len(ids), "eleves_en_retard": len(en_retard),
                        "eleves_a_jour": len(ids) - len(en_retard),
                        "niveau": None if groupe == "niveau" else getattr(getattr(cls, "level", None), "name", None),
                        "niveau_id": None if groupe == "niveau" else getattr(cls, "level_id", None),
                        "ordre": getattr(getattr(cls, "level", None), "order", 0) or 0,
                        **_formater(t, devise)})
    groupes.sort(key=lambda g: (g["ordre"], g["nom"] or ""))

    totaux = _totaux(items, aujourd_hui)
    # Sans échéancier, les encaissements restent un chiffre RÉEL : ils portent sur les
    # élèves de la sélection (structure, recherche), pas sur une liste d'échéances vide.
    population = retenus if configure else _eleves_selection(academie, filtres)
    encaissements, encaisse_total = _encaissements(academie, filtres, population, devise)
    totaux["encaisse_total_minor"] = encaisse_total
    totaux["hors_echeancier_minor"] = max(encaisse_total - totaux["paye_minor"], 0)
    compte = defaultdict(int)
    for e in eleves:
        compte[e["statut"]] += 1
    effectif = Student.objects.filter(school=academie, is_active=True).count()
    kpi = {"effectif": effectif, "eleves_concernes": len(eleves), "eleves_soldes": compte["solde"],
           "eleves_partiels": compte["partiel"], "eleves_aucun_paiement": compte["aucun"],
           "eleves_exoneres": compte["exonere"], "eleves_en_retard": sum(1 for e in eleves if e["en_retard"])}

    # Ajustements par catégorie (graphique « remises et exonérations »).
    ajust = defaultdict(int)
    for i in items:
        if i.exemption:
            ajust[("exoneration", "exoneration")] += i.exemption
        if i.discount:
            ajust[("remise", "remise")] += i.discount
    vus = set()
    par_categorie = defaultdict(int)
    for i in items:
        cle = (i.student.pk, i.fee.pk, i.school_year_id)
        if cle in vus:
            continue
        vus.add(cle)
        for a in i.adjustments:
            if a["retenue"] and a["montant_minor"]:
                par_categorie[(a["genre"], a["categorie"])] += a["montant_minor"]

    # Tri et pagination de la vue « par élève ».
    cles_tri = {"nom": lambda e: e["nom"].lower(), "classe": lambda e: (e["classe"] or ""),
                "net": lambda e: e["net_minor"], "paye": lambda e: e["paye_minor"], "restant": lambda e: e["restant_minor"],
                "retard": lambda e: (e["retard_minor"], e["restant_minor"]), "statut": lambda e: e["statut"],
                "matricule": lambda e: e["matricule"]}
    eleves.sort(key=cles_tri.get(tri, cles_tri["retard"]), reverse=(ordre != "asc"))
    total_eleves = len(eleves)
    page = max(1, page)
    debut = (page - 1) * par_page

    return {
        "academie": {"id": academie.pk, "nom": academie.name}, "devise": devise, "groupe": groupe,
        "date_reference": aujourd_hui,
        "echeancier_configure": configure,
        "calculable": configure,
        "raison_non_calculable": None if configure else (
            "Aucun tarif avec échéances n'est configuré pour cette académie : le montant attendu et le reste à "
            "payer ne peuvent pas être calculés (ce n'est pas un montant nul)."),
        "totaux": _formater(totaux, devise), "kpi": kpi,
        "groupes": groupes,
        "eleves": eleves[debut:debut + par_page], "eleves_total": total_eleves, "page": page,
        "pages": max(1, -(-total_eleves // par_page)),
        "graphiques": {
            "repartition": [
                {"cle": "encaisse", "libelle": "Encaissé", "montant_minor": totaux["paye_minor"]},
                {"cle": "a_echoir", "libelle": "Restant à échoir", "montant_minor": totaux["restant_minor"] - totaux["retard_minor"]},
                {"cle": "retard", "libelle": "En retard", "montant_minor": totaux["retard_minor"]},
            ],
            "statuts": [{"cle": k, "libelle": v, "nombre": compte[k]} for k, v in STATUTS_ELEVE.items()],
            "encaissements_mensuels": encaissements,
            "ajustements": [{"genre": g, "categorie": c, "montant_minor": m, "montant": Money(m, devise).formatted()}
                            for (g, c), m in sorted(par_categorie.items(), key=lambda kv: -kv[1])],
        },
        "anomalies": [a.get("message") for a in anomalies][:20],
    }


def situation_eleve(eleve, annee_id=None, aujourd_hui=None, avec_historique=True):
    """Fiche financière : tarifs, remises, exonérations, échéances, paiements, reçus, retards, solde, historique."""
    from apps.payments.models import JournalFinancier, Payment
    from apps.payments.transaction_models import PaymentTransaction

    academie = eleve.school
    aujourd_hui = aujourd_hui or academy_today(academie)
    devise = academie.currency_code
    filtres = Filtres({})
    filtres.annee, filtres.eleve = annee_id, eleve.pk
    items, _anomalies, _configure = _items(academie, aujourd_hui, filtres)
    paiements = Payment.objects.filter(student=eleve, is_deleted=False).select_related("school_year").order_by("-payment_date", "-pk")
    if annee_id:
        paiements = paiements.filter(school_year_id=annee_id)
    remb = dict(PaymentTransaction.objects.filter(payment__in=paiements, amount_refunded_minor__gt=0)
                .values_list("payment_id", "amount_refunded_minor"))
    confirmes = [p for p in paiements if p.is_confirmed]
    total_net = sum(max(p.amount_minor - remb.get(p.pk, 0), 0) for p in confirmes)
    totaux = _totaux(items, aujourd_hui)
    totaux["paye_total_minor"] = total_net
    totaux["hors_echeancier_minor"] = max(total_net - totaux["paye_minor"], 0)

    # Tarifs appliqués et explication (une fois par tarif × année).
    tarifs, vus = [], set()
    for i in sorted(items, key=lambda x: (x.school_year_id, x.fee.payment_type)):
        cle = (i.fee.pk, i.school_year_id)
        if cle in vus:
            continue
        vus.add(cle)
        lignes = [x for x in items if (x.fee.pk, x.school_year_id) == cle]
        t = _totaux(lignes, aujourd_hui)
        tarifs.append({
            "tarif_id": i.fee.pk, "libelle": i.fee.label or type_label(i.fee.payment_type),
            "nature": type_label(i.fee.payment_type), "annee_id": i.school_year_id,
            "echeancier_personnel": any(getattr(x.installment, "est_personnelle", False) for x in lignes),
            "ajustements": [{**a, "montant": Money(a["montant_minor"], devise).formatted()} for a in i.adjustments],
            **_formater(t, devise),
        })
    explication = (
        f"Frais théoriques {Money(totaux['theorique_minor'], devise).formatted()}"
        f" − exonérations {Money(totaux['exonerations_minor'], devise).formatted()}"
        f" − remises {Money(totaux['remises_minor'], devise).formatted()}"
        f" = net dû {Money(totaux['net_minor'], devise).formatted()} ;"
        f" payé (imputé) {Money(totaux['paye_minor'], devise).formatted()}"
        f" ; reste {Money(totaux['restant_minor'], devise).formatted()}"
        f", dont en retard {Money(totaux['retard_minor'], devise).formatted()}."
    ) if items else None

    historique = []
    if avec_historique:
        for j in JournalFinancier.objects.filter(academy=academie, student=eleve).select_related("auteur")[:100]:
            historique.append({"le": j.le, "objet": j.get_objet_display(), "action": j.get_action_display(),
                               "description": j.description, "avant": j.avant, "apres": j.apres, "motif": j.motif,
                               "auteur": j.auteur.get_full_name() if j.auteur else j.auteur_email})
    cls = eleve.current_class
    return {
        "eleve": {"id": eleve.pk, "nom": eleve.get_full_name(), "matricule": eleve.matricule or "",
                  "classe": getattr(cls, "name", None), "niveau": getattr(getattr(cls, "level", None), "name", None)},
        "devise": devise,
        "date_reference": aujourd_hui,
        "echeancier_configure": bool(items),
        "totaux": _formater(totaux, devise),
        "explication": explication,
        "tarifs": tarifs,
        "echeances": [{**i.as_dict(), "net_minor": i.net, "net_display": Money(i.net, devise).formatted(),
                       "en_retard": i.installment.due_date < aujourd_hui and i.outstanding > 0} for i in
                      sorted(items, key=lambda x: (x.installment.due_date, x.fee.payment_type))],
        "paiements": [{
            "id": p.pk, "reference": p.reference_number, "date": p.payment_date, "nature": p.get_payment_type_display(),
            "mode": p.get_payment_method_display(), "montant": Money(p.amount_minor, p.currency or devise).formatted(),
            "rembourse": Money(remb[p.pk], p.currency or devise).formatted() if p.pk in remb else None,
            "statut": "confirmé" if p.is_confirmed else "annulé", "annee": getattr(p.school_year, "name", None),
            "recu_disponible": bool(p.receipt_file),
        } for p in paiements[:200]],
        "historique": historique,
    }


# ── Vues ──────────────────────────────────────────────────────────────

from rest_framework.permissions import IsAuthenticated  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

from apps.accounts.permissions import IsAdminOrAbove  # noqa: E402


def _annee(request):
    from apps.core.request_text import identifiant
    brut = request.query_params.get("annee")
    return identifiant(brut) if brut else None


def _academies(request):
    from apps.core.tenancy import get_request_school
    from apps.schools.models import School
    ecole = get_request_school(request)
    if ecole is None and not request.user.is_superadmin():
        return None
    return [ecole] if ecole is not None else list(School.objects.order_by("name"))


class SituationView(APIView):
    """GET /api/payments/situation/?groupe=classe|niveau|eleve&annee=&cycle=&niveau=&classe=&nature=&statut=
       &q=&debut=&fin=&page=&tri=&ordre=

    Personnel seulement. Académie du sélecteur ; en « Toutes les Académies »
    (super administrateur), une situation par académie, chacune dans sa devise.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from apps.core.request_text import identifiant
        groupe = request.query_params.get("groupe", "classe")
        if groupe not in ("classe", "niveau", "eleve"):
            return Response({"groupe": "Valeur attendue : classe, niveau ou eleve."}, status=400)
        academies = _academies(request)
        if academies is None:
            return Response({"detail": "Aucune académie."}, status=403)
        filtres = Filtres(request.query_params)
        if len(academies) > 1:
            # Vue consolidée : les filtres propres à une académie (année, classe…) n'y ont pas de sens.
            filtres = Filtres({k: v for k, v in request.query_params.items() if k in ("nature", "statut", "q", "debut", "fin")})
        page = identifiant(request.query_params.get("page")) or 1
        tri = request.query_params.get("tri", "retard")
        ordre = request.query_params.get("ordre", "desc")
        return Response({"academies": [situation_groupee(a, "classe" if groupe == "eleve" else groupe, filtres=filtres,
                                                         page=page, tri=tri, ordre=ordre) for a in academies]})


class SituationExportView(APIView):
    """GET /api/payments/situation/export/ (mêmes filtres) : CSV par élève. Personnel seulement."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from apps.core.csv_sur import cellule
        academies = _academies(request)
        if academies is None or len(academies) != 1:
            return Response({"detail": "Choisissez une académie pour exporter."}, status=400)
        a = academies[0]
        data = situation_groupee(a, filtres=Filtres(request.query_params), page=1, par_page=100000)
        reponse = HttpResponse(content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = f'attachment; filename="situation-financiere-{a.code}.csv"'
        reponse.write("﻿")
        w = csv.writer(reponse, delimiter=";")
        w.writerow(["Matricule", "Nom", "Classe", "Niveau", f"Frais théoriques ({data['devise']})", "Exonérations",
                    "Remises", "Net dû", "Payé", "Reste à payer", "En retard", "Prochaine échéance", "Statut"])
        dev = __import__("apps.core.currency", fromlist=["get_currency"]).get_currency(data["devise"])
        m = lambda v: str(dev.to_decimal(v))  # noqa: E731
        for e in data["eleves"]:
            w.writerow([cellule(e["matricule"]), cellule(e["nom"]), cellule(e["classe"] or ""), cellule(e["niveau"] or ""),
                        m(e["theorique_minor"]), m(e["exonerations_minor"]), m(e["remises_minor"]), m(e["net_minor"]),
                        m(e["paye_minor"]), m(e["restant_minor"]), m(e["retard_minor"]),
                        (e["prochaine_echeance"] or {}).get("date", "") or "", e["statut_libelle"]])
        return reponse


class SituationEleveView(APIView):
    """GET /api/payments/situation/eleves/<id>/

    Personnel de l'académie de l'élève, ou parent de l'élève (sans l'historique
    interne : auteurs et motifs restent au personnel). Enseignant et élève : refusé.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from rest_framework.exceptions import NotFound, PermissionDenied
        from apps.students.models import Student
        user = request.user
        eleve = Student.objects.select_related("school", "current_class__level").filter(pk=pk).first()
        if eleve is None:
            raise NotFound("Élève introuvable.")
        personnel = True
        if user.is_superadmin():
            pass
        elif user.is_admin():
            if eleve.school_id != user.school_id:
                raise NotFound("Élève introuvable.")
        elif user.is_parent():
            if not eleve.parents.filter(parent__user=user).exists():
                raise NotFound("Élève introuvable.")
            personnel = False
        else:
            raise PermissionDenied("Les informations financières ne sont pas accessibles à ce profil.")
        data = situation_eleve(eleve, annee_id=_annee(request), avec_historique=personnel)
        if not personnel:
            for t in data["tarifs"]:
                t["ajustements"] = [{k: v for k, v in a.items() if k in ("nom", "genre", "montant", "montant_minor", "retenue")}
                                    for a in t["ajustements"] if a["retenue"]]
        return Response(data)
