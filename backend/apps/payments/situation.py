"""
Situation financière : par élève, par classe, par niveau et par académie.

Une seule règle de calcul : `reminders.compute_dues` (tarifs résolus par année
et niveau, échéances, réductions, exonérations, abonnements, imputation des
paiements confirmés nets des remboursements). Ce module ne fait qu'agréger :
il ne réinvente aucun montant.

Définitions
- attendu    : montant des échéances, réductions déduites (exonération = 0) ;
- payé       : part des paiements imputée sur ces échéances ;
- restant    : attendu non couvert (toutes échéances de l'année, passées et à venir) ;
- en retard  : restant des échéances dont la date est passée ;
- hors échéancier : paiements confirmés (nets) qui ne sont imputés à aucune
  échéance (nature sans tarif, trop-perçu) ; jamais perdus, affichés à part.
"""
from collections import defaultdict

from django.db.models import Sum

from apps.core.age import academy_today
from apps.core.currency import Money


def _lignes(academie, aujourd_hui, annee_id=None):
    from apps.payments.reminders import compute_dues
    calcul = compute_dues(academie, on_date=aujourd_hui)
    items = [i for i in calcul.items if annee_id is None or i.school_year_id == annee_id]
    return items, calcul.anomalies


def _totaux(items, aujourd_hui):
    attendu = sum(i.net for i in items)
    paye = sum(min(i.paid, i.net) for i in items)
    restant = sum(max(i.outstanding, 0) for i in items)
    retard = sum(max(i.outstanding, 0) for i in items if i.installment.due_date < aujourd_hui)
    echu = sum(i.net for i in items if i.installment.due_date < aujourd_hui)
    paye_echu = sum(min(i.paid, i.net) for i in items if i.installment.due_date < aujourd_hui)
    return {"attendu_minor": attendu, "paye_minor": paye, "restant_minor": restant, "retard_minor": retard,
            "taux_recouvrement": round(100 * paye_echu / echu, 1) if echu else None}


def _formater(totaux, devise):
    return {**totaux, **{k.replace("_minor", "_affiche"): Money(v, devise).formatted()
                         for k, v in totaux.items() if k.endswith("_minor")}}


def situation_eleve(eleve, annee_id=None, aujourd_hui=None):
    from apps.payments.models import Payment
    from apps.payments.transaction_models import PaymentTransaction

    academie = eleve.school
    aujourd_hui = aujourd_hui or academy_today(academie)
    devise = academie.currency_code
    items, _ = _lignes(academie, aujourd_hui, annee_id)
    items = [i for i in items if i.student.pk == eleve.pk]
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
    return {
        "eleve": {"id": eleve.pk, "nom": eleve.get_full_name(), "classe": getattr(eleve.current_class, "name", None)},
        "devise": devise,
        "echeancier_configure": bool(items),
        "totaux": _formater(totaux, devise),
        "echeances": [{**i.as_dict(), "net_minor": i.net,
                       "en_retard": i.installment.due_date < aujourd_hui and i.outstanding > 0} for i in
                      sorted(items, key=lambda x: (x.installment.due_date, x.fee.payment_type))],
        "paiements": [{
            "id": p.pk, "reference": p.reference_number, "date": p.payment_date, "nature": p.get_payment_type_display(),
            "mode": p.get_payment_method_display(), "montant": Money(p.amount_minor, p.currency or devise).formatted(),
            "rembourse": Money(remb[p.pk], p.currency or devise).formatted() if p.pk in remb else None,
            "statut": "confirmé" if p.is_confirmed else "annulé", "annee": getattr(p.school_year, "name", None),
        } for p in paiements[:200]],
    }


