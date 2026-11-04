"""API du centre d'analyse : lecture seule, périmètre appliqué par `contexte.resoudre`."""
from django.utils.dateparse import parse_date
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import calculs
from .contexte import resoudre


class _Vue(APIView):
    permission_classes = [IsAuthenticated]
    personnel_seulement = True

    def get(self, request, *args, **kwargs):
        ctx = resoudre(request, personnel_seulement=self.personnel_seulement)
        return Response(self.calculer(ctx, request, *args, **kwargs))


class ResultatsView(_Vue):
    """GET /api/analytics/resultats/ : synthèse, répartition, maîtrise, classes, niveaux, progression."""
    def calculer(self, ctx, request):
        return calculs.resultats(ctx, request.query_params)


class MatieresView(_Vue):
    def calculer(self, ctx, request):
        return calculs.matieres(ctx, request.query_params)


class EnseignantsView(_Vue):
    """Administration : toutes les lignes ; enseignant : les siennes seulement."""
    def calculer(self, ctx, request):
        return calculs.enseignants(ctx, request.query_params)


class EffectifsView(_Vue):
    def calculer(self, ctx, request):
        return calculs.effectifs(ctx)


class PresencesView(_Vue):
    def calculer(self, ctx, request):
        dates = {}
        for cle in ("du", "au"):
            brut = request.query_params.get(cle)
            try:
                dates[cle] = parse_date(brut) if brut else None
            except ValueError:
                dates[cle] = None
            if brut and dates[cle] is None:
                raise ValidationError({cle: "Date invalide : format attendu AAAA-MM-JJ."})
        return calculs.presences(ctx, dates["du"], dates["au"])


class EleveView(_Vue):
    """GET /api/analytics/eleves/<id>/ : vue personnelle (personnel, parent de l'élève, l'élève lui-même)."""
    personnel_seulement = False

    def calculer(self, ctx, request, pk):
        from apps.students.models import Student
        eleve = Student.objects.select_related("current_class__level").filter(pk=pk, school=ctx.academie).first()
        if eleve is None:
            raise NotFound("Élève introuvable.")
        if ctx.eleves_autorises is not None and eleve.pk not in ctx.eleves_autorises:
            raise NotFound("Élève introuvable.")
        if ctx.classes_autorisees is not None and eleve.current_class_id not in ctx.classes_autorisees:
            raise PermissionDenied("Cet élève ne fait pas partie de vos classes.")
        return calculs.eleve(ctx, eleve)


class OptionsView(_Vue):
    """Choix des filtres, limités au périmètre et dépendants (cycle → niveau → classe → élève)."""
    def calculer(self, ctx, request):
        from apps.classes.models import Class
        from apps.schools.models import Level, SchoolYear
        from apps.students.models import Student
        from apps.subjects.models import Subject
        from apps.teachers.models import Teacher
        a = ctx.academie
        classes = ctx.filtrer_classes(Class.objects.filter(level__school=a, school_year=ctx.annee)).select_related("level")
        niveaux = Level.objects.filter(school=a, pk__in=classes.values("level_id")).order_by("order", "name")
        if ctx.cycle:
            niveaux = niveaux.filter(cycle=ctx.cycle)
            classes = classes.filter(level__cycle=ctx.cycle)
        if ctx.niveau:
            classes = classes.filter(level=ctx.niveau)
        matieres = Subject.objects.filter(school=a).order_by("name")
        if ctx.niveau:
            from django.db.models import Q
            matieres = matieres.filter(Q(level=ctx.niveau) | Q(level__isnull=True))
        eleves = []
        if ctx.classe:
            eleves = [{"id": e.pk, "nom": e.get_full_name()} for e in
                      Student.objects.filter(school=a, current_class=ctx.classe, is_active=True).order_by("last_name", "first_name")]
        enseignants = []
        if ctx.est_personnel:
            enseignants = [{"id": t.pk, "nom": t.user.get_full_name()} for t in
                           Teacher.objects.filter(user__school=a, user__is_active=True).select_related("user").order_by("user__last_name")]
        cycles = set(Level.objects.filter(school=a).values_list("cycle", flat=True))
        return {
            "academie": {"id": a.pk, "nom": a.name},
            "annees": [{"id": y.pk, "nom": y.name, "en_cours": y.is_current} for y in SchoolYear.objects.filter(school=a).order_by("-start_date")],
            "periodes": [{"id": c, "nom": n} for c, n in (("T1", "Trimestre 1"), ("T2", "Trimestre 2"), ("T3", "Trimestre 3"), ("exam", "Examen"))],
            "cycles": [{"id": c, "nom": n} for c, n in Level.CYCLE_CHOICES if c in cycles],
            "niveaux": [{"id": n.pk, "nom": n.name, "cycle": n.cycle} for n in niveaux],
            "classes": [{"id": c.pk, "nom": c.name, "niveau_id": c.level_id} for c in classes.order_by("level__order", "name")],
            "matieres": [{"id": m.pk, "nom": m.name} for m in matieres],
            "enseignants": enseignants,
            "eleves": eleves,
        }


class MesElevesView(_Vue):
    """GET /api/analytics/mes-eleves/ : élèves de la vue personnelle (parent : ses enfants ; élève : lui-même)."""
    personnel_seulement = False

    def calculer(self, ctx, request):
        from apps.students.models import Student
        if ctx.eleves_autorises is None:
            raise PermissionDenied("Vue réservée aux familles et aux élèves.")
        eleves = Student.objects.filter(pk__in=ctx.eleves_autorises, school=ctx.academie).select_related("current_class")
        return {"eleves": [{"id": e.pk, "nom": e.get_full_name(), "classe": getattr(e.current_class, "name", None)}
                           for e in eleves.order_by("first_name")]}
