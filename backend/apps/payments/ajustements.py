"""
apps/payments/ajustements.py — Application des remises et exonérations aux échéances.

Appelé par `reminders._items_for`, donc par TOUT ce qui affiche un montant dû
(situation financière, relances, tableaux de bord, exports) : une seule règle.

RÈGLES (documentées dans docs/livraison/cloture/RAPPORT_MODULE_FINANCIER.md)
1. Périmètre. Une règle s'applique à un élève, pour un tarif et une année, si
   chacun de ses critères renseignés correspond : année, nature de frais, niveau
   et classe DE CETTE ANNÉE (inscription), élève, famille (responsable commun),
   rang dans la fratrie. Seules les échéances dont la date est dans [début, fin]
   sont concernées.
2. Exonérations d'abord (elles ne sont pas des remises commerciales) :
   pourcentage du montant des échéances concernées, ou montant fixe. Elles se
   cumulent entre elles, plafonnées au montant dû. 100 % = exonération totale.
3. Remises ensuite, sur le montant restant après exonération :
   - les remises CUMULABLES s'additionnent ;
   - une remise NON CUMULABLE ne se combine avec aucune autre ;
   - le moteur retient la solution la plus favorable à la famille entre
     « la somme des cumulables » et « la meilleure non cumulable » (à égalité :
     priorité, puis ancienneté) ; les remises écartées sont listées avec la raison.
   Une règle n'est comptée qu'UNE fois par élève, tarif et année.
4. Conditions. « Paiement anticipé » : le montant net (remise comprise) doit
   être entièrement payé au plus tard à la date limite. « Paiement intégral » :
   un seul paiement couvre tout le montant net. Une condition non remplie écarte
   la remise (raison affichée) ; le calcul est refait sans elle.
5. Jamais de montant négatif : chaque réduction est plafonnée au reste dû de
   l'échéance ; une réduction est imputée sur les DERNIÈRES échéances (elle
   allège le solde, elle ne retarde pas la première tranche).
6. Arrondi : pourcentage appliqué au total concerné puis arrondi à l'unité
   mineure la plus proche (demi vers le haut), de façon déterministe.
"""
from decimal import ROUND_HALF_UP, Decimal


