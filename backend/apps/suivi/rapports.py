"""Rapports pédagogiques : tirés des données réelles, rédigés et validés par l'enseignant, puis figés."""
import io
import json
from xml.sax.saxutils import escape

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rest_framework.exceptions import ValidationError

from . import services
from .models import Objectif, PlanAccompagnement, RapportPedagogique, RapportVersion

NON_RENSEIGNE = "Non renseigné"
RUBRIQUES = [
    ("bilan", "Bilan général"), ("points_forts", "Points forts"), ("points_ameliorer", "Points à améliorer"),
    ("difficultes", "Difficultés"), ("recommandations", "Recommandations pédagogiques"),
    ("appreciation", "Appréciation de l'enseignant"),
]


def _instantane(student, du, au):
    fiche = services.fiche(student, du, au)
    objectifs = Objectif.objects.filter(student=student)
    plans = PlanAccompagnement.objects.filter(student=student, statut="actif")
    donnees = {
        "eleve": {"nom": student.get_full_name(), "matricule": student.matricule,
                  "classe": student.current_class.name if student.current_class else None},
        "periode": {"du": du, "au": au},
        "progression": fiche["progression"], "assiduite": fiche["assiduite"], "participation": fiche["participation"],
        "competences": fiche["competences"], "evaluations": fiche["evaluations"],
        "resultats_examens": fiche["resultats_examens"],
        "objectifs_atteints": list(objectifs.filter(statut="atteint").values_list("titre", flat=True)),
        "objectifs_restants": list(objectifs.filter(statut__in=["a_commencer", "en_cours", "reporte"]).values_list("titre", flat=True)),
        "plans": list(plans.values_list("titre", flat=True)),
    }
    return json.loads(json.dumps(donnees, cls=DjangoJSONEncoder))


def generer(student, type_rapport, du, au, user):
    if au < du:
        raise ValidationError({"au": "La fin doit suivre le début."})
    return RapportPedagogique.objects.create(student=student, type=type_rapport, du=du, au=au,
                                             donnees=_instantane(student, du, au), cree_par=user)


def _figer(rapport, user):
    RapportVersion.objects.update_or_create(
        rapport=rapport, numero=rapport.numero_version, statut=rapport.statut,
        defaults={"donnees": rapport.donnees, "contenu": rapport.contenu, "par": user})


def _charger(rapport):
    return RapportPedagogique.objects.select_for_update().get(pk=rapport.pk)


def modifier(rapport, contenu, user):
    if not isinstance(contenu, dict) or set(contenu) - {c for c, _ in RUBRIQUES}:
        raise ValidationError({"contenu": "Rubrique inconnue."})
    if any(not isinstance(v, str) for v in contenu.values()):
        raise ValidationError({"contenu": "Texte attendu."})
    with transaction.atomic():
        rapport = _charger(rapport)
        if rapport.statut == RapportPedagogique.PUBLIE:
            raise ValidationError({"detail": "Un rapport publié ne se modifie plus : créez une nouvelle version."})
        rapport.contenu = {**rapport.contenu, **contenu}
        rapport.statut = RapportPedagogique.BROUILLON
        rapport.save()
    return rapport


def valider(rapport, user):
    with transaction.atomic():
        rapport = _charger(rapport)
        if rapport.statut != RapportPedagogique.BROUILLON:
            raise ValidationError({"detail": "Seul un brouillon se valide."})
        rapport.statut = RapportPedagogique.VALIDE
        rapport.save()
        _figer(rapport, user)
    return rapport


def publier(rapport, user):
    with transaction.atomic():
        rapport = _charger(rapport)
        if rapport.statut != RapportPedagogique.VALIDE:
            raise ValidationError({"detail": "Validez le rapport avant de le publier."})
        rapport.statut = RapportPedagogique.PUBLIE
        rapport.save()
        _figer(rapport, user)
    return rapport


