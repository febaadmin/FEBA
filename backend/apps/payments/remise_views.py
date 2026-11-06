"""
apps/payments/remise_views.py — Remises, exonérations, échéanciers personnels, journal.

    /api/payments/regles-remise/                 liste, création
    /api/payments/regles-remise/<id>/            détail, modification (motif)
    /api/payments/regles-remise/<id>/annuler/    annulation (motif obligatoire) — jamais de suppression
    /api/payments/regles-remise/<id>/reactiver/  réactivation (motif obligatoire)
    /api/payments/regles-remise/<id>/impact/     élèves concernés et montants, calculés par le moteur
    /api/payments/echeanciers-eleves/            lecture ; POST : définir l'échéancier d'un élève
    /api/payments/echeanciers-eleves/retablir/   revenir à l'échéancier standard (motif)
    /api/payments/journal-financier/             historique (tarifs + décisions), filtrable

Administrateur de l'académie ou super administrateur sur une académie choisie.
Toute écriture est journalisée (auteur, date, avant, après, motif).
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.currency import Money, get_currency
from apps.core.request_text import date_field, identifiant

from .models import EcheanceEleve, FeeSchedule, JournalFinancier, Payment, RegleRemise
from .reminder_views import AcademyScopedMixin, _to_minor
from .reminders import type_label

CHAMPS_SUIVIS = ["nom", "description", "genre", "categorie", "mode", "pourcentage", "montant_minor", "school_year_id",
                 "payment_type", "level_id", "class_obj_id", "student_id", "famille_id", "debut", "fin",
                 "rang_enfant_min", "date_limite_paiement", "cumulable", "priorite", "actif", "justification",
                 "autorise_par_id"]


def _instantane(obj, champs):
    out = {}
    for c in champs:
        v = getattr(obj, c, None)
        out[c] = str(v) if isinstance(v, Decimal) else (v.isoformat() if hasattr(v, "isoformat") else v)
    return out


def journaliser(request, academy, objet, obj, action_, description, avant=None, apres=None, motif="", student=None):
    user = request.user
    return JournalFinancier.objects.create(
        academy=academy, objet=objet, objet_id=getattr(obj, "pk", None), student=student, action=action_,
        description=description[:255], avant=avant or {}, apres=apres or {}, motif=(motif or "")[:255],
        auteur=user if user.is_authenticated else None, auteur_email=getattr(user, "email", "") or "")


def _motif(request, obligatoire=False):
    valeur = request.data.get("motif")
    valeur = valeur.strip() if isinstance(valeur, str) else ""
    if obligatoire and not valeur:
        raise ValidationError({"motif": "Indiquez le motif."})
    return valeur


def decrire_regle(r):
    valeur = f"{r.pourcentage} %" if r.mode == r.POURCENTAGE else Money(r.montant_minor or 0, r.devise).formatted()
    return f"{r.get_genre_display()} « {r.nom} » ({valeur})"


class RegleSerializer(serializers.ModelSerializer):
    montant = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    montant_affiche = serializers.SerializerMethodField()
    montant_valeur = serializers.SerializerMethodField()
    genre_libelle = serializers.CharField(source="get_genre_display", read_only=True)
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    mode_libelle = serializers.CharField(source="get_mode_display", read_only=True)
    perimetre = serializers.SerializerMethodField()
    en_vigueur = serializers.BooleanField(read_only=True)
    cree_par_nom = serializers.SerializerMethodField()
    autorise_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = RegleRemise
        fields = ["id", "nom", "description", "genre", "genre_libelle", "categorie", "categorie_libelle", "mode",
                  "mode_libelle", "pourcentage", "montant", "montant_minor", "montant_valeur", "montant_affiche", "devise",
                  "school_year", "payment_type", "level", "class_obj", "student", "famille", "debut", "fin",
                  "rang_enfant_min", "date_limite_paiement", "cumulable", "priorite", "actif", "en_vigueur",
                  "justification", "autorise_par", "autorise_par_nom", "cree_par_nom", "cree_le", "modifie_le",
                  "annulee_le", "motif_annulation", "perimetre"]
        read_only_fields = ["montant_minor", "devise", "cree_le", "modifie_le", "annulee_le", "motif_annulation", "actif"]

    def get_montant_affiche(self, r):
        return f"{r.pourcentage} %" if r.mode == r.POURCENTAGE else Money(r.montant_minor or 0, r.devise).formatted()

    def get_montant_valeur(self, r):
        return str(get_currency(r.devise or r.academy.currency_code).to_decimal(r.montant_minor)) if r.montant_minor else None

    def get_cree_par_nom(self, r):
        return r.cree_par.get_full_name() if r.cree_par else ""

    def get_autorise_par_nom(self, r):
        return r.autorise_par.get_full_name() if r.autorise_par else ""

    def get_perimetre(self, r):
        parts = []
        if r.school_year_id:
            parts.append(r.school_year.name)
        if r.payment_type:
            parts.append(dict(Payment.PAYMENT_TYPES).get(r.payment_type, r.payment_type))
        if r.level_id:
            parts.append(r.level.name)
        if r.class_obj_id:
            parts.append(r.class_obj.name)
        if r.student_id:
            parts.append(r.student.get_full_name())
        if r.famille_id:
            parts.append(f"Famille {r.famille.user.get_full_name() if r.famille.user_id else r.famille_id}")
        return parts

    def validate_payment_type(self, valeur):
        if valeur and valeur not in dict(Payment.PAYMENT_TYPES):
            raise serializers.ValidationError("Nature de frais inconnue.")
        return valeur

    def validate(self, attrs):
        academy = self.context["academy"]
        for champ in ("school_year", "level", "class_obj", "student"):
            objet = attrs.get(champ)
            if objet is not None and objet.school_id != academy.pk:
                raise serializers.ValidationError({champ: "Élément d'une autre académie."})
        famille = attrs.get("famille")
        if famille is not None and not famille.children_links.filter(student__school=academy).exists():
            raise serializers.ValidationError({"famille": "Cette famille n'a pas d'enfant dans l'académie."})
        autorise = attrs.get("autorise_par")
        if autorise is not None and not (autorise.is_superadmin() or (autorise.is_admin() and autorise.school_id == academy.pk)):
            raise serializers.ValidationError({"autorise_par": "Seul un membre de l'administration peut autoriser."})
        return attrs

    def _appliquer(self, regle, validated):
        montant = validated.pop("montant", None)
        for k, v in validated.items():
            setattr(regle, k, v)
        if regle.mode == RegleRemise.MONTANT:
            if montant not in (None, ""):
                regle.montant_minor = _to_minor(montant, regle.academy.currency_code, "montant") or None
            regle.pourcentage = None
        else:
            regle.montant_minor = None
        try:
            regle.save()
        except Exception as exc:  # ValidationError du modèle : message lisible
            raise ValidationError(getattr(exc, "message_dict", None) or {"non_field_errors": [str(exc)]})
        return regle

    @transaction.atomic
    def create(self, validated):
        request = self.context["request"]
        regle = RegleRemise(academy=self.context["academy"], cree_par=request.user)
        if "autorise_par" not in validated:
            regle.autorise_par = request.user
        self._appliquer(regle, validated)
        journaliser(request, regle.academy, JournalFinancier.REGLE, regle, "creation", decrire_regle(regle),
                    apres=_instantane(regle, CHAMPS_SUIVIS), motif=_motif(request), student=regle.student)
        return regle

    @transaction.atomic
    def update(self, regle, validated):
        request = self.context["request"]
        if not regle.en_vigueur:
            raise ValidationError({"detail": "Une règle annulée ne se modifie pas : réactivez-la d'abord."})
        avant = _instantane(regle, CHAMPS_SUIVIS)
        self._appliquer(regle, validated)
        apres = _instantane(regle, CHAMPS_SUIVIS)
        changes = {k for k in apres if apres[k] != avant[k]}
        if changes:
            journaliser(request, regle.academy, JournalFinancier.REGLE, regle, "modification", decrire_regle(regle),
                        avant={k: avant[k] for k in changes}, apres={k: apres[k] for k in changes},
                        motif=_motif(request, obligatoire=True), student=regle.student)
        return regle


class RegleRemiseViewSet(AcademyScopedMixin, viewsets.ModelViewSet):
    serializer_class = RegleSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = (RegleRemise.objects.filter(academy=self.academy())
              .select_related("school_year", "level", "class_obj", "student", "famille__user", "cree_par", "autorise_par"))
        p = self.request.query_params
        if p.get("genre") in dict(RegleRemise.GENRES):
            qs = qs.filter(genre=p["genre"])
        if p.get("etat") == "en_vigueur":
            qs = qs.filter(actif=True, annulee_le__isnull=True)
        elif p.get("etat") == "annulees":
            qs = qs.filter(annulee_le__isnull=False)
        if (eleve := identifiant(p.get("eleve"))) is not None:
            qs = qs.filter(student_id=eleve)
        return qs.order_by("genre", "-actif", "nom", "pk")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "academy": self.academy()}

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def annuler(self, request, pk=None):
        regle = self.get_object()
        motif = _motif(request, obligatoire=True)
        if not regle.en_vigueur:
            return Response({"detail": "Règle déjà annulée."}, status=400)
        regle.actif, regle.annulee_le, regle.annulee_par, regle.motif_annulation = False, timezone.now(), request.user, motif
        regle.save()
        journaliser(request, regle.academy, JournalFinancier.REGLE, regle, "annulation", decrire_regle(regle),
                    avant={"actif": True}, apres={"actif": False}, motif=motif, student=regle.student)
        return Response(self.get_serializer(regle).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reactiver(self, request, pk=None):
        regle = self.get_object()
        motif = _motif(request, obligatoire=True)
        if regle.en_vigueur:
            return Response({"detail": "Règle déjà en vigueur."}, status=400)
        regle.actif, regle.annulee_le, regle.annulee_par, regle.motif_annulation = True, None, None, ""
        regle.save()
        journaliser(request, regle.academy, JournalFinancier.REGLE, regle, "reactivation", decrire_regle(regle),
                    avant={"actif": False}, apres={"actif": True}, motif=motif, student=regle.student)
        return Response(self.get_serializer(regle).data)

    @action(detail=True, methods=["get"])
    def impact(self, request, pk=None):
        """Élèves concernés et montant réellement accordé, selon le moteur (aucune écriture)."""
        from .reminders import compute_dues
        regle = self.get_object()
        par_eleve = {}
        for item in compute_dues(regle.academy).items:
            for a in item.adjustments:
                if a.get("regle_id") == regle.pk:
                    cle = (item.student.pk, item.fee.pk, item.school_year_id)
                    par_eleve.setdefault(item.student.pk, {"eleve_id": item.student.pk, "nom": item.student.get_full_name(),
                                                           "montant_minor": 0, "ecartee": [], "vus": set()})
                    ligne = par_eleve[item.student.pk]
                    if cle not in ligne["vus"]:
                        ligne["vus"].add(cle)
                        ligne["montant_minor"] += a["montant_minor"]
                        if not a["retenue"] and a["raison"]:
                            ligne["ecartee"].append(a["raison"])
        devise = regle.academy.currency_code
        lignes = sorted(par_eleve.values(), key=lambda l: l["nom"])
        for l in lignes:
            l.pop("vus")
            l["montant"] = Money(l["montant_minor"], devise).formatted()
        total = sum(l["montant_minor"] for l in lignes)
        return Response({"eleves": lignes, "nombre": len(lignes), "total_minor": total,
                         "total": Money(total, devise).formatted()})


def _echeance_dict(e, devise):
    return {"id": e.pk, "label": e.label, "due_date": e.due_date, "montant_minor": e.amount_minor,
            "montant": Money(e.amount_minor, devise).formatted(), "actif": e.actif, "motif": e.motif,
            "cree_le": e.cree_le}


class EcheancierEleveView(AcademyScopedMixin, APIView):
    """GET ?eleve=&tarif=&annee= ; POST {student, fee_schedule, school_year, motif, echeances: [{label, due_date, montant}]}"""

    def get(self, request):
        academy = self.academy()
        qs = EcheanceEleve.objects.filter(academy=academy).select_related("student", "fee_schedule", "school_year")
        p = request.query_params
        for cle, champ in (("eleve", "student_id"), ("tarif", "fee_schedule_id"), ("annee", "school_year_id")):
            if p.get(cle):
                qs = qs.filter(**{champ: identifiant(p[cle])})
        if p.get("tout") != "1":
            qs = qs.filter(actif=True)
        groupes = {}
        for e in qs.order_by("student__last_name", "fee_schedule_id", "due_date"):
            cle = (e.student_id, e.fee_schedule_id, e.school_year_id)
            g = groupes.setdefault(cle, {"eleve_id": e.student_id, "eleve": e.student.get_full_name(),
                                         "tarif_id": e.fee_schedule_id,
                                         "tarif": e.fee_schedule.label or type_label(e.fee_schedule.payment_type),
                                         "annee_id": e.school_year_id, "annee": e.school_year.name, "echeances": []})
            g["echeances"].append(_echeance_dict(e, academy.currency_code))
        return Response(list(groupes.values()))

    @transaction.atomic
    def post(self, request):
        from apps.schools.models import SchoolYear
        from apps.students.models import Student
        academy = self.academy()
        d = request.data
        eleve = Student.objects.filter(pk=identifiant(d.get("student")), school=academy).first()
        tarif = FeeSchedule.objects.filter(pk=identifiant(d.get("fee_schedule")), academy=academy).prefetch_related("installments").first()
        annee = SchoolYear.objects.filter(pk=identifiant(d.get("school_year")), school=academy).first()
        if not (eleve and tarif and annee):
            raise ValidationError({"detail": "Élève, tarif ou année inconnu dans cette académie."})
        if tarif.school_year_id and tarif.school_year_id != annee.pk:
            raise ValidationError({"school_year": "Ce tarif concerne une autre année scolaire."})
        motif = _motif(request, obligatoire=True)
        lignes = d.get("echeances")
        if not isinstance(lignes, list) or not lignes or len(lignes) > 24:
            raise ValidationError({"echeances": "Entre 1 et 24 échéances."})
        nouvelles, dates = [], set()
        for n, l in enumerate(lignes):
            if not isinstance(l, dict):
                raise ValidationError({"echeances": "Format invalide."})
            due = date_field(l.get("due_date"), "due_date")
            if due is None or due in dates:
                raise ValidationError({"echeances": f"Échéance {n + 1} : date absente ou en double."})
            dates.add(due)
            montant = _to_minor(l.get("montant"), academy.currency_code, "montant")
            if montant <= 0:
                raise ValidationError({"echeances": f"Échéance {n + 1} : montant positif requis."})
            label = (l.get("label") if isinstance(l.get("label"), str) else "").strip()[:80] or f"Échéance {n + 1}"
            nouvelles.append((label, due, montant, n))
        attendu = (tarif.amount_minor if tarif.installment_mode == tarif.INSTALLMENTS_SPLIT
                   else sum(i.amount_minor for i in tarif.installments.all()))
        total = sum(m for _l, _d, m, _n in nouvelles)
        if total != attendu:
            raise ValidationError({"echeances": (
                f"La somme des échéances ({Money(total, academy.currency_code).formatted()}) doit être égale au montant "
                f"du tarif ({Money(attendu, academy.currency_code).formatted()}). Une remise se définit à part.")})
        anciennes = list(EcheanceEleve.objects.filter(student=eleve, fee_schedule=tarif, school_year=annee, actif=True))
        avant = {"echeances": [[e.label, e.due_date.isoformat(), e.amount_minor] for e in anciennes]
                 or [[i.label, i.due_date.isoformat(), i.amount_minor] for i in tarif.installments.all()]}
        EcheanceEleve.objects.filter(pk__in=[e.pk for e in anciennes]).update(actif=False)
        crees = [EcheanceEleve.objects.create(academy=academy, student=eleve, fee_schedule=tarif, school_year=annee,
                                              label=l, due_date=dd, amount_minor=m, order=n, motif=motif,
                                              cree_par=request.user) for l, dd, m, n in nouvelles]
        journaliser(request, academy, JournalFinancier.ECHEANCIER, crees[0], "modification" if anciennes else "creation",
                    f"Échéancier personnel : {eleve.get_full_name()} · {tarif.label or type_label(tarif.payment_type)} · {annee.name}",
                    avant=avant, apres={"echeances": [[l, dd.isoformat(), m] for l, dd, m, _n in nouvelles]},
                    motif=motif, student=eleve)
        return Response([_echeance_dict(e, academy.currency_code) for e in crees], status=status.HTTP_201_CREATED)


class RetablirEcheancierView(AcademyScopedMixin, APIView):
    """POST {student, fee_schedule, school_year, motif} : revient aux échéances standard (rien n'est supprimé)."""

    @transaction.atomic
    def post(self, request):
        academy = self.academy()
        d = request.data
        qs = EcheanceEleve.objects.filter(academy=academy, actif=True, student_id=identifiant(d.get("student")),
                                          fee_schedule_id=identifiant(d.get("fee_schedule")),
                                          school_year_id=identifiant(d.get("school_year")))
        lignes = list(qs.select_related("student", "fee_schedule", "school_year"))
        if not lignes:
            return Response({"detail": "Aucun échéancier personnel actif."}, status=404)
        motif = _motif(request, obligatoire=True)
        qs.update(actif=False)
        e = lignes[0]
        journaliser(request, academy, JournalFinancier.ECHEANCIER, e, "desactivation",
                    f"Retour à l'échéancier standard : {e.student.get_full_name()} · "
                    f"{e.fee_schedule.label or type_label(e.fee_schedule.payment_type)} · {e.school_year.name}",
                    avant={"echeances": [[x.label, x.due_date.isoformat(), x.amount_minor] for x in lignes]},
                    apres={"echeances": "standard"}, motif=motif, student=e.student)
        return Response({"ok": True})


class JournalFinancierView(AcademyScopedMixin, APIView):
    """Historique des tarifs ET des décisions (remises, exonérations, échéanciers, dispositions)."""

    def get(self, request):
        from .models import FeeScheduleChange
        academy = self.academy()
        p = request.query_params
        eleve = identifiant(p.get("eleve")) if p.get("eleve") else None
        objet = p.get("objet")
        lignes = []
        if objet in (None, "", "tarif") and eleve is None:
            for c in FeeScheduleChange.objects.filter(academy=academy).select_related("changed_by")[:500]:
                lignes.append({"id": f"t{c.pk}", "objet": "tarif", "objet_libelle": "Tarif", "action": c.action,
                               "action_libelle": c.get_action_display(), "description": c.fee_description,
                               "avant": ({"montant": Money(c.old_amount_minor, c.currency).formatted()}
                                         if c.old_amount_minor is not None else {}),
                               "apres": ({"montant": Money(c.new_amount_minor, c.currency).formatted()}
                                         if c.new_amount_minor is not None else {}),
                               "champs": c.fields_changed, "motif": c.reason,
                               "auteur": c.changed_by.get_full_name() if c.changed_by else c.changed_by_email,
                               "le": c.changed_at})
        qs = JournalFinancier.objects.filter(academy=academy).select_related("auteur")
        if eleve is not None:
            qs = qs.filter(student_id=eleve)
        if objet in dict(JournalFinancier.OBJETS):
            qs = qs.filter(objet=objet)
        for j in qs[:500]:
            lignes.append({"id": f"j{j.pk}", "objet": j.objet, "objet_libelle": j.get_objet_display(), "action": j.action,
                           "action_libelle": j.get_action_display(), "description": j.description,
                           "avant": j.avant, "apres": j.apres, "champs": sorted(set(j.avant) | set(j.apres)),
                           "motif": j.motif, "auteur": j.auteur.get_full_name() if j.auteur else j.auteur_email,
                           "le": j.le})
        lignes.sort(key=lambda x: x["le"], reverse=True)
        return Response(lignes[:500])


class BaremesView(AcademyScopedMixin, APIView):
    """GET : barèmes officiels disponibles pour l'académie, avec aperçu et points à confirmer.
       POST {fichier, confirmation: true} : crée les tarifs ABSENTS (jamais de remplacement)."""

    def get(self, request):
        from .bareme import apercu, baremes_pour
        academy = self.academy()
        out = []
        for nom, _plan in baremes_pour(academy):
            a = apercu(academy, nom)
            for l in a["lignes"]:
                l.pop("_spec"); l.pop("_rows")
            out.append(a)
        return Response(out)

    def post(self, request):
        from .bareme import importer
        if request.data.get("confirmation") is not True:
            return Response({"confirmation": "Confirmez après avoir vérifié les points signalés."}, status=400)
        nom = request.data.get("fichier") if isinstance(request.data.get("fichier"), str) else ""
        crees = importer(self.academy(), nom, request.user)
        if crees is None:
            return Response({"detail": "Barème introuvable pour cette académie, ou année scolaire absente."}, status=404)
        return Response({"crees": crees}, status=status.HTTP_201_CREATED)