def situation_groupee(academie, groupe="classe", annee_id=None, aujourd_hui=None):
    """Totaux par classe ou par niveau, plus l'académie entière et la liste des élèves."""
    aujourd_hui = aujourd_hui or academy_today(academie)
    devise = academie.currency_code
    items, anomalies = _lignes(academie, aujourd_hui, annee_id)
    par_groupe, par_eleve = defaultdict(list), defaultdict(list)
    for i in items:
        cls = i.student.current_class
        cle = (getattr(cls, "level_id", None), getattr(getattr(cls, "level", None), "name", None)) if groupe == "niveau" \
            else (getattr(cls, "pk", None), getattr(cls, "name", None))
        par_groupe[cle].append(i)
        par_eleve[i.student.pk].append(i)
    eleves_par_groupe = defaultdict(set)
    for cle, lignes in par_groupe.items():
        for i in lignes:
            eleves_par_groupe[cle].add(i.student.pk)
    groupes = []
    for (gid, nom), lignes in sorted(par_groupe.items(), key=lambda kv: (kv[0][1] or "")):
        t = _totaux(lignes, aujourd_hui)
        en_retard = {i.student.pk for i in lignes if i.installment.due_date < aujourd_hui and i.outstanding > 0}
        groupes.append({"id": gid, "nom": nom or "Sans classe", "eleves": len(eleves_par_groupe[(gid, nom)]),
                        "eleves_en_retard": len(en_retard), **_formater(t, devise)})
    eleves = []
    for sid, lignes in par_eleve.items():
        t = _totaux(lignes, aujourd_hui)
        e = lignes[0].student
        eleves.append({"id": sid, "nom": e.get_full_name(), "classe": getattr(e.current_class, "name", None),
                       "classe_id": getattr(e.current_class, "pk", None), "niveau_id": getattr(e.current_class, "level_id", None),
                       **_formater(t, devise)})
    eleves.sort(key=lambda e: (-e["retard_minor"], -e["restant_minor"], e["nom"]))
    return {"academie": {"id": academie.pk, "nom": academie.name}, "devise": devise, "groupe": groupe,
            "echeancier_configure": bool(items), "totaux": _formater(_totaux(items, aujourd_hui), devise),
            "groupes": groupes, "eleves": eleves,
            "anomalies": [a.get("message") for a in anomalies][:20]}


# ── Vues ──────────────────────────────────────────────────────────────

from rest_framework.permissions import IsAuthenticated  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

from apps.accounts.permissions import IsAdminOrAbove  # noqa: E402


def _annee(request):
    from apps.core.request_text import identifiant
    brut = request.query_params.get("annee")
    return identifiant(brut) if brut else None


class SituationView(APIView):
    """GET /api/payments/situation/?groupe=classe|niveau&annee=<id>

    Personnel seulement. Académie du sélecteur ; en « Toutes les Académies »
    (super administrateur), une situation par académie, chacune dans sa devise.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from apps.core.tenancy import get_request_school
        from apps.schools.models import School
        groupe = request.query_params.get("groupe", "classe")
        if groupe not in ("classe", "niveau"):
            return Response({"groupe": "Valeur attendue : classe ou niveau."}, status=400)
        ecole = get_request_school(request)
        if ecole is None and not request.user.is_superadmin():
            return Response({"detail": "Aucune académie."}, status=403)
        academies = [ecole] if ecole is not None else list(School.objects.order_by("name"))
        annee = _annee(request) if ecole is not None else None
        return Response({"academies": [situation_groupee(a, groupe, annee) for a in academies]})


class SituationEleveView(APIView):
    """GET /api/payments/situation/eleves/<id>/

    Personnel de l'académie de l'élève, ou parent de l'élève. Enseignant et
    élève : refusé (les finances ne les concernent pas).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from rest_framework.exceptions import NotFound, PermissionDenied
        from apps.students.models import Student
        user = request.user
        eleve = Student.objects.select_related("school", "current_class").filter(pk=pk).first()
        if eleve is None:
            raise NotFound("Élève introuvable.")
        if user.is_superadmin():
            pass
        elif user.is_admin():
            if eleve.school_id != user.school_id:
                raise NotFound("Élève introuvable.")
        elif user.is_parent():
            if not eleve.parents.filter(parent__user=user).exists():
                raise NotFound("Élève introuvable.")
        else:
            raise PermissionDenied("Les informations financières ne sont pas accessibles à ce profil.")
        return Response(situation_eleve(eleve, annee_id=_annee(request)))