def nouvelle_version(rapport, user):
    """Reprend un rapport publié en brouillon. Les familles gardent la version publiée."""
    with transaction.atomic():
        rapport = _charger(rapport)
        if rapport.statut != RapportPedagogique.PUBLIE:
            raise ValidationError({"detail": "Seul un rapport publié se reprend."})
        rapport.numero_version += 1
        rapport.statut = RapportPedagogique.BROUILLON
        rapport.donnees = _instantane(rapport.student, rapport.du, rapport.au)
        rapport.save()
    return rapport


def version_publiee(rapport):
    return rapport.versions.filter(statut=RapportPedagogique.PUBLIE).order_by("-numero").first()


def pdf(donnees, contenu, numero=None, type_rapport=""):
    """PDF d'une version. Une rubrique vide reste écrite comme non renseignée."""
    tampon = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(tampon, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
                            title="Rapport pédagogique", author="FEBA")
    texte = lambda v: Paragraph(escape(str(v)).replace("\n", "<br/>"), styles["BodyText"])  # noqa: E731
    titre = lambda v: Paragraph(escape(v), styles["Heading2"])  # noqa: E731
    eleve, periode = donnees.get("eleve", {}), donnees.get("periode", {})
    h = [Paragraph("Rapport pédagogique", styles["Title"]),
         texte(f"Élève : {eleve.get('nom')} - {eleve.get('matricule') or NON_RENSEIGNE}"),
         texte(f"Classe : {eleve.get('classe') or NON_RENSEIGNE}"),
         texte(f"Période : {periode.get('du')} au {periode.get('au')}" + (f" - version {numero}" if numero else "")),
         Spacer(1, 8)]
    prog, assid, part = donnees.get("progression", {}), donnees.get("assiduite", {}), donnees.get("participation", {})
    indicateurs = [
        ["Progression générale", f"{prog['valeur']} %" if prog.get("has_data") else NON_RENSEIGNE],
        ["Assiduité", f"{assid['taux']} % ({assid['absents']} absence(s), {assid['retards']} retard(s))" if assid.get("has_data") else NON_RENSEIGNE],
        ["Participation", f"{part['moyenne']} / 4" if part.get("moyenne") is not None else NON_RENSEIGNE],
    ]
    table = Table(indicateurs, colWidths=[6 * cm, 11 * cm])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "#cbd5e1"), ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    h += [titre("Indicateurs"), table]
    lignes = donnees.get("competences", {}).get("lignes", [])
    h.append(titre("Compétences"))
    if lignes:
        t2 = Table([["Compétence", "Niveau"]] + [[Paragraph(escape(l["nom"]), styles["BodyText"]), l["niveau"]] for l in lignes], colWidths=[11 * cm, 6 * cm])
        t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "#cbd5e1"), ("BACKGROUND", (0, 0), (-1, 0), "#f1f5f9")]))
        h.append(t2)
    else:
        h.append(texte(NON_RENSEIGNE))
    h.append(titre("Résultats des évaluations"))
    resultats = donnees.get("evaluations", {}).get("lignes", []) + donnees.get("resultats_examens", {}).get("lignes", [])
    h += [texte(f"{r['date']} - {r['titre']} : {r['score']} %") for r in resultats] or [texte(NON_RENSEIGNE)]
    h.append(titre("Objectifs atteints"))
    h += [texte(o) for o in donnees.get("objectifs_atteints", [])] or [texte(NON_RENSEIGNE)]
    h.append(titre("Objectifs restants"))
    h += [texte(o) for o in donnees.get("objectifs_restants", [])] or [texte(NON_RENSEIGNE)]
    h.append(titre("Plan d'accompagnement"))
    h += [texte(o) for o in donnees.get("plans", [])] or [texte(NON_RENSEIGNE)]
    for cle, libelle in RUBRIQUES:
        h += [titre(libelle), texte(contenu.get(cle) or NON_RENSEIGNE)]
    doc.build(h)
    return tampon.getvalue()
