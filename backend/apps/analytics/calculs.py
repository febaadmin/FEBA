"""
Indicateurs du centre d'analyse, agrégés en base puis assemblés ici.

Règles de calcul (identiques aux bulletins, `apps.grades.grading`) :
- moyenne d'une matière pour un élève : moyenne arithmétique de ses notes
  (toutes les évaluations pèsent 1, règle V8) ; une matière sans note ne vaut pas 0 ;
- moyenne générale d'un élève : moyennes de matières pondérées par le coefficient
  de la matière ;
- calculs internes sur 20 ; affichage dans le barème du niveau (10 ou 20). Si la
  sélection mélange les deux barèmes, l'affichage reste sur 20 et le signale ;
- réussite : moyenne ≥ seuil (50 % du barème par défaut, paramétrable) ;
- niveaux de maîtrise : barème d'appréciations de l'académie (Paramètres).

Les listes « moyennes les plus élevées » et « élèves à accompagner » ne sont
produites que pour une classe ou un niveau précis (conditions comparables) et
seulement pour les élèves ayant au moins `min_evaluations` notes.
"""
from collections import defaultdict
from decimal import Decimal
from statistics import median, pstdev

from django.db.models import Avg, Count, Q
from django.db.models.functions import Coalesce, TruncMonth

VINGT = Decimal("20")
SEUIL_DEFAUT = Decimal("50")
MIN_EVALUATIONS_DEFAUT = 3


def _r(v, n=2):
    return None if v is None else round(float(v), n)


# ── Notes ───────────────────────────────────────────────────────────────

def notes(ctx, avec_periode=True):
    from apps.grades.models import Grade
    qs = (Grade.objects.filter(is_deleted=False, school_year=ctx.annee, student__school=ctx.academie,
                               student__is_active=True)
          .annotate(classe_ref=Coalesce("enrollment__class_obj_id", "student__current_class_id"),
                    niveau_ref=Coalesce("enrollment__class_obj__level_id", "student__current_class__level_id"),
                    cycle_ref=Coalesce("enrollment__class_obj__level__cycle", "student__current_class__level__cycle")))
    if avec_periode and ctx.periode:
        qs = qs.filter(period=ctx.periode)
    if ctx.cycle:
        qs = qs.filter(cycle_ref=ctx.cycle)
    if ctx.niveau:
        qs = qs.filter(niveau_ref=ctx.niveau.pk)
    if ctx.classe:
        qs = qs.filter(classe_ref=ctx.classe.pk)
    if ctx.matiere:
        qs = qs.filter(subject_id=ctx.matiere.pk)
    if ctx.enseignant:
        qs = qs.filter(teacher_id=ctx.enseignant.pk)
    if ctx.eleve:
        qs = qs.filter(student_id=ctx.eleve.pk)
    if ctx.genre:
        qs = qs.filter(student__gender=ctx.genre)
    if ctx.classes_autorisees is not None:
        qs = qs.filter(classe_ref__in=ctx.classes_autorisees)
    if ctx.eleves_autorises is not None:
        qs = qs.filter(student_id__in=ctx.eleves_autorises)
    return qs


class Bareme:
    """Barème d'affichage de la sélection : 10 ou 20, ou 20 « mixte »."""

    def __init__(self, niveaux_ids):
        from apps.grades.grading import get_grading_scale
        from apps.schools.models import Level
        baremes = {get_grading_scale(n) for n in Level.objects.filter(pk__in=[i for i in niveaux_ids if i])}
        self.mixte = len(baremes) > 1
        self.valeur = baremes.pop() if len(baremes) == 1 else VINGT

    def aff(self, v20):
        return None if v20 is None else _r(Decimal(v20) / VINGT * self.valeur)

    def dict(self):
        return {"bareme": int(self.valeur), "bareme_mixte": self.mixte}


def _matieres(ids):
    from apps.subjects.models import Subject
    return {s.pk: s for s in Subject.objects.filter(pk__in=ids)}


