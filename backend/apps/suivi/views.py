"""API du suivi pédagogique. Lecture et écriture contrôlées côté serveur, par académie et par élève."""
import csv
import io
import logging

from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrAbove, IsSuperAdmin
from apps.core.features import HasEntityFeature, entity_has_feature
from apps.core.request_text import checked_upload, identifiant, text_field
from apps.core.tenancy import get_request_school
from apps.schools.models import School

from apps.notifications.utils import create_notification

from . import alertes, rapports, services
from .models import (
    ActionPedagogique,
    AlertePedagogique,
    Competence,
    EvaluationCompetence,
    EvaluationPedagogique,
    NiveauMaitrise,
    Objectif,
    ObjectifHistorique,
    ObservationParticipation,
    PlanAccompagnement,
    RapportPedagogique,
    Referentiel,
    RegleAlerte,
)
from .permissions import controler_ecriture, eleves_visibles, est_famille
from .serializers import (
    ActionSerializer,
    AlerteSerializer,
    CompetenceSerializer,
    EvaluationCompetenceSerializer,
    EvaluationPedagogiqueSerializer,
    NiveauSerializer,
    ObjectifSerializer,
    ObservationSerializer,
    ParametresSerializer,
    PlanSerializer,
    RapportSerializer,
    ReferentielSerializer,
    RegleSerializer,
)

logger = logging.getLogger(__name__)


def _ecole(request):
    school = get_request_school(request)
    if school is None:
        raise ValidationError({"detail": "Sélectionnez une académie."})
    return school


def _reserve_personnel(request):
    if request.user.role_level < 50:
        raise PermissionDenied("Réservé au personnel de l'académie.")


def _periode(params, du="du", au="au"):
    from apps.core.request_text import date_field
    return date_field(params.get(du), du), date_field(params.get(au), au)


class Base(viewsets.GenericViewSet):
    required_feature = "suivi_pedagogique"
    permission_classes = [IsAuthenticated, HasEntityFeature]

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        contexte["school"] = get_request_school(self.request)
        return contexte


class ReferentielConfigMixin:
    """Référentiels et compétences : lecture pour tous dans l'académie, écriture par le personnel enseignant."""

    def _controler_personnel(self):
        if self.request.user.role_level < 50:
            raise PermissionDenied("Réservé au personnel de l'académie.")


class ReferentielViewSet(ReferentielConfigMixin, Base, viewsets.ModelViewSet):
    serializer_class = ReferentielSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        self._controler_personnel()
        if EvaluationCompetence.objects.filter(competence__referentiel=instance).exists():
            raise ValidationError({"detail": "Ce référentiel a des évaluations : archivez-le, son historique reste consultable."})
        instance.delete()

    @action(detail=True, methods=["post"])
    def dupliquer(self, request, pk=None):
        """Réutilise un référentiel, sans son historique."""
        self._controler_personnel()
        source = self.get_object()
        school = _ecole(request)
        nom = f"{source.nom} (copie)"
        rang = 2
        while Referentiel.objects.filter(school=school, nom=nom).exists():
            nom = f"{source.nom} (copie {rang})"
            rang += 1
        with transaction.atomic():
            copie = Referentiel.objects.create(school=school, nom=nom, description=source.description, subject=source.subject,
                                               level=source.level, class_obj=source.class_obj, periode=source.periode,
                                               programme=source.programme, created_by=request.user)
            Competence.objects.bulk_create([
                Competence(referentiel=copie, domaine=c.domaine, sous_domaine=c.sous_domaine, code=c.code, nom=c.nom, nom_en=c.nom_en,
                           description=c.description, objectif=c.objectif, criteres=c.criteres, subject=c.subject,
                           niveau_attendu=c.niveau_attendu, periode=c.periode, ordre=c.ordre)
                for c in source.competences.filter(actif=True)])
        return Response(self.get_serializer(copie).data, status=201)

    def get_queryset(self):
        return Referentiel.objects.filter(school=get_request_school(self.request)).prefetch_related("competences")

    def perform_create(self, serializer):
        self._controler_personnel()
        serializer.save(school=_ecole(self.request), created_by=self.request.user)

    def perform_update(self, serializer):
        self._controler_personnel()
        serializer.save()


