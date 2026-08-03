"""
P3 — Les rapports mensuels FEBA French Heritage Academy.

CE QUE CES TESTS DÉFENDENT
--------------------------
Un rapport mensuel part chez des parents et fait autorité sur le mois
écoulé de leur enfant. Trois affirmations doivent être vraies, et chacune
est vérifiée ici plutôt que supposée :

1. **Ce qui est écrit a été saisi.** Aucune donnée inventée, aucune
   moyenne de remplissage. Une rubrique vide le dit avec une phrase, pas
   avec un zéro — « 0 absence » laisse croire que la présence a été
   relevée et qu'elle était parfaite ; « aucune donnée » dit la vérité.

2. **Relancer ne duplique rien.** Le planificateur rejoue, un
   administrateur relance, un worker redémarre. Aucun de ces cas ne doit
   produire un second rapport ni un second courrier.

3. **« Envoyé » veut dire envoyé.** Écrire un PDF n'est pas un envoi, et
   un backend qui écrit dans la console non plus. Le statut ne bascule
   que si un fournisseur externe a accepté le message.
"""
from datetime import date, timedelta

import fitz  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient

from apps.classes.models import Class
from apps.monthly_reports.aggregation import EMPTY_SECTION, build_report_data
from apps.monthly_reports.models import (
    InvalidTransition, MonthlyReportStatus, MonthlyStudentReport,
)
from apps.monthly_reports.services import generate_report, send_report
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student

User = get_user_model()

URL = "/api/monthly-reports/reports/"
ANNEE, MOIS = 2026, 5

TEXTE_LONG = ("Observation de l'enseignant. " * 220
              + "\n\nConclusion : progrès <très nets> & réguliers.")


def texte_du_pdf(chemin):
    document = fitz.open(chemin)
    try:
        return "".join(p.get_text() for p in document), document.page_count
    finally:
        document.close()


@pytest.fixture
def academies(db):
    feba, _ = School.objects.update_or_create(
        code=School.CODE_FEBA,
        defaults=dict(name="Faith & Excellence Bilingual Academy",
                      address="Akpakpa, Cotonou", currency_code="XOF"))
    fha, _ = School.objects.update_or_create(
        code=School.CODE_FEBA_FHA,
        defaults=dict(name="FEBA French Heritage Academy",
                      address="Programme en ligne", entity_type="online",
                      currency_code="USD"))
    return feba, fha


def _student(school, first, last):
    year, _ = SchoolYear.objects.get_or_create(
        school=school, name="2025-2026",
        defaults=dict(start_date=date(2025, 9, 1), end_date=date(2026, 7, 31),
                      is_current=True))
    level = Level.objects.create(school=school, name=f"N-{school.pk}", order=3)
    klass = Class.objects.create(name=f"C-{school.pk}", level=level,
                                 school_year=year)
    return Student.objects.create(school=school, first_name=first,
                                  last_name=last, current_class=klass,
                                  school_year=year)


@pytest.fixture
def eleve_fha(academies):
    return _student(academies[1], "Amélie", "Adjovi-Bokô")


@pytest.fixture
def eleve_feba(academies):
    return _student(academies[0], "Kofi", "Mensah")


@pytest.fixture
def utilisateurs(academies):
    feba, fha = academies
    return {
        "admin_fha": User.objects.create_user(
            username="a.fha", email="a.fha@test", password="x",
            role="admin", school=fha),
        "admin_feba": User.objects.create_user(
            username="a.feba", email="a.feba@test", password="x",
            role="admin", school=feba),
        "superadmin": User.objects.create_user(
            username="sa", email="sa@test", password="x",
            role="superadmin", school=fha),
        "teacher": User.objects.create_user(
            username="t", email="t@test", password="x",
            role="teacher", school=fha),
        "parent": User.objects.create_user(
            username="p", email="p@test", password="x",
            role="parent", school=fha),
    }