def moyennes_eleves(lignes, matieres):
    """{eleve: {moyenne (sur 20), notes, classe, niveau}} à partir des moyennes par matière."""
    acc = defaultdict(lambda: {"somme": Decimal(0), "coef": 0, "notes": 0, "classe": None, "niveau": None})
    for l in lignes:
        matiere = matieres.get(l["subject_id"])
        coef = (matiere.coefficient or 1) if matiere is not None else 1
        a = acc[l["student_id"]]
        a["somme"] += Decimal(l["moy"]) * coef
        a["coef"] += coef
        a["notes"] += l["n"]
        a["classe"], a["niveau"] = l["classe_ref"], l["niveau_ref"]
    return {e: {"moyenne": a["somme"] / a["coef"], "notes": a["notes"], "classe": a["classe"], "niveau": a["niveau"]}
            for e, a in acc.items() if a["coef"]}


def _stats(valeurs20, seuil20, bareme):
    if not valeurs20:
        return {"moyenne": None, "mediane": None, "ecart_type": None, "minimum": None, "maximum": None, "taux_reussite": None}
    v = [Decimal(x) for x in valeurs20]
    return {
        "moyenne": bareme.aff(sum(v) / len(v)), "mediane": bareme.aff(median(v)),
        "ecart_type": bareme.aff(Decimal(pstdev([float(x) for x in v]))) if len(v) > 1 else 0.0,
        "minimum": bareme.aff(min(v)), "maximum": bareme.aff(max(v)),
        "taux_reussite": _r(100 * sum(1 for x in v if x >= seuil20) / len(v), 1),
    }


def _seuil(params):
    brut = params.get("seuil")
    try:
        s = Decimal(brut) if brut else SEUIL_DEFAUT
    except Exception:
        s = None
    if s is None or not (0 < s <= 100):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"seuil": "Pourcentage attendu entre 1 et 100."})
    return s


def _min_evaluations(params):
    from apps.core.request_text import identifiant
    brut = params.get("min_evaluations")
    if not brut:
        return MIN_EVALUATIONS_DEFAUT
    v = identifiant(brut)
    if v is None or v > 100:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"min_evaluations": "Entier attendu entre 1 et 100."})
    return v