class CompetenceViewSet(ReferentielConfigMixin, Base, viewsets.ModelViewSet):
    serializer_class = CompetenceSerializer
    filterset_fields = ["referentiel", "subject", "actif", "domaine"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        valide = Q(evaluations__statut=EvaluationCompetence.VALIDEE)
        qs = Competence.objects.filter(referentiel__school=get_request_school(self.request)).select_related(
            "referentiel__subject", "subject").annotate(
            nombre_evaluations=Count("evaluations", filter=valide),
            nombre_eleves=Count("evaluations__student", filter=valide, distinct=True))
        # Une requête agrégée ignore Meta.ordering : sans ordre explicite et stable, la
        # pagination pouvait répéter ou omettre des compétences d'une page à l'autre.
        qs = qs.order_by("referentiel_id", "ordre", "nom", "pk")
        recherche = self.request.query_params.get("q")
        if recherche:
            qs = qs.filter(Q(nom__icontains=recherche) | Q(domaine__icontains=recherche) | Q(description__icontains=recherche))
        return qs

    def perform_destroy(self, instance):
        self._controler_personnel()
        if instance.evaluations.exists() or instance.questions.exists():
            raise ValidationError({"detail": "Cette compétence a un historique ou des questions liées : désactivez-la pour la conserver."})
        instance.delete()

    @action(detail=False, methods=["get"])
    def exporter(self, request):
        """CSV réimportable, avec les cellules neutralisées pour les tableurs."""
        self._controler_personnel()
        sortie = io.StringIO()
        ecrivain = csv.writer(sortie)
        ecrivain.writerow(["referentiel", "nom", "domaine", "sous_domaine", "description", "criteres"])
        qs = self.get_queryset().order_by("referentiel__nom", "domaine", "nom")
        referentiel = identifiant(request.query_params.get("referentiel"))
        if referentiel:
            qs = qs.filter(referentiel_id=referentiel)
        for c in qs:
            ligne = [c.referentiel.nom, c.nom, c.domaine, c.sous_domaine, c.description, c.criteres]
            ecrivain.writerow([f"'{x}" if str(x)[:1] in "=+-@" else x for x in ligne])
        reponse = HttpResponse(sortie.getvalue(), content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="competences.csv"'
        return reponse

    @action(detail=False, methods=["post"])
    def importer(self, request):
        """CSV : nom, domaine, sous_domaine, description, criteres. Tout ou rien, doublons ignorés."""
        self._controler_personnel()
        referentiel = get_object_or_404(Referentiel, pk=identifiant(request.data.get("referentiel")), school=_ecole(request))
        fichier = request.FILES.get("fichier")
        if fichier is None or fichier.size > 2_000_000:
            raise ValidationError({"fichier": "Fichier CSV de 2 Mo au plus attendu."})
        try:
            lignes = list(csv.DictReader(io.StringIO(fichier.read().decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error):
            raise ValidationError({"fichier": "CSV illisible : enregistrez-le en UTF-8."})
        vides = [i for i, l in enumerate(lignes, 2) if not (l.get("nom") or "").strip()]
        if vides or not lignes:
            raise ValidationError({"fichier": f"Colonne « nom » vide, ligne(s) : {vides[:10]}." if vides else "Fichier vide."})
        existants = {n.casefold() for n in referentiel.competences.values_list("nom", flat=True)}
        creees = 0
        with transaction.atomic():
            for l in lignes:
                nom = l["nom"].strip()[:200]
                if nom.casefold() in existants:
                    continue
                existants.add(nom.casefold())
                Competence.objects.create(referentiel=referentiel, nom=nom, domaine=(l.get("domaine") or "").strip()[:120],
                                          sous_domaine=(l.get("sous_domaine") or "").strip()[:120],
                                          description=(l.get("description") or "").strip(), criteres=(l.get("criteres") or "").strip())
                creees += 1
        return Response({"creees": creees, "ignorees": len(lignes) - creees}, status=201)

    def perform_create(self, serializer):
        self._controler_personnel()
        serializer.save()

    def perform_update(self, serializer):
        self._controler_personnel()
        serializer.save()


class NiveauViewSet(Base, mixins.ListModelMixin, mixins.UpdateModelMixin):
    serializer_class = NiveauSerializer
    pagination_class = None
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        school = get_request_school(self.request)
        if school is None:
            return NiveauMaitrise.objects.none()
        return services.assurer_niveaux(school)

    def perform_update(self, serializer):
        if self.request.user.role_level < 80:
            raise PermissionDenied("Réservé à l'administration.")
        serializer.save()


class ParEleveMixin:
    """Liste filtrée sur les élèves visibles ; écritures soumises à controler_ecriture."""

    champ_date = None

    def filtrer(self, qs):
        qs = qs.filter(student__in=eleves_visibles(self.request))
        eleve = self.request.query_params.get("student")
        if eleve:
            qs = qs.filter(student_id=identifiant(eleve))
        return qs


class EvaluationCompetenceViewSet(ParEleveMixin, Base, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin):
    """Ajout seul : ni modification ni suppression. Seule la décision sur une proposition change l'état."""

    serializer_class = EvaluationCompetenceSerializer
    filterset_fields = ["competence", "statut"]

    def get_queryset(self):
        qs = self.filtrer(EvaluationCompetence.objects.select_related("competence", "niveau", "evalue_par"))
        if est_famille(self.request.user):
            qs = qs.filter(statut=EvaluationCompetence.VALIDEE)
        return qs

    def create(self, request, *args, **kwargs):
        donnees = request.data.copy()
        if "preuve" in request.FILES:
            checked_upload(request.FILES["preuve"])
        serializer = self.get_serializer(data=donnees)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        controler_ecriture(request, data["student"], data["competence"].subject or data["competence"].referentiel.subject)
        serializer.save(evalue_par=request.user, decide_par=request.user, decide_le=timezone.now())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def lot(self, request):
        """Évaluation collective ou de plusieurs compétences. Tout ou rien, chaque ligne contrôlée."""
        lignes = request.data.get("lignes")
        date_evaluation = _periode({"date": request.data.get("date")}, "date", "date")[0]
        if not isinstance(lignes, list) or not lignes or date_evaluation is None:
            raise ValidationError({"detail": "Indiquez la date et au moins une évaluation."})
        school = _ecole(request)
        a_creer = []
        for ligne in lignes:
            if not isinstance(ligne, dict):
                raise ValidationError({"lignes": "Ligne invalide."})
            student = get_object_or_404(eleves_visibles(request), pk=identifiant(ligne.get("student")))
            competence = get_object_or_404(Competence, pk=identifiant(ligne.get("competence")), referentiel__school=school, actif=True)
            niveau = get_object_or_404(NiveauMaitrise, pk=identifiant(ligne.get("niveau")), school=school)
            controler_ecriture(request, student, competence.subject or competence.referentiel.subject)
            a_creer.append(EvaluationCompetence(
                student=student, competence=competence, niveau=niveau, date_evaluation=date_evaluation,
                commentaire=text_field(ligne, "commentaire"), evalue_par=request.user, decide_par=request.user, decide_le=timezone.now()))
        with transaction.atomic():
            for e in a_creer:
                e.save()
        return Response({"creees": len(a_creer)}, status=201)

    @action(detail=True, methods=["post"])
    def decider(self, request, pk=None):
        """Valide ou refuse une proposition. La ligne reste, avec sa décision."""
        with transaction.atomic():
            ligne = get_object_or_404(EvaluationCompetence.objects.select_for_update(of=("self",)),
                                      pk=self.get_object().pk)
            controler_ecriture(request, ligne.student, ligne.competence.subject or ligne.competence.referentiel.subject)
            decision = text_field(request.data, "decision")
            if decision not in (EvaluationCompetence.VALIDEE, EvaluationCompetence.REFUSEE):
                raise ValidationError({"decision": "Valeur attendue : validee ou refusee."})
            if ligne.statut != EvaluationCompetence.PROPOSEE:
                raise ValidationError({"detail": "Cette évaluation a déjà été décidée."})
            niveau = identifiant(request.data.get("niveau"))
            if niveau:
                ligne.niveau = get_object_or_404(NiveauMaitrise, pk=niveau, school=ligne.student.school)
            ligne.statut, ligne.decide_par, ligne.decide_le = decision, request.user, timezone.now()
            ligne.save(update_fields=["statut", "niveau", "decide_par", "decide_le"])
        return Response(self.get_serializer(ligne).data)


class EcritureEleveMixin:
    """Création et modification : l'écriture suit le périmètre de l'élève et de la matière."""

    auteur = "evalue_par"

    def perform_create(self, serializer):
        data = serializer.validated_data
        controler_ecriture(self.request, data["student"], data.get("subject"))
        serializer.save(**{self.auteur: self.request.user})

    def perform_update(self, serializer):
        instance = serializer.instance
        controler_ecriture(self.request, instance.student, serializer.validated_data.get("subject", instance.subject))
        if "student" in serializer.validated_data and serializer.validated_data["student"] != instance.student:
            raise ValidationError({"student": "L'élève ne peut pas changer."})
        serializer.save()


class EvaluationPedagogiqueViewSet(EcritureEleveMixin, ParEleveMixin, Base, viewsets.ModelViewSet):
    serializer_class = EvaluationPedagogiqueSerializer
    filterset_fields = ["subject", "type"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return self.filtrer(EvaluationPedagogique.objects.all())


class ObservationViewSet(EcritureEleveMixin, ParEleveMixin, Base, viewsets.ModelViewSet):
    serializer_class = ObservationSerializer
    auteur = "observe_par"
    filterset_fields = ["subject"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = self.filtrer(ObservationParticipation.objects.all())
        return qs.none() if est_famille(self.request.user) else qs


class ObjectifViewSet(Base, viewsets.ModelViewSet):
    serializer_class = ObjectifSerializer
    filterset_fields = ["statut", "subject", "class_obj", "priorite"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        request = self.request
        school = get_request_school(request)
        eleves = eleves_visibles(request)
        visibles = Q(student__in=eleves) | Q(class_obj_id__in=eleves.values("current_class_id"))
        if request.user.is_teacher():
            teacher = getattr(request.user, "teacher_profile", None)
            if teacher is not None:
                visibles |= Q(class_obj__in=teacher.classes.all())
        qs = Objectif.objects.filter(visibles, school=school).select_related("subject", "competence", "responsable").prefetch_related(
            "actions", "historique__par").distinct()
        if est_famille(request.user):
            qs = qs.filter(archive_le__isnull=True)
        elif self.action == "list":
            qs = qs.filter(archive_le__isnull=request.query_params.get("archives") != "1")
        eleve = request.query_params.get("student")
        if eleve:
            eleve_id = identifiant(eleve)
            classe = eleves.filter(pk=eleve_id).values("current_class_id")
            qs = qs.filter(Q(student_id=eleve_id) | Q(class_obj_id__in=classe))
        return qs

    def _controler(self, data, instance=None):
        request = self.request
        student = data.get("student", getattr(instance, "student", None))
        classe = data.get("class_obj", getattr(instance, "class_obj", None))
        subject = data.get("subject", getattr(instance, "subject", None))
        if student:
            controler_ecriture(request, student, subject)
            return
        if est_famille(request.user) or request.user.role_level < 50:
            raise PermissionDenied("Réservé au personnel de l'académie.")
        if request.user.is_teacher():
            teacher = getattr(request.user, "teacher_profile", None)
            if teacher is None or not teacher.classes.filter(pk=classe.pk).exists():
                raise PermissionDenied("Cette classe n'est pas dans votre périmètre.")

    def perform_create(self, serializer):
        self._controler(serializer.validated_data)
        with transaction.atomic():
            objectif = serializer.save(school=_ecole(self.request), created_by=self.request.user)
            ObjectifHistorique.objects.create(objectif=objectif, nouveau_statut=objectif.statut, par=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        self._controler(serializer.validated_data, instance)
        ancien = instance.statut
        modifies = [c for c, v in serializer.validated_data.items() if c != "statut" and getattr(instance, c) != v]
        with transaction.atomic():
            objectif = serializer.save()
            if objectif.statut != ancien:
                ObjectifHistorique.objects.create(objectif=objectif, ancien_statut=ancien, nouveau_statut=objectif.statut,
                                                  note=text_field(self.request.data, "note"), par=self.request.user)
            if modifies:
                ObjectifHistorique.objects.create(objectif=objectif, ancien_statut=objectif.statut, nouveau_statut=objectif.statut,
                                                  note=f"Modifié : {', '.join(c.replace('_', ' ') for c in modifies)}", par=self.request.user)

    def _archivage(self, date, note):
        objectif = self.get_object()
        self._controler({}, objectif)
        with transaction.atomic():
            objectif.archive_le = date
            objectif.save(update_fields=["archive_le", "updated_at"])
            ObjectifHistorique.objects.create(objectif=objectif, ancien_statut=objectif.statut, nouveau_statut=objectif.statut,
                                              note=note, par=self.request.user)
        return Response(self.get_serializer(objectif).data)

    @action(detail=True, methods=["post"])
    def archiver(self, request, pk=None):
        return self._archivage(timezone.now(), "Archivé")

    @action(detail=True, methods=["post"])
    def desarchiver(self, request, pk=None):
        return self._archivage(None, "Sorti des archives")


class PlanViewSet(EcritureEleveMixin, ParEleveMixin, Base, viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    auteur = "created_by"
    filterset_fields = ["statut"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = self.filtrer(PlanAccompagnement.objects.prefetch_related("actions"))
        if est_famille(self.request.user):
            qs = qs.filter(partage_famille=True)
        return qs

    def perform_update(self, serializer):
        controler_ecriture(self.request, serializer.instance.student)
        serializer.save()

    def perform_create(self, serializer):
        controler_ecriture(self.request, serializer.validated_data["student"])
        serializer.save(created_by=self.request.user)


class ActionViewSet(Base, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.RetrieveModelMixin):
    serializer_class = ActionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        eleves = eleves_visibles(self.request)
        qs = ActionPedagogique.objects.filter(
            Q(plan__student__in=eleves) | Q(objectif__student__in=eleves)
            | Q(objectif__class_obj_id__in=eleves.values("current_class_id"))
            | Q(objectif__school=get_request_school(self.request), objectif__class_obj__isnull=False,
                objectif__class_obj__in=self._classes_enseignant()))
        return qs.none() if est_famille(self.request.user) else qs.distinct()

    def _classes_enseignant(self):
        teacher = getattr(self.request.user, "teacher_profile", None)
        return teacher.classes.all() if teacher else []

    def _controler(self, objectif, plan):
        request = self.request
        school = _ecole(request)
        if plan:
            if plan.student.school_id != school.pk:
                raise PermissionDenied("Hors de votre académie.")
            controler_ecriture(request, plan.student)
        elif objectif.student:
            if objectif.school_id != school.pk:
                raise PermissionDenied("Hors de votre académie.")
            controler_ecriture(request, objectif.student, objectif.subject)
        else:
            if objectif.school_id != school.pk or est_famille(request.user) or request.user.role_level < 50:
                raise PermissionDenied("Hors de votre périmètre.")
            if request.user.is_teacher() and objectif.class_obj not in self._classes_enseignant():
                raise PermissionDenied("Cette classe n'est pas dans votre périmètre.")

    def perform_create(self, serializer):
        data = serializer.validated_data
        self._controler(data.get("objectif"), data.get("plan"))
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        self._controler(serializer.instance.objectif, serializer.instance.plan)
        serializer.save()


class EleveViewSet(Base):
    """Élèves visibles, fiche individuelle et comparaison de périodes."""

    def _eleve(self, pk):
        return get_object_or_404(eleves_visibles(self.request), pk=identifiant(pk))

    def list(self, request):
        eleves = eleves_visibles(request).select_related("current_class").order_by("last_name", "first_name")
        classe = identifiant(request.query_params.get("classe"))
        if classe:
            eleves = eleves.filter(current_class_id=classe)
        page = self.paginate_queryset(eleves)
        lignes = [{"id": e.pk, "nom": e.get_full_name(), "matricule": e.matricule, "classe": e.current_class_id,
                   "classe_nom": e.current_class.name if e.current_class else None,
                   "progression": services.progression(e)["valeur"]} for e in page]
        return self.get_paginated_response(lignes)

    @action(detail=True, methods=["get"])
    def fiche(self, request, pk=None):
        eleve = self._eleve(pk)
        du, au = _periode(request.query_params)
        donnees = services.fiche(eleve, du, au, identifiant(request.query_params.get("subject")),
                                 famille=est_famille(request.user))
        if est_famille(request.user):
            donnees.pop("participation", None)
        donnees["eleve"] = {"id": eleve.pk, "nom": eleve.get_full_name(), "matricule": eleve.matricule,
                            "classe": eleve.current_class.name if eleve.current_class else None,
                            "sans_classe": eleve.current_class_id is None}
        donnees["periode"] = {"du": du, "au": au}
        return Response(donnees)

    @action(detail=True, methods=["get"])
    def comparer(self, request, pk=None):
        eleve = self._eleve(pk)
        a = _periode(request.query_params, "a_du", "a_au")
        b = _periode(request.query_params, "b_du", "b_au")
        if None in a or None in b:
            raise ValidationError({"detail": "Indiquez les deux périodes : a_du, a_au, b_du, b_au."})
        return Response(services.comparer(eleve, a, b, identifiant(request.query_params.get("subject"))))


class ParametresViewSet(Base):
    def list(self, request):
        return Response(ParametresSerializer(services.parametres(_ecole(request))).data)

    @action(detail=False, methods=["patch"], url_path="modifier", permission_classes=[IsAuthenticated, IsAdminOrAbove, HasEntityFeature])
    def modifier(self, request):
        serializer = ParametresSerializer(services.parametres(_ecole(request)), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RapportViewSet(Base, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Une famille ne lit que la dernière version publiée, jamais un brouillon."""

    serializer_class = RapportSerializer
    filterset_fields = ["student", "statut", "type"]

    def get_queryset(self):
        qs = RapportPedagogique.objects.filter(student__in=eleves_visibles(self.request)).select_related("student").prefetch_related("versions")
        if est_famille(self.request.user):
            qs = qs.filter(versions__statut=RapportPedagogique.PUBLIE).distinct()
        return qs

    def retrieve(self, request, *args, **kwargs):
        return Response(self._vue(self.get_object()))

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response([self._vue(r) for r in page])

    def _vue(self, rapport):
        base = {"id": rapport.pk, "student": rapport.student_id, "type": rapport.type, "du": rapport.du, "au": rapport.au}
        if est_famille(self.request.user):
            v = rapports.version_publiee(rapport)
            return {**base, "statut": v.statut, "numero_version": v.numero, "donnees": v.donnees, "contenu": v.contenu, "versions": []}
        return {**RapportSerializer(rapport).data}

    def create(self, request):
        student = get_object_or_404(eleves_visibles(request), pk=identifiant(request.data.get("student")))
        controler_ecriture(request, student)
        du, au = _periode(request.data)
        if not du or not au:
            raise ValidationError({"detail": "Indiquez le début et la fin de la période."})
        type_rapport = text_field(request.data, "type") or "mensuel"
        if type_rapport not in dict(RapportPedagogique.TYPES):
            raise ValidationError({"type": "Type inconnu."})
        return Response(self._vue(rapports.generer(student, type_rapport, du, au, request.user)), status=201)

    def _action(self, fn, pk):
        rapport = self.get_object()
        controler_ecriture(self.request, rapport.student)
        return Response(self._vue(fn(rapport, self.request.user)))

    def partial_update(self, request, pk=None):
        rapport = self.get_object()
        controler_ecriture(request, rapport.student)
        return Response(self._vue(rapports.modifier(rapport, request.data.get("contenu"), request.user)))

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        return self._action(rapports.valider, pk)

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        rapport = self.get_object()
        controler_ecriture(request, rapport.student)
        rapport = rapports.publier(rapport, request.user)
        # Notification seulement si l'académie a ouvert le suivi aux familles.
        if entity_has_feature(rapport.student.school, "suivi_familles"):
            destinataires = [rapport.student.user] + [l.parent.user for l in rapport.student.parents.select_related("parent__user")]
            for compte in filter(None, destinataires):
                create_notification(compte, "announcement", "Nouveau rapport pédagogique", f"Période du {rapport.du} au {rapport.au}.")
        return Response(self._vue(rapport))

    @action(detail=True, methods=["post"])
    def nouvelle_version(self, request, pk=None):
        return self._action(rapports.nouvelle_version, pk)

    @action(detail=True, methods=["get"], url_path="pdf")
    def telecharger(self, request, pk=None):
        rapport = self.get_object()
        if est_famille(request.user):
            v = rapports.version_publiee(rapport)
            contenu = rapports.pdf(v.donnees, v.contenu, v.numero)
        else:
            contenu = rapports.pdf(rapport.donnees, rapport.contenu, rapport.numero_version)
        reponse = HttpResponse(contenu, content_type="application/pdf")
        reponse["Content-Disposition"] = f'attachment; filename="rapport-{rapport.pk}.pdf"'
        return reponse


class AlerteViewSet(Base, mixins.ListModelMixin):
    """File de l'enseignant. Les familles n'y ont pas accès."""

    serializer_class = AlerteSerializer
    filterset_fields = ["statut", "categorie", "student"]

    def get_queryset(self):
        _reserve_personnel(self.request)
        return AlertePedagogique.objects.filter(student__in=eleves_visibles(self.request)).select_related("student")

    @action(detail=True, methods=["post"])
    def decider(self, request, pk=None):
        alerte = get_object_or_404(self.get_queryset(), pk=identifiant(pk))
        controler_ecriture(request, alerte.student)
        decision = text_field(request.data, "decision")
        if decision not in ("acceptee", "modifiee", "refusee"):
            raise ValidationError({"decision": "Valeur attendue : acceptee, modifiee ou refusee."})
        if alerte.statut != "nouvelle":
            raise ValidationError({"detail": "Déjà décidée."})
        if decision == "modifiee":
            alerte.recommandation = text_field(request.data, "recommandation") or alerte.recommandation
        alerte.statut, alerte.decide_par, alerte.decide_le = decision, request.user, timezone.now()
        alerte.note_decision = text_field(request.data, "note")
        alerte.save()
        return Response(self.get_serializer(alerte).data)

    @action(detail=False, methods=["post"])
    def detecter(self, request):
        _reserve_personnel(request)
        return Response({"nouvelles": alertes.detecter_academie(_ecole(request))})

    @action(detail=False, methods=["get", "patch"], url_path="regles")
    def regles(self, request):
        _reserve_personnel(request)
        school = _ecole(request)
        alertes.regles(school)
        if request.method == "PATCH":
            if request.user.role_level < 80:
                raise PermissionDenied("Réservé à l'administration.")
            regle = get_object_or_404(RegleAlerte, school=school, code=text_field(request.data, "code"))
            serializer = RegleSerializer(regle, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(RegleSerializer(RegleAlerte.objects.filter(school=school), many=True).data)


class ActivationViewSet(viewsets.GenericViewSet):
    """Superadministrateur : ouvre ou ferme les modules pédagogiques, académie par académie."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    DRAPEAUX = ("suivi_pedagogique", "suivi_familles", "evaluations_en_ligne")

    def list(self, request):
        return Response([
            {"id": s.pk, "nom": s.name, **{d: s.has_feature(d) for d in self.DRAPEAUX}}
            for s in School.objects.order_by("name")
        ])

    def partial_update(self, request, pk=None):
        ecole = get_object_or_404(School, pk=identifiant(pk))
        changements = {d: request.data[d] for d in self.DRAPEAUX if d in request.data}
        if not changements or any(not isinstance(v, bool) for v in changements.values()):
            raise ValidationError({"detail": "Indiquez un drapeau et une valeur vraie ou fausse."})
        with transaction.atomic():
            ecole = School.objects.select_for_update().get(pk=ecole.pk)
            reglages = dict(ecole.settings or {})
            reglages["features"] = {**(reglages.get("features") or {}), **changements}
            ecole.settings = reglages
            ecole.save(update_fields=["settings"])
        logger.info("Modules pédagogiques de l'académie %s modifiés par l'utilisateur %s : %s", ecole.pk, request.user.pk, changements)
        return Response({"id": ecole.pk, "nom": ecole.name, **{d: ecole.has_feature(d) for d in self.DRAPEAUX}})