def _pourcentage(base, pct):
    return int((Decimal(base) * Decimal(pct) / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def regle_concerne(regle, *, student, fee, year_id, level_id, class_id, parents_ids, rang):
    if not regle.en_vigueur:
        return False
    if regle.school_year_id and regle.school_year_id != year_id:
        return False
    if regle.payment_type and regle.payment_type != fee.payment_type:
        return False
    if regle.level_id and regle.level_id != level_id:
        return False
    if regle.class_obj_id and regle.class_obj_id != class_id:
        return False
    if regle.student_id and regle.student_id != student.pk:
        return False
    if regle.famille_id and regle.famille_id not in parents_ids:
        return False
    if regle.rang_enfant_min and (rang is None or rang < regle.rang_enfant_min):
        return False
    return True


def _eligibles(regle, rows):
    return [r for r in rows if (regle.debut is None or r.installment.due_date >= regle.debut)
            and (regle.fin is None or r.installment.due_date <= regle.fin)]


def _montant(regle, base):
    if base <= 0:
        return 0
    if regle.mode == regle.POURCENTAGE:
        return min(_pourcentage(base, regle.pourcentage), base)
    return min(regle.montant_minor or 0, base)


def _repartir(rows, montant, attribut):
    """Impute `montant` sur les dernières échéances, sans dépasser le reste de chacune."""
    reste = montant
    for r in reversed(rows):
        libre = r.expected - r.exemption - r.discount
        prise = min(reste, max(libre, 0))
        setattr(r, attribut, getattr(r, attribut) + prise)
        reste -= prise
        if reste <= 0:
            break
    return montant - reste


def appliquer(rows, regles, paiements, *, legacy_exoneration=False, legacy_remise=0):
    """
    Applique exonérations puis remises aux `rows` (DueItem) d'un élève × tarif × année.
    `paiements` : [(montant_net, period_month, date)]. Renvoie la liste des
    ajustements (dicts) pour l'explication du calcul.
    """
    details = []
    # 1. Exonérations.
    if legacy_exoneration:
        for r in rows:
            r.exemption = r.expected
        details.append({"regle_id": None, "nom": "Exonération totale (disposition de l'élève)", "genre": "exoneration",
                        "categorie": "disposition", "montant_minor": sum(r.expected for r in rows), "retenue": True, "raison": ""})
    for regle in sorted((g for g in regles if g.genre == g.EXONERATION), key=lambda g: (g.priorite * -1, g.pk)):
        cibles = _eligibles(regle, rows)
        base = sum(r.expected - r.exemption for r in cibles)
        pris = _repartir(cibles, _montant(regle, base), "exemption")
        details.append({"regle_id": regle.pk, "nom": regle.nom, "genre": regle.genre, "categorie": regle.categorie,
                        "montant_minor": pris, "retenue": pris > 0,
                        "raison": "" if pris > 0 else "Aucune échéance concernée ou montant déjà nul."})

    # 2. Remises (avec conditions et règle de cumul).
    remises = [g for g in regles if g.genre == g.REMISE]
    candidates = list(remises)
    ecartees = {}
    total_brut = sum(r.expected - r.exemption for r in rows)
    for _ in range(len(remises) + 1):
        choix, montants = _choisir(candidates, rows, legacy_remise)
        net = total_brut - sum(montants.values()) - (legacy_remise if "legacy" in choix else 0)
        net = max(net, 0)
        fautive = None
        for regle in (g for g in candidates if g.pk in choix):
            if regle.categorie == regle.ANTICIPE:
                regle_paye = sum(m for m, _mois, d in paiements if d and d <= regle.date_limite_paiement)
                if regle_paye < net:
                    fautive = (regle, "Solde non entièrement réglé à la date limite du paiement anticipé.")
                    break
            if regle.categorie == regle.INTEGRAL:
                if not any(m >= net for m, _mois, _d in paiements) or net == 0:
                    fautive = (regle, "Aucun paiement unique ne couvre la totalité du montant.")
                    break
        if fautive is None:
            break
        ecartees[fautive[0].pk] = fautive[1]
        candidates = [g for g in candidates if g.pk != fautive[0].pk]

    for regle in remises:
        if regle.pk in choix:
            pris = _repartir(_eligibles(regle, rows), montants[regle.pk], "discount")
            details.append({"regle_id": regle.pk, "nom": regle.nom, "genre": regle.genre, "categorie": regle.categorie,
                            "montant_minor": pris, "retenue": pris > 0, "raison": ""})
        else:
            raison = ecartees.get(regle.pk) or (
                "Non cumulable : une solution plus favorable a été retenue." if not regle.cumulable
                else "Écartée au profit d'une remise non cumulable plus favorable.")
            details.append({"regle_id": regle.pk, "nom": regle.nom, "genre": regle.genre, "categorie": regle.categorie,
                            "montant_minor": 0, "retenue": False, "raison": raison})
    if "legacy" in choix and legacy_remise:
        pris = _repartir(rows, legacy_remise, "discount")
        details.append({"regle_id": None, "nom": "Réduction (disposition de l'élève)", "genre": "remise",
                        "categorie": "disposition", "montant_minor": pris, "retenue": pris > 0, "raison": ""})
    return details


def _choisir(regles, rows, legacy_remise):
    """Ensemble de remises retenu et montant de chacune, selon la règle de cumul."""
    montants = {}
    for regle in regles:
        cibles = _eligibles(regle, rows)
        montants[regle.pk] = _montant(regle, sum(r.expected - r.exemption for r in cibles))
    cumulables = [g for g in regles if g.cumulable]
    seules = [g for g in regles if not g.cumulable]
    total_cumul = sum(montants[g.pk] for g in cumulables) + legacy_remise
    meilleure = max(seules, key=lambda g: (montants[g.pk], g.priorite, -g.pk), default=None)
    if meilleure is not None and montants[meilleure.pk] > total_cumul:
        return {meilleure.pk}, {meilleure.pk: montants[meilleure.pk]}
    choix = {g.pk for g in cumulables}
    if legacy_remise:
        choix.add("legacy")
    return choix, {g.pk: montants[g.pk] for g in cumulables}


def rangs_fratrie(students):
    """Rang de chaque élève dans sa fratrie (responsable commun), l'aîné en premier."""
    from apps.parents.models import ParentStudent
    ids = [s.pk for s in students]
    parents_de = {}
    for lien in ParentStudent.objects.filter(student_id__in=ids).values_list("student_id", "parent_id"):
        parents_de.setdefault(lien[0], set()).add(lien[1])
    par_id = {s.pk: s for s in students}
    # Composantes connexes : deux élèves partageant un responsable sont frères et sœurs.
    groupe_de, groupes = {}, []
    for sid in ids:
        if sid in groupe_de or sid not in parents_de:
            continue
        pile, membres = [sid], set()
        while pile:
            x = pile.pop()
            if x in membres:
                continue
            membres.add(x)
            for y in ids:
                if y not in membres and parents_de.get(y, set()) & parents_de.get(x, set()):
                    pile.append(y)
        for m in membres:
            groupe_de[m] = len(groupes)
        groupes.append(membres)
    rangs = {}
    for membres in groupes:
        ordre = sorted(membres, key=lambda i: (par_id[i].date_of_birth is None, par_id[i].date_of_birth or 0, i))
        for rang, i in enumerate(ordre, start=1):
            rangs[i] = rang
    return rangs, parents_de