def resultats(ctx, params):
    from apps.classes.models import Class
    from apps.grades.appreciations import effective_scale
    from apps.schools.models import Level
    seuil, min_eval = _seuil(params), _min_evaluations(params)
    seuil20 = seuil / 100 * VINGT
    qs = notes(ctx)
    lignes = list(qs.values("student_id", "subject_id", "classe_ref", "niveau_ref").annotate(moy=Avg("value"), n=Count("id")))
    matieres = _matieres({l["subject_id"] for l in lignes})
    eleves = moyennes_eleves(lignes, matieres)
    bareme = Bareme({e["niveau"] for e in eleves.values()} | ({ctx.niveau.pk} if ctx.niveau else set()))
    valeurs = [e["moyenne"] for e in eleves.values()]

    # Répartition en tranches du barème d'affichage (5 tranches égales).
    pas = bareme.valeur / 5
    repartition = []
    for i in range(5):
        bas, haut = pas * i, pas * (i + 1)
        n = sum(1 for v in valeurs if bas <= v / VINGT * bareme.valeur < haut or (i == 4 and v / VINGT * bareme.valeur == haut))
        repartition.append({"de": _r(bas), "a": _r(haut), "eleves": n})

    # Niveaux de maîtrise : barème d'appréciations de l'académie (cycle si unique).
    cycles = set(Level.objects.filter(pk__in={e["niveau"] for e in eleves.values()}).values_list("cycle", flat=True))
    regles, _ = effective_scale(ctx.academie, cycles.pop() if len(cycles) == 1 else None)
    paliers = sorted(regles, key=lambda r: Decimal(r[0]), reverse=True)    # du plus haut au plus bas
    comptes = [0] * len(paliers)
    for v in valeurs:
        for i, (min_pct, _, _) in enumerate(paliers):
            if v * 100 >= Decimal(min_pct) * VINGT:
                comptes[i] += 1
                break
    maitrise = [{"min_pourcent": _r(m, 1), "libelle_fr": fr, "libelle_en": en or fr, "eleves": comptes[i]}
                for i, (m, fr, en) in enumerate(paliers)]

    def groupe(cle, noms):
        g = defaultdict(list)
        for e in eleves.values():
            g[e[cle]].append(e)
        sortie = []
        for gid, membres in g.items():
            st = _stats([m["moyenne"] for m in membres], seuil20, bareme)
            sortie.append({"id": gid, "nom": noms.get(gid, "Sans classe"), "eleves_notes": len(membres),
                           "notes": sum(m["notes"] for m in membres), **st})
        return sorted(sortie, key=lambda x: x["nom"] or "")

    classes = {c.pk: c.name for c in Class.objects.filter(pk__in={e["classe"] for e in eleves.values()})}
    niveaux = {n.pk: n.name for n in Level.objects.filter(pk__in={e["niveau"] for e in eleves.values()})}

    # Progression : même sélection, toutes périodes.
    progression = []
    toutes = list(notes(ctx, avec_periode=False).values("student_id", "subject_id", "classe_ref", "niveau_ref", "period")
                  .annotate(moy=Avg("value"), n=Count("id")))
    for code in ("T1", "T2", "T3", "exam"):
        par_p = moyennes_eleves([l for l in toutes if l["period"] == code], matieres | _matieres({l["subject_id"] for l in toutes}))
        if par_p:
            v = [e["moyenne"] for e in par_p.values()]
            progression.append({"periode": code, "eleves_notes": len(v), "moyenne": bareme.aff(sum(v) / len(v)),
                                "taux_reussite": _r(100 * sum(1 for x in v if x >= seuil20) / len(v), 1)})

    # Listes nominatives : conditions comparables seulement (une classe ou un niveau), assez de notes.
    listes = None
    raison = None
    if not (ctx.classe or ctx.niveau):
        raison = "Choisissez une classe ou un niveau : les élèves ne sont comparés qu'entre conditions comparables."
    else:
        from apps.students.models import Student
        eligibles = {k: v for k, v in eleves.items() if v["notes"] >= min_eval}
        noms = {s.pk: s.get_full_name() for s in Student.objects.filter(pk__in=eligibles)}
        tri = sorted(eligibles.items(), key=lambda kv: kv[1]["moyenne"], reverse=True)
        fiche = lambda kv: {"id": kv[0], "nom": noms.get(kv[0]), "classe": classes.get(kv[1]["classe"]),
                            "moyenne": bareme.aff(kv[1]["moyenne"]), "notes": kv[1]["notes"]}
        listes = {"plus_hautes": [fiche(x) for x in tri[:5]],
                  "a_accompagner": [fiche(x) for x in reversed(tri[-5:]) if x[1]["moyenne"] < seuil20],
                  "exclus_trop_peu_de_notes": len(eleves) - len(eligibles)}

    return {
        "filtres": ctx.actifs, **bareme.dict(), "seuil_pourcent": _r(seuil, 1), "min_evaluations": min_eval,
        "synthese": {"eleves_notes": len(eleves), "notes": sum(e["notes"] for e in eleves.values()),
                     **_stats(valeurs, seuil20, bareme)},
        "repartition": repartition, "maitrise": maitrise,
        "par_classe": groupe("classe", classes), "par_niveau": groupe("niveau", niveaux),
        "progression": progression, "listes": listes, "listes_indisponibles": raison,
    }


def matieres(ctx, params):
    seuil = _seuil(params)
    seuil20 = seuil / 100 * VINGT
    lignes = list(notes(ctx).values("student_id", "subject_id", "niveau_ref").annotate(moy=Avg("value"), n=Count("id")))
    infos = _matieres({l["subject_id"] for l in lignes})
    bareme = Bareme({l["niveau_ref"] for l in lignes})
    par = defaultdict(list)
    for l in lignes:
        par[l["subject_id"]].append(l)
    sortie = []
    for sid, ls in par.items():
        s = infos.get(sid)
        sortie.append({"id": sid, "nom": getattr(s, "name", "?"), "langue": getattr(s, "language", None),
                       "coefficient": getattr(s, "coefficient", None), "eleves_notes": len(ls),
                       "notes": sum(l["n"] for l in ls), **_stats([l["moy"] for l in ls], seuil20, bareme)})
    return {"filtres": ctx.actifs, **bareme.dict(), "seuil_pourcent": _r(seuil, 1),
            "matieres": sorted(sortie, key=lambda x: x["nom"])}