def client_de(user, scope=None):
    if user.is_superadmin():
        user.active_organization = (
            School.objects.filter(code=scope).first() if scope else None)
        user.save(update_fields=["active_organization"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _avec_donnees(student):
    """Sème des données RÉELLES sur le mois observé."""
    from apps.attendance.models import Attendance

    for jour, statut in ((4, "present"), (5, "absent"), (6, "late"),
                         (7, "present"), (8, "excused")):
        Attendance.objects.create(student=student, date=date(ANNEE, MOIS, jour),
                                  status=statut,
                                  justification="Rendez-vous médical"
                                  if statut == "excused" else "")
    return student


# ── 1. L'agrégation ne fabrique rien ─────────────────────────────────


@pytest.mark.django_db
class TestAgregation:

    def test_un_mois_sans_donnee_le_declare(self, eleve_fha):
        data = build_report_data(eleve_fha, ANNEE, MOIS)
        assert data["resume"]["mois_sans_donnee"] is True
        for cle, section in data["sections"].items():
            assert section["has_data"] is False, cle

    def test_un_mois_vide_n_invente_pas_de_zero(self, eleve_fha):
        """
        « 0 absence » laisserait croire que la présence a été relevée.
        L'absence de relevé et un relevé parfait sont deux choses
        différentes, et une seule est vérifiable.
        """
        data = build_report_data(eleve_fha, ANNEE, MOIS)
        assert "absent" not in data["sections"]["attendance"]

    def test_les_presences_saisies_sont_comptees_exactement(self, eleve_fha):
        _avec_donnees(eleve_fha)
        section = build_report_data(eleve_fha, ANNEE, MOIS)["sections"]["attendance"]
        assert section["has_data"] is True
        assert section["total_days"] == 5
        assert section["present"] == 2
        assert section["absent"] == 1
        assert section["late"] == 1
        assert section["excused"] == 1

    def test_le_taux_porte_sur_les_jours_releves(self, eleve_fha):
        """
        Diviser par les jours ouvrés théoriques fabriquerait un
        pourcentage qu'aucune saisie ne soutient.
        """
        _avec_donnees(eleve_fha)
        section = build_report_data(eleve_fha, ANNEE, MOIS)["sections"]["attendance"]
        assert section["presence_rate"] == 60.0  # (2 présents + 1 excusé) / 5

    def test_les_motifs_saisis_sont_repris_mot_pour_mot(self, eleve_fha):
        _avec_donnees(eleve_fha)
        section = build_report_data(eleve_fha, ANNEE, MOIS)["sections"]["attendance"]
        motifs = [j["motif"] for j in section["justifications"]]
        assert "Rendez-vous médical" in motifs

    def test_les_donnees_d_un_autre_mois_ne_debordent_pas(self, eleve_fha):
        from apps.attendance.models import Attendance

        _avec_donnees(eleve_fha)
        Attendance.objects.create(student=eleve_fha,
                                  date=date(ANNEE, MOIS + 1, 3), status="absent")
        section = build_report_data(eleve_fha, ANNEE, MOIS)["sections"]["attendance"]
        assert section["total_days"] == 5

    def test_chaque_rubrique_porte_un_titre(self, eleve_fha):
        data = build_report_data(eleve_fha, ANNEE, MOIS)
        for cle, section in data["sections"].items():
            assert section.get("title"), f"rubrique « {cle} » sans titre"


# ── 2. Génération et idempotence ─────────────────────────────────────


@pytest.mark.django_db
class TestGeneration:

    def test_un_rapport_est_produit_avec_son_pdf(self, eleve_fha):
        report, created = generate_report(eleve_fha, ANNEE, MOIS)
        assert created is True
        assert report.has_pdf
        assert report.pdf_sha256
        assert report.status == MonthlyReportStatus.GENERATED

    def test_la_reference_suit_un_format_stable(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        assert report.reference.startswith(f"FHA-RM-{ANNEE}-{MOIS:02d}-")
        assert report.reference.endswith("-v1")

    def test_relancer_ne_cree_pas_un_second_rapport(self, eleve_fha):
        """
        LE CŒUR DE L'IDEMPOTENCE. Le planificateur rejoue, un
        administrateur relance, un worker redémarre : aucun de ces cas ne
        doit produire un doublon.
        """
        generate_report(eleve_fha, ANNEE, MOIS)
        _, created = generate_report(eleve_fha, ANNEE, MOIS)
        assert created is False
        assert MonthlyStudentReport.objects.count() == 1

    def test_la_base_refuse_le_doublon_meme_forcé(self, eleve_fha, academies):
        from django.db import IntegrityError, transaction

        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                MonthlyStudentReport.objects.create(
                    academy=academies[1], student=eleve_fha, year=ANNEE,
                    month=MOIS, version=report.version)

    def test_une_nouvelle_version_conserve_la_precedente(self, eleve_fha):
        premier, _ = generate_report(eleve_fha, ANNEE, MOIS)
        second, created = generate_report(eleve_fha, ANNEE, MOIS,
                                          force_new_version=True)
        assert created is True
        assert second.version == premier.version + 1
        assert MonthlyStudentReport.objects.count() == 2
        assert MonthlyStudentReport.objects.filter(pk=premier.pk).exists()

    def test_une_nouvelle_version_reprend_le_texte_humain(self, eleve_fha):
        """
        Perdre le texte rédigé obligerait à le réécrire — et c'est ainsi
        qu'on finit par ne plus le réécrire du tout.
        """
        premier, _ = generate_report(eleve_fha, ANNEE, MOIS)
        premier.editable_content = {"summary": "Très bon mois."}
        premier.save(update_fields=["editable_content"])
        second, _ = generate_report(eleve_fha, ANNEE, MOIS,
                                    force_new_version=True)
        assert second.editable_content["summary"] == "Très bon mois."

    def test_regenerer_n_efface_pas_le_texte_humain(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.editable_content = {"recommendations": "Poursuivre la lecture."}
        report.save(update_fields=["editable_content"])
        generate_report(eleve_fha, ANNEE, MOIS)
        report.refresh_from_db()
        assert report.editable_content["recommendations"] == "Poursuivre la lecture."

    def test_un_mois_change_produit_un_rapport_distinct(self, eleve_fha):
        generate_report(eleve_fha, ANNEE, MOIS)
        generate_report(eleve_fha, ANNEE, MOIS + 1)
        assert MonthlyStudentReport.objects.count() == 2

    def test_l_academie_vient_de_l_eleve(self, eleve_fha, academies):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        assert report.academy_id == academies[1].pk


# ── 3. Le PDF ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPdf:

    def test_le_pdf_est_range_hors_du_repertoire_public(self, eleve_fha):
        from django.conf import settings

        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        media = str(getattr(settings, "MEDIA_ROOT", "/media-absent"))
        assert not report.pdf_absolute_path.startswith(media)
        assert "monthly_reports" in report.pdf_absolute_path

    def test_les_permissions_du_fichier_sont_restreintes(self, eleve_fha):
        import os
        import stat

        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        mode = stat.S_IMODE(os.stat(report.pdf_absolute_path).st_mode)
        assert mode & 0o077 == 0

    def test_le_pdf_porte_l_identite_de_l_academie_en_ligne(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        texte, _ = texte_du_pdf(report.pdf_absolute_path)
        plat = texte.replace("\n", " ")
        assert "French Heritage Academy" in plat
        assert "Faith & Excellence Bilingual Academy" not in plat, (
            "un rapport de l'académie en ligne porte l'identité de l'école "
            "de Cotonou : deux établissements, deux directions.")

    def test_une_rubrique_vide_porte_la_phrase_d_absence(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        texte, _ = texte_du_pdf(report.pdf_absolute_path)
        assert EMPTY_SECTION in texte.replace("\n", " ")

    def test_aucune_rubrique_n_est_escamotee(self, eleve_fha):
        """
        Une rubrique qui disparaît fait croire qu'elle n'existe pas,
        alors qu'elle existe et n'a rien reçu.
        """
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        texte, _ = texte_du_pdf(report.pdf_absolute_path)
        plat = texte.upper().replace("\n", " ")
        for titre in ("PRÉSENCE", "SÉANCES", "DEVOIRS", "ÉVALUATIONS"):
            assert titre in plat, f"rubrique « {titre} » absente du rapport"

    def test_les_donnees_saisies_apparaissent(self, eleve_fha):
        _avec_donnees(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        texte, _ = texte_du_pdf(report.pdf_absolute_path)
        plat = texte.replace("\n", " ")
        assert "Rendez-vous médical" in plat
        assert "60.0 %" in plat or "60 %" in plat

    def test_un_texte_de_plusieurs_milliers_de_caracteres_passe(self, eleve_fha):
        """Non-régression du LayoutError corrigé en P0."""
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.editable_content = {"summary": TEXTE_LONG,
                                   "recommendations": TEXTE_LONG}
        report.save(update_fields=["editable_content"])
        from apps.monthly_reports.pdf import generate_report_pdf

        contenu = generate_report_pdf(report)
        assert contenu[:5] == b"%PDF-"

    def test_les_chevrons_du_texte_humain_ne_sont_pas_avales(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.editable_content = {"summary": "Progrès <très nets> & réguliers."}
        report.save(update_fields=["editable_content"])
        from apps.monthly_reports.pdf import generate_report_pdf

        import io

        document = fitz.open(stream=generate_report_pdf(report), filetype="pdf")
        try:
            plat = "".join(p.get_text() for p in document).replace("\n", "")
        finally:
            document.close()
        assert "<très nets>" in plat
        assert "& réguliers" in plat

    def test_le_nom_accentue_survit(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        texte, _ = texte_du_pdf(report.pdf_absolute_path)
        assert "Adjovi-Bokô" in texte.replace("\n", "")


# ── 4. Envoi : ce que « envoyé » veut dire ───────────────────────────


@pytest.mark.django_db
class TestEnvoi:

    def _avec_parent(self, student, email="parent@example.org", langue="fr"):
        from apps.parents.models import Parent, ParentStudent

        user = User.objects.create_user(
            username=f"p-{student.pk}", email=email, password="x",
            role="parent", school=student.school)
        user.preferred_language = langue
        user.save(update_fields=["preferred_language"])
        parent = Parent.objects.create(user=user)
        ParentStudent.objects.create(parent=parent, student=student,
                                     relationship="mother")
        return user

    def test_un_backend_local_ne_donne_jamais_le_statut_envoye(
            self, eleve_fha, settings):
        """
        LE TEST QUI EMPÊCHE LE MENSONGE POLI.

        Le backend en mémoire accepte le message et Django renvoie 1.
        Une lecture naïve conclurait « le parent a reçu son rapport ».
        Personne ne l'a reçu.
        """
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        self._avec_parent(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)

        report = send_report(report)
        assert report.status == MonthlyReportStatus.FAILED
        assert report.really_sent is False
        assert "capturé localement" in report.last_error

    def test_le_message_est_bien_composé_malgre_tout(self, eleve_fha, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        self._avec_parent(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        send_report(report)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["parent@example.org"]
        assert "Rapport mensuel" in message.subject
        assert "Adjovi-Bokô" in message.subject
        assert message.attachments, "aucune pièce jointe"
        nom, contenu, mimetype = message.attachments[0]
        assert nom.endswith(".pdf")
        assert mimetype == "application/pdf"
        assert contenu[:5] == b"%PDF-"

    def test_la_langue_du_parent_est_respectee(self, eleve_fha, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        self._avec_parent(eleve_fha, langue="en")
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        send_report(report)
        assert "Monthly report" in mail.outbox[0].subject
        assert "Please find attached" in mail.outbox[0].body

    def test_un_fournisseur_externe_permet_le_statut_envoye(
            self, eleve_fha, settings, monkeypatch):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "mailpit"
        self._avec_parent(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)

        # On simule l'ACCEPTATION par le serveur, pas le rendu du PDF.
        monkeypatch.setattr(
            "django.core.mail.EmailMultiAlternatives.send", lambda self, **k: 1)

        report = send_report(report)
        assert report.status == MonthlyReportStatus.SENT
        assert report.really_sent is True
        assert report.provider_message_id

    def test_un_rapport_deja_accepte_n_est_pas_renvoye(
            self, eleve_fha, settings, monkeypatch):
        """Garde-fou anti-doublon : la tâche peut être rejouée."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "mailpit"
        self._avec_parent(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        appels = []
        monkeypatch.setattr(
            "django.core.mail.EmailMultiAlternatives.send",
            lambda self, **k: (appels.append(1), 1)[1])

        send_report(report)
        send_report(report)
        send_report(report)
        assert len(appels) == 1, "le rapport est reparti plusieurs fois"

    def test_un_eleve_sans_parent_joignable_echoue_explicitement(
            self, eleve_fha, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report = send_report(report)
        assert report.status == MonthlyReportStatus.FAILED
        assert "adresse électronique" in report.last_error
        assert report.recipients == []

    def test_chaque_tentative_est_historisee(self, eleve_fha, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        self._avec_parent(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        send_report(report)
        send_report(report)
        assert report.attempts.count() == 2
        assert all(not a.succeeded for a in report.attempts.all())

    def test_un_echec_smtp_est_enregistre_et_non_masque(
            self, eleve_fha, settings, monkeypatch):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "mailpit"
        self._avec_parent(eleve_fha)
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)

        def refuse(self, **kwargs):
            raise OSError("connexion refusée par le serveur")

        monkeypatch.setattr(
            "django.core.mail.EmailMultiAlternatives.send", refuse)

        report = send_report(report)
        assert report.status == MonthlyReportStatus.FAILED
        assert "connexion refusée" in report.last_error
        assert report.really_sent is False


# ── 5. Les états ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEtats:

    def test_un_rapport_naissant_est_un_brouillon(self, eleve_fha, academies):
        report = MonthlyStudentReport.objects.create(
            academy=academies[1], student=eleve_fha, year=ANNEE, month=MOIS)
        assert report.status == MonthlyReportStatus.DRAFT

    def test_generer_ne_suffit_pas_a_passer_a_envoye(self, eleve_fha):
        """
        Produire un PDF n'est pas un envoi. La transition directe est
        refusée par le modèle, pas seulement évitée par convention.
        """
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        with pytest.raises(InvalidTransition):
            report.transition_to(MonthlyReportStatus.SENT)

    def test_un_rapport_archive_est_terminal(self, eleve_fha, academies):
        report = MonthlyStudentReport.objects.create(
            academy=academies[1], student=eleve_fha, year=ANNEE, month=MOIS,
            status=MonthlyReportStatus.ARCHIVED)
        for cible in MonthlyReportStatus:
            with pytest.raises(InvalidTransition):
                report.transition_to(cible)

    def test_l_archivage_horodate(self, eleve_fha):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.transition_to(MonthlyReportStatus.CANCELLED)
        report.transition_to(MonthlyReportStatus.ARCHIVED)
        assert report.archived_at is not None

    def test_les_huit_etats_existent(self):
        attendus = {"draft", "generated", "ready", "sending", "sent",
                    "failed", "cancelled", "archived"}
        assert {s.value for s in MonthlyReportStatus} == attendus


# ── 6. L'API et le cloisonnement ─────────────────────────────────────


@pytest.mark.django_db
class TestApi:

    def test_l_administrateur_de_l_academie_en_ligne_voit_les_rapports(
            self, eleve_fha, utilisateurs):
        generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_fha"]).get(URL)
        assert reponse.status_code == 200
        lignes = reponse.data.get("results", reponse.data)
        assert len(lignes) == 1

    def test_l_administrateur_de_cotonou_est_refuse(self, eleve_fha, utilisateurs):
        """
        Masquer l'entrée de menu ne protège rien : l'URL reste
        atteignable à la main.
        """
        generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_feba"]).get(URL)
        assert reponse.status_code == 403

    @pytest.mark.parametrize("role", ["teacher", "parent"])
    def test_les_autres_profils_sont_refuses(self, eleve_fha, utilisateurs, role):
        reponse = client_de(utilisateurs[role]).get(URL)
        assert reponse.status_code == 403

    def test_un_anonyme_est_refuse(self, eleve_fha):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_le_super_admin_sur_cotonou_ne_voit_aucun_rapport(
            self, eleve_fha, utilisateurs):
        generate_report(eleve_fha, ANNEE, MOIS)
        client = client_de(utilisateurs["superadmin"], School.CODE_FEBA)
        lignes = client.get(URL).data
        assert len(lignes.get("results", lignes)) == 0

    def test_produire_pour_un_eleve_de_cotonou_est_refuse(
            self, eleve_feba, utilisateurs):
        """
        Anti-IDOR : un identifiant d'élève de Cotonou produirait un
        rapport à l'identité de l'académie en ligne pour un enfant qui
        n'y est pas inscrit.
        """
        client = client_de(utilisateurs["admin_fha"])
        reponse = client.post(URL, {"student": eleve_feba.pk, "year": ANNEE,
                                    "month": MOIS}, format="json")
        assert reponse.status_code == 404

    def test_produire_deux_fois_ne_cree_pas_de_doublon(self, eleve_fha,
                                                       utilisateurs):
        client = client_de(utilisateurs["admin_fha"])
        payload = {"student": eleve_fha.pk, "year": ANNEE, "month": MOIS}
        premier = client.post(URL, payload, format="json")
        second = client.post(URL, payload, format="json")
        assert premier.status_code == 201
        assert second.status_code == 200
        assert MonthlyStudentReport.objects.count() == 1

    def test_un_mois_invalide_est_refuse(self, eleve_fha, utilisateurs):
        client = client_de(utilisateurs["admin_fha"])
        reponse = client.post(URL, {"student": eleve_fha.pk, "year": ANNEE,
                                    "month": 13}, format="json")
        assert reponse.status_code == 400

    def test_le_pdf_se_telecharge(self, eleve_fha, utilisateurs):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_fha"]).get(f"{URL}{report.pk}/pdf/")
        assert reponse.status_code == 200
        assert reponse["Content-Type"] == "application/pdf"
        assert "no-store" in reponse["Cache-Control"]

    def test_l_apercu_s_ouvre_dans_l_onglet(self, eleve_fha, utilisateurs):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_fha"]).get(
            f"{URL}{report.pk}/pdf/?preview=1")
        assert reponse["Content-Disposition"].startswith("inline")

    def test_l_administrateur_de_cotonou_n_obtient_aucun_pdf(
            self, eleve_fha, utilisateurs):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_feba"]).get(
            f"{URL}{report.pk}/pdf/")
        assert reponse.status_code == 403

    def test_le_texte_humain_est_modifiable(self, eleve_fha, utilisateurs):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_fha"]).patch(
            f"{URL}{report.pk}/",
            {"editable_content": {"summary": "Mois solide."}}, format="json")
        assert reponse.status_code == 200
        report.refresh_from_db()
        assert report.editable_content["summary"] == "Mois solide."

    def test_un_champ_redige_inconnu_est_refuse(self, eleve_fha, utilisateurs):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        reponse = client_de(utilisateurs["admin_fha"]).patch(
            f"{URL}{report.pk}/",
            {"editable_content": {"note_secrete": "x"}}, format="json")
        assert reponse.status_code == 400

    def test_les_donnees_agregees_ne_sont_pas_modifiables(self, eleve_fha,
                                                          utilisateurs):
        """
        Elles décrivent ce que les enseignants ont saisi. Les corriger
        d'ici ferait dire à un relevé autre chose que ce qu'il contient.
        """
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        avant = report.generated_data
        client_de(utilisateurs["admin_fha"]).patch(
            f"{URL}{report.pk}/", {"generated_data": {"truque": True}},
            format="json")
        report.refresh_from_db()
        assert report.generated_data == avant

    def test_un_rapport_envoye_n_est_plus_modifiable(self, eleve_fha,
                                                     utilisateurs):
        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.status = MonthlyReportStatus.SENT
        report.save(update_fields=["status"])
        reponse = client_de(utilisateurs["admin_fha"]).patch(
            f"{URL}{report.pk}/",
            {"editable_content": {"summary": "corrigé"}}, format="json")
        assert reponse.status_code == 400

    def test_un_rapport_reellement_transmis_ne_se_supprime_pas(
            self, eleve_fha, utilisateurs):
        from django.utils import timezone

        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.status = MonthlyReportStatus.SENT
        report.sent_at = timezone.now()
        report.provider_message_id = "abc123"
        report.save(update_fields=["status", "sent_at", "provider_message_id"])

        reponse = client_de(utilisateurs["admin_fha"]).delete(f"{URL}{report.pk}/")
        assert reponse.status_code == 400
        assert MonthlyStudentReport.objects.filter(pk=report.pk).exists()

    def test_la_recherche_filtre_sur_le_nom(self, eleve_fha, utilisateurs):
        generate_report(eleve_fha, ANNEE, MOIS)
        client = client_de(utilisateurs["admin_fha"])
        trouve = client.get(f"{URL}?search=Adjovi").data
        absent = client.get(f"{URL}?search=Zzzz").data
        assert len(trouve.get("results", trouve)) == 1
        assert len(absent.get("results", absent)) == 0

    def test_les_filtres_periode_et_statut_fonctionnent(self, eleve_fha,
                                                        utilisateurs):
        generate_report(eleve_fha, ANNEE, MOIS)
        client = client_de(utilisateurs["admin_fha"])
        ok = client.get(f"{URL}?year={ANNEE}&month={MOIS}&status=generated").data
        ko = client.get(f"{URL}?year={ANNEE}&month={MOIS}&status=sent").data
        assert len(ok.get("results", ok)) == 1
        assert len(ko.get("results", ko)) == 0

    def test_le_lot_d_un_mois_se_declenche(self, eleve_fha, utilisateurs):
        client = client_de(utilisateurs["admin_fha"])
        reponse = client.post(f"{URL}generate-month/",
                              {"year": ANNEE, "month": MOIS}, format="json")
        assert reponse.status_code == 200
        assert reponse.data["crees"] == 1

    def test_relancer_le_lot_ne_duplique_rien(self, eleve_fha, utilisateurs):
        client = client_de(utilisateurs["admin_fha"])
        payload = {"year": ANNEE, "month": MOIS}
        client.post(f"{URL}generate-month/", payload, format="json")
        second = client.post(f"{URL}generate-month/", payload, format="json")
        assert second.data["crees"] == 0
        assert second.data["existants"] == 1
        assert MonthlyStudentReport.objects.count() == 1

    def test_le_lot_ignore_les_eleves_de_l_autre_academie(
            self, eleve_fha, eleve_feba, utilisateurs):
        client = client_de(utilisateurs["admin_fha"])
        client.post(f"{URL}generate-month/", {"year": ANNEE, "month": MOIS},
                    format="json")
        assert MonthlyStudentReport.objects.count() == 1
        assert MonthlyStudentReport.objects.first().student_id == eleve_fha.pk


# ── 7. Deux défauts vus sur le DOCUMENT, pas dans le code ────────────


@pytest.mark.django_db
class TestDefautsVusSurLeDocument:
    """
    Ces deux défauts ont survécu à soixante tests unitaires. Ils n'ont
    été trouvés qu'en ouvrant le PDF produit et en le regardant.
    """

    def test_le_logo_de_l_academie_en_ligne_ne_nomme_pas_l_autre_ecole(
            self, academies):
        """
        DÉFAUT N°1 — Les deux académies partageaient `logo_feba.jpeg`.
        Cette image ne porte pas que le blason du groupe : le libellé
        « Faith & Excellence Bilingual Academy » y est incrusté sous le
        bouclier. Chaque document de l'académie en ligne — fiche
        d'inscription, reçu, rapport mensuel — portait donc en tête le
        nom de l'école de Cotonou.

        Aucun test textuel ne pouvait l'attraper : le nom était dans une
        image matricielle, invisible à l'extraction de texte. Ce test
        compare les FICHIERS.
        """
        import os

        from apps.schools.branding import get_branding

        feba, fha = academies
        logo_feba = get_branding(feba).document_logo
        logo_fha = get_branding(fha).document_logo

        assert logo_fha, "l'académie en ligne n'a aucun logo"
        assert os.path.exists(logo_fha), logo_fha
        assert os.path.basename(logo_fha) != os.path.basename(logo_feba), (
            "les deux académies impriment le même fichier de logo ; celui de "
            "Cotonou contient son nom en toutes lettres."
        )

    def test_le_blason_du_groupe_est_conserve_intact(self, academies):
        """
        La correction retire le libellé, pas le blason. Le bouclier est
        la marque du GROUPE, commune aux deux académies et présente sur
        les documents officiels des deux.
        """
        from PIL import Image

        from apps.schools.branding import get_branding

        feba, fha = academies
        source = Image.open(get_branding(feba).document_logo).convert("RGB")
        derive = Image.open(get_branding(fha).document_logo).convert("RGB")

        assert derive.width == source.width, "le blason a été redimensionné"
        assert derive.height < source.height, "rien n'a été retiré"
        # Chaque pixel conservé doit être IDENTIQUE : une réécriture du
        # blason (recompression, filtre, redimensionnement) l'abîmerait
        # sans que personne ne le remarque avant l'impression.
        haut_source = source.crop((0, 0, source.width, derive.height))
        assert list(haut_source.getdata()) == list(derive.getdata()), (
            "les pixels conservés du blason ont été altérés")

    def test_un_texte_non_redige_ne_pretend_pas_a_un_defaut_de_saisie(
            self, eleve_fha):
        """
        DÉFAUT N°2 — Un champ d'appréciation vide affichait « Aucune
        donnée enregistrée pour cette période ». C'est faux deux fois :
        il n'y a rien à « enregistrer » — ce sont des textes qu'on écrit —
        et la phrase accusait les enseignants d'un défaut de saisie alors
        que c'est l'administration qui n'avait pas encore rédigé.
        """
        from apps.monthly_reports.aggregation import NOT_WRITTEN
        from apps.monthly_reports.pdf import build_sections

        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        sections = dict(build_sections(report))
        appreciation = next(v for k, v in sections.items()
                            if "Appréciation" in k)
        valeurs = [valeur for _, valeur in appreciation]
        assert all(v == NOT_WRITTEN for v in valeurs), valeurs
        assert EMPTY_SECTION not in valeurs

    def test_les_deux_phrases_d_absence_restent_distinctes(self):
        from apps.monthly_reports.aggregation import EMPTY_SECTION, NOT_WRITTEN

        assert EMPTY_SECTION != NOT_WRITTEN

    def test_un_texte_redige_remplace_bien_la_mention(self, eleve_fha):
        from apps.monthly_reports.aggregation import NOT_WRITTEN
        from apps.monthly_reports.pdf import build_sections

        report, _ = generate_report(eleve_fha, ANNEE, MOIS)
        report.editable_content = {"summary": "Excellent mois."}
        report.save(update_fields=["editable_content"])
        sections = dict(build_sections(report))
        appreciation = next(v for k, v in sections.items()
                            if "Appréciation" in k)
        assert ("Synthèse du mois", "Excellent mois.") in appreciation
        assert ("Progrès observés", NOT_WRITTEN) in appreciation
