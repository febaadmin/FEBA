"""API des examens en ligne. Le corrigé ne quitte jamais le serveur vers un élève pendant l'épreuve."""
import csv
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.features import HasEntityFeature, entity_has_feature
from apps.core.request_text import checked_upload, identifiant, text_field
from apps.core.tenancy import get_request_school
from apps.students.models import Student
from apps.teachers.affectations import paires_autorisees

from . import services
from .models import Amenagement, Epreuve, EpreuveQuestion, Question, QuestionVersion, Tentative
from .serializers import AmenagementSerializer, CopieSerializer, EpreuveSerializer, QuestionSerializer

CHAMPS_VERSION = ("enonce", "contenu", "corrige", "criteres", "explication", "points", "media", "media_type")


def _ecole(request):
    school = get_request_school(request)
    if school is None:
        raise ValidationError({"detail": "Sélectionnez une académie."})
    return school


def _personnel(request):
    if request.user.role_level < 50:
        raise PermissionDenied("Réservé au personnel de l'académie.")


class Base(viewsets.GenericViewSet):
    required_feature = "evaluations_en_ligne"
    permission_classes = [IsAuthenticated, HasEntityFeature]

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        contexte["school"] = get_request_school(self.request)
        return contexte


class QuestionViewSet(Base, viewsets.ModelViewSet):
    serializer_class = QuestionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["subject", "level", "difficulte", "type", "archive", "competences"]

    def get_queryset(self):
        _personnel(self.request)
        qs = Question.objects.filter(school=get_request_school(self.request)).select_related("subject").prefetch_related("versions", "competences")
        if self.request.user.role_level < 80:
            qs = qs.filter(Q(prive=False) | Q(auteur=self.request.user))
        return qs

    def _ecrire(self, serializer, creation):
        donnees = {c: serializer.validated_data.pop(c) for c in CHAMPS_VERSION if c in serializer.validated_data}
        if donnees.get("media"):
            checked_upload(donnees["media"])
        with transaction.atomic():
            if creation:
                question = serializer.save(school=_ecole(self.request), auteur=self.request.user)
            else:
                question = serializer.save()
            if creation or donnees:
                courant = question.version_courante
                base = {c: getattr(courant, c) for c in CHAMPS_VERSION} if courant else {}
                services.creer_version(question, {**base, **donnees}, self.request.user)

    def perform_create(self, serializer):
        _personnel(self.request)
        self._ecrire(serializer, True)

    def perform_update(self, serializer):
        self._controler_auteur(serializer.instance)
        self._ecrire(serializer, False)

    def _controler_auteur(self, question):
        if self.request.user.role_level < 80 and question.auteur_id != self.request.user.pk:
            raise PermissionDenied("Seul l'auteur modifie cette question ; dupliquez-la.")

    @action(detail=True, methods=["post"])
    def archiver(self, request, pk=None):
        question = self.get_object()
        self._controler_auteur(question)
        question.archive = bool(request.data.get("archive", True))
        question.save(update_fields=["archive"])
        return Response(self.get_serializer(question).data)

    @action(detail=True, methods=["post"])
    def dupliquer(self, request, pk=None):
        source = self.get_object()
        version = source.version_courante
        with transaction.atomic():
            copie = Question.objects.create(school=source.school, auteur=request.user, subject=source.subject,
                                            level=source.level, type=source.type, difficulte=source.difficulte, prive=source.prive)
            copie.competences.set(source.competences.all())
            services.creer_version(copie, {c: getattr(version, c) for c in CHAMPS_VERSION}, request.user)
        return Response(self.get_serializer(copie).data, status=201)

    @action(detail=False, methods=["get"])
    def exporter(self, request):
        sortie = io.StringIO()
        ecrivain = csv.writer(sortie)
        ecrivain.writerow(["type", "enonce", "points", "difficulte", "choix", "bonnes"])
        for q in self.get_queryset().filter(archive=False):
            v = q.version_courante
            choix = "|".join(c.get("texte", "") for c in (v.contenu or {}).get("choix", []))
            bonnes = v.corrige.get("bonnes") or [v.corrige.get("bonne", v.corrige.get("valeur", ""))]
            ligne = [q.type, v.enonce, v.points, q.difficulte, choix, "|".join(str(b) for b in bonnes)]
            # Un tableur exécuterait une cellule commençant par ces signes.
            ecrivain.writerow([f"'{c}" if str(c)[:1] in "=+-@" else c for c in ligne])
        reponse = HttpResponse(sortie.getvalue(), content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="questions.csv"'
        return reponse

    @action(detail=False, methods=["post"])
    def importer(self, request):
        """CSV : type, enonce, points, difficulte, choix (a|b|c), bonnes (a|b). Tout ou rien."""
        _personnel(request)
        fichier = request.FILES.get("fichier")
        if fichier is None or fichier.size > 2_000_000:
            raise ValidationError({"fichier": "Fichier CSV de 2 Mo au plus attendu."})
        try:
            lignes = list(csv.DictReader(io.StringIO(fichier.read().decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error):
            raise ValidationError({"fichier": "CSV illisible : enregistrez-le en UTF-8."})
        subject = identifiant(request.data.get("subject"))
        school = _ecole(request)
        erreurs, a_creer = [], []
        for numero, l in enumerate(lignes, 2):
            try:
                type_q = (l.get("type") or "").strip()
                textes = [c.strip() for c in (l.get("choix") or "").split("|") if c.strip()]
                bonnes = [b.strip() for b in (l.get("bonnes") or "").split("|") if b.strip()]
                contenu = {"choix": [{"id": f"c{i}", "texte": t} for i, t in enumerate(textes)]} if textes else {}
                ids = {t: f"c{i}" for i, t in enumerate(textes)}
                if type_q == "qcm_unique":
                    corrige = {"bonne": ids.get(bonnes[0]) if bonnes else None}
                elif type_q == "qcm_multiple":
                    corrige = {"bonnes": [ids[b] for b in bonnes]}
                elif type_q == "vrai_faux":
                    corrige = {"valeur": bonnes[0].lower() in ("vrai", "true", "oui")}
                elif type_q == "courte":
                    corrige = {"acceptees": bonnes}
                elif type_q == "ouverte":
                    corrige = {}
                else:
                    raise ValueError("type non pris en charge")
                points = Decimal((l.get("points") or "1").replace(",", "."))
                difficulte = int(l.get("difficulte") or 2)
                if not (l.get("enonce") or "").strip() or difficulte not in (1, 2, 3) or points < 0:
                    raise ValueError("ligne incomplète")
                from .correction import valider_question
                problemes = valider_question(type_q, contenu, corrige)
                if problemes:
                    raise ValueError(problemes[0])
                a_creer.append((type_q, l["enonce"].strip(), contenu, corrige, points, difficulte))
            except (ValueError, KeyError, IndexError, InvalidOperation) as exc:
                erreurs.append(f"Ligne {numero} : {exc}")
        if erreurs:
            raise ValidationError({"lignes": erreurs[:20]})
        if subject and not school.subjects.filter(pk=subject).exists():
            raise ValidationError({"subject": "Hors de votre académie."})
        with transaction.atomic():
            for type_q, enonce, contenu, corrige, points, difficulte in a_creer:
                q = Question.objects.create(school=school, auteur=request.user, subject_id=subject, type=type_q, difficulte=difficulte)
                services.creer_version(q, {"enonce": enonce, "contenu": contenu, "corrige": corrige, "points": points}, request.user)
        return Response({"importees": len(a_creer)}, status=201)


class EpreuveViewSet(Base, viewsets.ModelViewSet):
    serializer_class = EpreuveSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["statut", "class_obj", "subject", "type"]

    def get_queryset(self):
        _personnel(self.request)
        qs = Epreuve.objects.filter(school=get_request_school(self.request)).select_related("subject", "class_obj").prefetch_related("questions__version__question")
        if self.request.user.is_teacher():
            teacher = getattr(self.request.user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            qs = qs.filter(Q(responsable=self.request.user) | Q(class_obj__in=teacher.classes.all())).distinct()
        return qs

    def _droit(self, classe, subject):
        user = self.request.user
        if user.role_level < 50:
            raise PermissionDenied("Réservé au personnel de l'académie.")
        if user.is_teacher():
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None or (classe.pk, subject.pk) not in paires_autorisees(teacher):
                raise PermissionDenied(f"Vous n'êtes pas affecté à {subject.name} dans cette classe.")

    def _droit_sur(self, epreuve):
        self._droit(epreuve.class_obj, epreuve.subject)

    def _brouillon(self, epreuve):
        if epreuve.statut != Epreuve.BROUILLON:
            raise ValidationError({"detail": "Une épreuve publiée ne se modifie plus."})

    def perform_create(self, serializer):
        d = serializer.validated_data
        self._droit(d["class_obj"], d["subject"])
        serializer.save(school=_ecole(self.request), created_by=self.request.user, responsable=self.request.user)

    def perform_update(self, serializer):
        epreuve = serializer.instance
        self._brouillon(epreuve)
        self._droit(serializer.validated_data.get("class_obj", epreuve.class_obj), serializer.validated_data.get("subject", epreuve.subject))
        serializer.save()

    def perform_destroy(self, instance):
        self._droit_sur(instance)
        self._brouillon(instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def ajouter_question(self, request, pk=None):
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        self._brouillon(epreuve)
        visibles = Question.objects.filter(school=epreuve.school, archive=False)
        if request.user.role_level < 80:
            visibles = visibles.filter(Q(prive=False) | Q(auteur=request.user))
        question = get_object_or_404(visibles, pk=identifiant(request.data.get("question")))
        version = question.version_courante
        try:
            points = Decimal(str(request.data.get("points", version.points)))
        except InvalidOperation:
            raise ValidationError({"points": "Nombre attendu."})
        if points < 0:
            raise ValidationError({"points": "Nombre positif attendu."})
        ligne, _ = EpreuveQuestion.objects.get_or_create(
            epreuve=epreuve, version=version, defaults={"points": points, "ordre": epreuve.questions.count() + 1})
        return Response({"id": ligne.pk}, status=201)

    @action(detail=True, methods=["post"])
    def retirer_question(self, request, pk=None):
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        self._brouillon(epreuve)
        get_object_or_404(epreuve.questions, pk=identifiant(request.data.get("ligne"))).delete()
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        return Response(self.get_serializer(services.publier(epreuve)).data)

    @action(detail=True, methods=["post"])
    def fermer(self, request, pk=None):
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        if epreuve.statut != Epreuve.PUBLIEE:
            raise ValidationError({"detail": "Seule une épreuve publiée peut être close."})
        epreuve.statut = Epreuve.CLOSE
        epreuve.save(update_fields=["statut", "updated_at"])
        for t in epreuve.tentatives.filter(statut=Tentative.EN_COURS):
            services.remettre(t, "auto")
        return Response(self.get_serializer(epreuve).data)

    @action(detail=True, methods=["post"])
    def publier_resultats(self, request, pk=None):
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        if epreuve.statut == Epreuve.BROUILLON:
            raise ValidationError({"detail": "L'épreuve n'est pas publiée."})
        epreuve.resultats_publies = bool(request.data.get("publies", True))
        epreuve.save(update_fields=["resultats_publies", "updated_at"])
        return Response(self.get_serializer(epreuve).data)

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        return Response(services.statistiques(self.get_object()))

    @action(detail=True, methods=["get"])
    def copies(self, request, pk=None):
        epreuve = self.get_object()
        qs = epreuve.tentatives.select_related("student").prefetch_related("transferts").order_by("student__last_name", "numero")
        return Response(CopieSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def exporter_resultats(self, request, pk=None):
        epreuve = self.get_object()
        sortie = io.StringIO()
        ecrivain = csv.writer(sortie)
        ecrivain.writerow(["eleve", "tentative", "statut", "points", "total", "pourcentage", "note"])
        for t in epreuve.tentatives.select_related("student").order_by("student__last_name", "numero"):
            nom = t.student.get_full_name()
            ecrivain.writerow([f"'{nom}" if nom[:1] in "=+-@" else nom, t.numero, t.statut,
                               t.score_valide if t.score_valide is not None else t.score_corrige, t.total_points, t.pourcentage, t.note_echelle])
        reponse = HttpResponse(sortie.getvalue(), content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = f'attachment; filename="resultats-{epreuve.pk}.csv"'
        return reponse

    @action(detail=True, methods=["post"])
    def amenagement(self, request, pk=None):
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        serializer = AmenagementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.validated_data["student"]
        if student.school_id != epreuve.school_id:
            raise ValidationError({"student": "Hors de votre académie."})
        ligne, _ = Amenagement.objects.update_or_create(epreuve=epreuve, student=student, defaults={
            "minutes_sup": serializer.validated_data.get("minutes_sup", 0),
            "tentatives_sup": serializer.validated_data.get("tentatives_sup", 0)})
        return Response(AmenagementSerializer(ligne).data, status=201)

    @action(detail=True, methods=["post"])
    def transferer(self, request, pk=None):
        """Transfert explicite vers le module de notes : un élève, ou tous les élèves validés."""
        epreuve = self.get_object()
        self._droit_sur(epreuve)
        ident = identifiant(request.data.get("student"))
        eleves = Student.objects.filter(pk__in=epreuve.tentatives.filter(statut=Tentative.VALIDEE).values("student_id"))
        if ident:
            eleves = eleves.filter(pk=ident)
        crees, deja, erreurs = 0, 0, []
        for eleve in eleves:
            try:
                _, nouveau = services.transferer(epreuve, eleve, request.user)
                crees, deja = crees + int(nouveau), deja + int(not nouveau)
            except (ValidationError, PermissionDenied) as exc:
                erreurs.append({"student": eleve.pk, "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail)})
        return Response({"crees": crees, "deja_transferes": deja, "erreurs": erreurs})


class CopieViewSet(Base, mixins.RetrieveModelMixin):
    """Correction d'une tentative par le personnel."""

    serializer_class = CopieSerializer

    def get_queryset(self):
        _personnel(self.request)
        qs = Tentative.objects.filter(epreuve__school=get_request_school(self.request)).select_related("student", "epreuve")
        if self.request.user.is_teacher():
            teacher = getattr(self.request.user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            qs = qs.filter(Q(epreuve__responsable=self.request.user) | Q(epreuve__class_obj__in=teacher.classes.all()))
        return qs

    def retrieve(self, request, *args, **kwargs):
        copie = self.get_object()
        versions = QuestionVersion.objects.select_related("question").in_bulk([s["version"] for s in copie.sujet])
        reponses = {r.version_id: r for r in copie.reponses.prefetch_related("historique")}
        lignes = []
        for s in copie.sujet:
            v, r = versions[s["version"]], reponses.get(s["version"])
            lignes.append({
                "version": v.pk, "type": v.question.type, "enonce": v.enonce, "contenu": v.contenu, "corrige": v.corrige,
                "criteres": v.criteres, "maximum": s["points"], "reponse": r.pk if r else None,
                "valeur": r.valeur if r else None, "fichier": r.fichier.url if r and r.fichier else None,
                "points_auto": r.points_auto if r else None, "points_manuel": r.points_manuel if r else None,
                "commentaire": r.commentaire if r else "",
                "historique": [{"avant": h.points_avant, "apres": h.points_apres, "le": h.created_at} for h in r.historique.all()] if r else [],
            })
        return Response({**CopieSerializer(copie).data, "epreuve": copie.epreuve_id, "lignes": lignes,
                         "evenements": list(copie.evenements.values("type", "donnees", "created_at"))})

    def _droit(self, copie):
        user = self.request.user
        if user.is_teacher() and (copie.student.current_class_id, copie.epreuve.subject_id) not in paires_autorisees(user.teacher_profile):
            raise PermissionDenied("Vous n'êtes pas affecté à cette matière dans la classe de cet élève.")

    @action(detail=True, methods=["post"])
    def corriger(self, request, pk=None):
        copie = self.get_object()
        self._droit(copie)
        reponse = get_object_or_404(copie.reponses, pk=identifiant(request.data.get("reponse")))
        try:
            points = Decimal(str(request.data.get("points")))
        except InvalidOperation:
            raise ValidationError({"points": "Nombre attendu."})
        services.corriger(reponse.pk, points, text_field(request.data, "commentaire"), request.user)
        copie.refresh_from_db()
        return Response(CopieSerializer(copie).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        copie = self.get_object()
        self._droit(copie)
        copie = services.valider(copie, request.user)
        propositions = 0
        if entity_has_feature(copie.epreuve.school, "suivi_pedagogique"):
            propositions = services.proposer_competences(copie)
        return Response({**CopieSerializer(copie).data, "propositions_competences": propositions})

    @action(detail=True, methods=["post"])
    def choisir(self, request, pk=None):
        """Politique « validee » : l'enseignant désigne la tentative retenue."""
        copie = self.get_object()
        self._droit(copie)
        with transaction.atomic():
            Tentative.objects.filter(epreuve=copie.epreuve, student=copie.student).update(choisie=False)
            Tentative.objects.filter(pk=copie.pk).update(choisie=True)
        return Response({"choisie": copie.pk})


def _presenter(tentative):
    """Sujet tel que l'élève le voit : ni corrigé, ni explication, ni critères."""
    versions = QuestionVersion.objects.select_related("question").in_bulk([s["version"] for s in tentative.sujet])
    reponses = {r.version_id: r for r in tentative.reponses.all()}
    questions = []
    for s in tentative.sujet:
        v = versions[s["version"]]
        contenu = {}
        source = v.contenu or {}
        for cle, ordre in s.get("ordre", {}).items():
            par_id = {c["id"]: c for c in source.get(cle, [])}
            contenu[cle] = [par_id[i] for i in ordre if i in par_id]
        if source.get("gauche"):
            contenu["gauche"] = source["gauche"]
        if source.get("texte"):
            contenu["texte"] = source["texte"]
        if source.get("nombre_trous"):
            contenu["nombre_trous"] = source["nombre_trous"]
        r = reponses.get(v.pk)
        questions.append({"version": v.pk, "type": v.question.type, "enonce": v.enonce, "contenu": contenu,
                          "points": s["points"], "media": v.media.url if v.media else None, "media_type": v.media_type,
                          "valeur": r.valeur if r else None, "a_fichier": bool(r and r.fichier)})
    return questions


class PassageViewSet(Base):
    """Espace de l'élève : ses épreuves, son passage, ses résultats publiés."""

    def _eleve(self):
        eleve = Student.objects.filter(user=self.request.user, school=get_request_school(self.request)).first()
        if eleve is None:
            raise PermissionDenied("Réservé aux élèves.")
        return eleve

    def _tentative(self, pk):
        return get_object_or_404(Tentative.objects.select_related("epreuve"), pk=identifiant(pk), student=self._eleve())

    def _etat(self, t):
        return {"id": t.pk, "statut": t.statut, "numero": t.numero, "secondes_restantes": max(0, int((t.echeance - _maintenant()).total_seconds())),
                "echeance": t.echeance, "jeton": str(t.jeton), "recu": str(t.recu) if t.remise_le else None,
                "remise_le": t.remise_le, "retour_autorise": t.epreuve.retour_autorise}

    def list(self, request):
        eleve = self._eleve()
        lignes = []
        for e in services.epreuves_ouvertes_pour(eleve).select_related("subject"):
            tentatives = e.tentatives.filter(student=eleve)
            lignes.append({"id": e.pk, "titre": e.titre, "type": e.type, "subject": e.subject.name, "ouverture": e.ouverture,
                           "fermeture": e.fermeture, "duree_minutes": e.duree_minutes, "tentatives_max": e.tentatives_max,
                           "consignes": e.consignes, "tentatives": tentatives.count(), "statut": e.statut,
                           "en_cours": tentatives.filter(statut=Tentative.EN_COURS).values_list("pk", flat=True).first(),
                           "resultats_publies": e.resultats_publies})
        return Response(lignes)

    @action(detail=True, methods=["post"])
    def demarrer(self, request, pk=None):
        eleve = self._eleve()
        epreuve = get_object_or_404(services.epreuves_ouvertes_pour(eleve), pk=identifiant(pk))
        ip = request.META.get("REMOTE_ADDR", "")
        tentative = services.demarrer(epreuve, eleve, ip)
        return Response({**self._etat(tentative), "questions": _presenter(tentative)})

    @action(detail=True, methods=["get"])
    def tentative(self, request, pk=None):
        t = self._tentative(pk)
        services.clore_si_echue(t)
        t.refresh_from_db()
        donnees = self._etat(t)
        if t.statut == Tentative.EN_COURS:
            donnees["questions"] = _presenter(t)
        return Response(donnees)

    @action(detail=True, methods=["post"])
    def repondre(self, request, pk=None):
        eleve = self._eleve()
        fichier = request.FILES.get("fichier")
        if fichier:
            checked_upload(fichier)
        version = identifiant(request.data.get("version"))
        t, _ = services.enregistrer_reponse(identifiant(pk), eleve, version, request.data.get("valeur"), request.data.get("jeton"), fichier)
        return Response(self._etat(t))

    @action(detail=True, methods=["post"])
    def remettre(self, request, pk=None):
        t = services.remettre(self._tentative(pk), "eleve")
        return Response(self._etat(t))

    @action(detail=True, methods=["post"])
    def evenement(self, request, pk=None):
        """Perte de connexion, sortie de fenêtre : signal pour l'enseignant, jamais une sanction."""
        t = self._tentative(pk)
        type_evenement = text_field(request.data, "type")
        if type_evenement not in ("perte_connexion", "reconnexion", "sortie_fenetre", "retour_fenetre"):
            raise ValidationError({"type": "Événement inconnu."})
        if t.statut == Tentative.EN_COURS:
            services.journal(t, type_evenement)
        return Response(status=204)

    @action(detail=False, methods=["get"])
    def resultats(self, request):
        """Résultats publiés : l'élève les siens ; un parent ceux de ses enfants, si l'académie l'a ouvert."""
        user = request.user
        school = _ecole(request)
        if user.is_parent():
            if not entity_has_feature(school, "suivi_familles"):
                raise PermissionDenied("Non ouvert aux familles par l'académie.")
            eleves = Student.objects.filter(school=school, parents__parent__user=user)
        else:
            eleves = Student.objects.filter(pk=self._eleve().pk)
        qs = Tentative.objects.filter(student__in=eleves, epreuve__resultats_publies=True, statut=Tentative.VALIDEE).select_related("epreuve", "student")
        return Response([{"id": t.pk, "eleve": t.student.get_full_name(), "epreuve": t.epreuve.titre, "numero": t.numero,
                          "note": t.note_echelle, "note_max": t.epreuve.note_max, "pourcentage": t.pourcentage,
                          "reussie": t.reussie, "remise_le": t.remise_le} for t in qs])

    @action(detail=True, methods=["get"])
    def resultat(self, request, pk=None):
        t = self._tentative(pk)
        if not (t.epreuve.resultats_publies and t.statut == Tentative.VALIDEE):
            raise PermissionDenied("Le résultat n'est pas encore publié.")
        versions = QuestionVersion.objects.select_related("question").in_bulk([s["version"] for s in t.sujet])
        reponses = {r.version_id: r for r in t.reponses.all()}
        lignes = [{"enonce": versions[s["version"]].enonce, "maximum": s["points"],
                   "points": reponses[s["version"]].points if s["version"] in reponses else None,
                   "commentaire": reponses[s["version"]].commentaire if s["version"] in reponses else "",
                   "explication": versions[s["version"]].explication} for s in t.sujet]
        return Response({"note": t.note_echelle, "note_max": t.epreuve.note_max, "pourcentage": t.pourcentage, "reussie": t.reussie, "lignes": lignes})


def _maintenant():
    from django.utils import timezone
    return timezone.now()