AVERTISSEMENT_ENSEIGNANTS = (
    "Ces chiffres décrivent les notes attribuées et les résultats des élèves, pas la qualité d'un "
    "enseignement : le niveau de départ des élèves, l'effectif, la matière, le nombre et le type "
    "d'évaluations diffèrent d'une classe à l'autre. Ils ne permettent aucune conclusion sur un enseignant."
)


def enseignants(ctx, params):
    from apps.classes.models import Class
    from apps.teachers.models import Teacher
    seuil = _seuil(params)
    seuil20 = seuil / 100 * VINGT
    qs = notes(ctx)
    if not ctx.est_personnel:
        qs = qs.filter(teacher__user=ctx.user)       # un enseignant ne voit que ses propres lignes
    lignes = list(qs.values("teacher_id", "classe_ref", "subject_id", "student_id", "niveau_ref")
                  .annotate(moy=Avg("value"), n=Count("id")))
    bareme = Bareme({l["niveau_ref"] for l in lignes})
    profs = {t.pk: t.user.get_full_name() for t in Teacher.objects.filter(pk__in={l["teacher_id"] for l in lignes}).select_related("user")}
    classes = {c.pk: c.name for c in Class.objects.filter(pk__in={l["classe_ref"] for l in lignes})}
    infos = _matieres({l["subject_id"] for l in lignes})
    par = defaultdict(list)
    for l in lignes:
        par[(l["teacher_id"], l["classe_ref"], l["subject_id"])].append(l)
    sortie = []
    for (tid, cid, sid), ls in par.items():
        sortie.append({"enseignant_id": tid, "enseignant": profs.get(tid) or "Non renseigné",
                       "classe": classes.get(cid, "Sans classe"), "matiere": getattr(infos.get(sid), "name", "?"),
                       "eleves_notes": len(ls), "notes": sum(l["n"] for l in ls),
                       "notes_par_eleve": _r(sum(l["n"] for l in ls) / len(ls), 1),
                       **{k: v for k, v in _stats([l["moy"] for l in ls], seuil20, bareme).items()
                          if k in ("moyenne", "ecart_type", "taux_reussite")}})
    # Tri par nom, jamais par résultat : ce n'est pas un classement.
    sortie.sort(key=lambda x: (x["enseignant"], x["classe"], x["matiere"]))
    return {"filtres": ctx.actifs, **bareme.dict(), "seuil_pourcent": _r(seuil, 1),
            "avertissement": AVERTISSEMENT_ENSEIGNANTS, "lignes": sortie}


# ── Effectifs ───────────────────────────────────────────────────────────

def effectifs(ctx):
    from apps.students.models import Student, StudentEnrollment
    qs = StudentEnrollment.objects.filter(school_year=ctx.annee, student__school=ctx.academie,
                                          is_active=True, student__is_active=True)
    if ctx.cycle:
        qs = qs.filter(class_obj__level__cycle=ctx.cycle)
    if ctx.niveau:
        qs = qs.filter(class_obj__level=ctx.niveau)
    if ctx.classe:
        qs = qs.filter(class_obj=ctx.classe)
    if ctx.genre:
        qs = qs.filter(student__gender=ctx.genre)
    if ctx.classes_autorisees is not None:
        qs = qs.filter(class_obj_id__in=ctx.classes_autorisees)
    total = qs.count()
    par_classe = list(qs.values("class_obj_id", "class_obj__name", "class_obj__level__name", "class_obj__max_students")
                      .annotate(n=Count("id"), filles=Count("id", filter=Q(student__gender="F")),
                                garcons=Count("id", filter=Q(student__gender="M")))
                      .order_by("class_obj__level__order", "class_obj__name"))
    par_niveau = list(qs.values("class_obj__level_id", "class_obj__level__name").annotate(n=Count("id"))
                      .order_by("class_obj__level__order"))
    par_genre = {r["student__gender"] or "?": r["n"] for r in qs.values("student__gender").annotate(n=Count("id"))}
    par_statut = {r["promotion_status"]: r["n"] for r in qs.values("promotion_status").annotate(n=Count("id"))}
    par_mois = [{"mois": r["m"].isoformat()[:7], "inscriptions": r["n"]} for r in
                qs.annotate(m=TruncMonth("enrolled_at")).values("m").annotate(n=Count("id")).order_by("m") if r["m"]]
    reponse = {
        "filtres": ctx.actifs, "annee": {"id": ctx.annee.pk, "nom": ctx.annee.name}, "inscrits": total,
        "par_genre": {"F": par_genre.get("F", 0), "M": par_genre.get("M", 0), "non_renseigne": par_genre.get("?", 0) + par_genre.get("", 0)},
        "par_statut": par_statut,
        "par_niveau": [{"id": r["class_obj__level_id"], "nom": r["class_obj__level__name"] or "Sans classe", "inscrits": r["n"]} for r in par_niveau],
        "par_classe": [{"id": r["class_obj_id"], "nom": r["class_obj__name"] or "Sans classe", "niveau": r["class_obj__level__name"],
                        "inscrits": r["n"], "filles": r["filles"], "garcons": r["garcons"], "capacite": r["class_obj__max_students"],
                        "taux_remplissage": _r(100 * r["n"] / r["class_obj__max_students"], 1) if r["class_obj__max_students"] else None}
                       for r in par_classe],
        "inscriptions_par_mois": par_mois,
    }
    if ctx.est_personnel and not any((ctx.cycle, ctx.niveau, ctx.classe, ctx.genre)):
        # Contrôle de cohérence : élèves actifs sans inscription pour l'année affichée.
        actifs = Student.objects.filter(school=ctx.academie, is_active=True)
        reponse["eleves_actifs"] = actifs.count()
        reponse["actifs_sans_inscription"] = actifs.exclude(enrollments__school_year=ctx.annee).count()
    return reponse


# ── Présences ───────────────────────────────────────────────────────────

def presences(ctx, du=None, au=None):
    from apps.attendance.models import Attendance
    from apps.classes.models import Class
    from apps.students.models import Student
    a = ctx.annee
    qs = (Attendance.objects.filter(student__school=ctx.academie, student__is_active=True)
          .filter(Q(school_year=a) | Q(school_year__isnull=True, date__gte=a.start_date, date__lte=a.end_date))
          .annotate(classe_ref=Coalesce("enrollment__class_obj_id", "student__current_class_id"),
                    niveau_ref=Coalesce("enrollment__class_obj__level_id", "student__current_class__level_id"),
                    cycle_ref=Coalesce("enrollment__class_obj__level__cycle", "student__current_class__level__cycle")))
    if du:
        qs = qs.filter(date__gte=du)
    if au:
        qs = qs.filter(date__lte=au)
    for cond, filtre in ((ctx.cycle, {"cycle_ref": ctx.cycle}), (ctx.niveau, {"niveau_ref": getattr(ctx.niveau, "pk", None)}),
                         (ctx.classe, {"classe_ref": getattr(ctx.classe, "pk", None)}), (ctx.matiere, {"subject_id": getattr(ctx.matiere, "pk", None)}),
                         (ctx.eleve, {"student_id": getattr(ctx.eleve, "pk", None)}), (ctx.genre, {"student__gender": ctx.genre})):
        if cond:
            qs = qs.filter(**filtre)
    if ctx.classes_autorisees is not None:
        qs = qs.filter(classe_ref__in=ctx.classes_autorisees)
    if ctx.eleves_autorises is not None:
        qs = qs.filter(student_id__in=ctx.eleves_autorises)

    def compte(rows):
        c = {s: 0 for s in ("present", "absent", "late", "excused")}
        for r in rows:
            c[r["status"]] = c.get(r["status"], 0) + r["n"]
        total = sum(c.values())
        return {**c, "appels": total,
                "taux_presence": _r(100 * (c["present"] + c["late"]) / total, 1) if total else None,
                "taux_absence": _r(100 * c["absent"] / total, 1) if total else None}

    global_ = compte(qs.values("status").annotate(n=Count("id")))
    par_classe = defaultdict(list)
    for r in qs.values("classe_ref", "status").annotate(n=Count("id")):
        par_classe[r["classe_ref"]].append(r)
    noms = {c.pk: c.name for c in Class.objects.filter(pk__in=par_classe)}
    par_mois = defaultdict(list)
    for r in qs.annotate(m=TruncMonth("date")).values("m", "status").annotate(n=Count("id")):
        par_mois[r["m"]].append(r)
    reponse = {
        "filtres": ctx.actifs, "periode": {"du": (du or a.start_date).isoformat(), "au": (au or a.end_date).isoformat()},
        "synthese": global_,
        "par_classe": sorted([{"id": k, "nom": noms.get(k, "Sans classe"), **compte(v)} for k, v in par_classe.items()],
                             key=lambda x: x["nom"]),
        "par_mois": [{"mois": m.isoformat()[:7], **compte(v)} for m, v in sorted(par_mois.items()) if m],
    }
    if ctx.eleves_autorises is None:
        absents = list(qs.filter(status="absent").values("student_id").annotate(n=Count("id")).order_by("-n")[:10])
        noms_e = {s.pk: s.get_full_name() for s in Student.objects.filter(pk__in=[r["student_id"] for r in absents])}
        reponse["eleves_a_suivre"] = [{"id": r["student_id"], "nom": noms_e.get(r["student_id"]), "absences_non_justifiees": r["n"]}
                                      for r in absents]
    return reponse


# ── Vue personnelle d'un élève ──────────────────────────────────────────

def eleve(ctx, eleve_obj):
    from apps.grades.grading import get_grading_scale
    qs = notes(ctx, avec_periode=False).filter(student=eleve_obj)
    lignes = list(qs.values("subject_id", "period").annotate(moy=Avg("value"), n=Count("id")))
    infos = _matieres({l["subject_id"] for l in lignes})
    niveau = getattr(eleve_obj.current_class, "level", None)
    bareme = Bareme({getattr(niveau, "pk", None)})
    par_matiere = defaultdict(dict)
    for l in lignes:
        par_matiere[l["subject_id"]][l["period"]] = {"moyenne": bareme.aff(l["moy"]), "notes": l["n"]}
    generales = []
    for code in ("T1", "T2", "T3", "exam"):
        ls = [l for l in lignes if l["period"] == code]
        if ls:
            somme = sum(Decimal(l["moy"]) * (getattr(infos.get(l["subject_id"]), "coefficient", 1) or 1) for l in ls)
            coef = sum((getattr(infos.get(l["subject_id"]), "coefficient", 1) or 1) for l in ls)
            generales.append({"periode": code, "moyenne": bareme.aff(somme / coef), "notes": sum(l["n"] for l in ls)})
    ctx.eleve = eleve_obj
    pres = presences(ctx)["synthese"]
    return {
        "eleve": {"id": eleve_obj.pk, "nom": eleve_obj.get_full_name(), "classe": getattr(eleve_obj.current_class, "name", None)},
        "annee": {"id": ctx.annee.pk, "nom": ctx.annee.name}, **bareme.dict(),
        "moyennes_generales": generales,
        "matieres": sorted([{"id": sid, "nom": getattr(infos.get(sid), "name", "?"),
                             "coefficient": getattr(infos.get(sid), "coefficient", None), "periodes": p}
                            for sid, p in par_matiere.items()], key=lambda x: x["nom"]),
        "presences": pres,
    }
