"""
P2 — La demande de préinscription FEBA, de la saisie au PDF.

LE DÉFAUT REPRODUIT
-------------------
Le tableau du back-office affichait six colonnes : date, enfant, niveau,
parent, téléphone, statut. L'e-mail, le WhatsApp, l'âge, l'année scolaire
et le message étaient collectés par le formulaire public, enregistrés en
base — et n'apparaissaient NULLE PART. Trois autres champs dont le
secrétariat avait besoin (date de naissance, adresse, second téléphone)
n'existaient même pas au modèle. Aucune fiche officielle n'était produite,
et la famille ne recevait aucun numéro de dossier.

CE QUE CES TESTS VÉRIFIENT
--------------------------
La chaîne entière, maillon par maillon :

    champ React → payload → serializer d'écriture → modèle → base
    → serializer de lecture → API admin → API super admin → PDF → CSV

Un champ qui disparaît en route ne provoque aucune erreur : il devient
simplement `undefined`. C'est pourquoi chaque maillon est vérifié
séparément, avec une valeur DIFFÉRENTE par champ — une valeur commune
laisserait passer une permutation de deux colonnes.
"""
import csv
import io
import re
from datetime import date

import fitz  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.schools.models import School
from apps.website.models import PreRegistration

User = get_user_model()

# ── Jeu d'essai : une valeur distincte et reconnaissable par champ ───────

MOT_300 = "M" + "o" * 298 + "T"
URL_LONGUE = (
    "https://feba.example.org/dossiers/" + "segment-tres-long-" * 12
    + "?token=" + "a" * 120
)
MESSAGE_5000 = (
    "Bonjour,\n\n"
    "Nous souhaitons inscrire notre fille <en urgence> & en internat.\n"
    + "Précision de la famille. " * 210
    + "\n\nCordialement,\nFamille Adjovi-Bokô"
)
ADRESSE = ("Carrefour Saint-Michel, derrière la pharmacie\n"
           "Lot 42, parcelle B\nAkpakpa, Cotonou, Bénin")

PAYLOAD = {
    "parent_name": "Chris Adjovi-Bokô",
    "phone": "+229 01 02 03 04",
    "phone_secondary": "+229 05 06 07 08",
    "whatsapp": "+229 09 10 11 12",
    "email": "chris.adjovi@example.org",
    "address": ADRESSE,
    "child_name": "Amélie Adjovi-Bokô",
    "child_age": 8,
    "child_birth_date": "2017-04-12",
    "desired_level": "ce1",
    "school_year": "2026-2027",
    "message": MESSAGE_5000,
}

#: Chaque champ du formulaire public, avec la valeur attendue en base.
#: `child_birth_date` est comparé comme date, pas comme chaîne.
CHAMPS_ATTENDUS = {
    "parent_name": PAYLOAD["parent_name"],
    "phone": PAYLOAD["phone"],
    "phone_secondary": PAYLOAD["phone_secondary"],
    "whatsapp": PAYLOAD["whatsapp"],
    "email": PAYLOAD["email"],
    "address": ADRESSE,
    "child_name": PAYLOAD["child_name"],
    "child_age": 8,
    "child_birth_date": date(2017, 4, 12),
    "desired_level": "ce1",
    "school_year": "2026-2027",
    "message": MESSAGE_5000,
}

PUBLIC_URL = "/api/website/preregistrations/"
ADMIN_URL = "/api/website/admin/preregistrations/"


def texte_du_pdf(content):
    document = fitz.open(stream=content, filetype="pdf")
    try:
        return "".join(page.get_text() for page in document), document.page_count
    finally:
        document.close()


@pytest.fixture
def academies(db):
    feba, _ = School.objects.update_or_create(
        code=School.CODE_FEBA,
        defaults=dict(name="Faith & Excellence Bilingual Academy",
                      address="Akpakpa, Cotonou", city="Cotonou",
                      country="Bénin", currency_code="XOF"),
    )
    fha, _ = School.objects.update_or_create(
        code=School.CODE_FEBA_FHA,
        defaults=dict(name="FEBA French Heritage Academy",
                      address="Programme en ligne", entity_type="online",
                      currency_code="USD"),
    )
    return feba, fha


@pytest.fixture
def demande(academies):
    """Une demande déposée par le formulaire public, avec tous les champs."""
    response = APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
    assert response.status_code == 201, response.data
    return PreRegistration.objects.get()


@pytest.fixture
def utilisateurs(academies):
    feba, fha = academies
    return {
        "admin_feba": User.objects.create_user(
            username="a.feba", email="a.feba@test", password="x",
            role="admin", school=feba),
        "admin_fha": User.objects.create_user(
            username="a.fha", email="a.fha@test", password="x",
            role="admin", school=fha),
        "superadmin": User.objects.create_user(
            username="sa", email="sa@test", password="x",
            role="superadmin", school=feba),
        "teacher": User.objects.create_user(
            username="t", email="t@test", password="x",
            role="teacher", school=feba),
        "parent": User.objects.create_user(
            username="p", email="p@test", password="x",
            role="parent", school=feba),
        "student": User.objects.create_user(
            username="e", email="e@test", password="x",
            role="student", school=feba),
    }


def client_de(user, scope=None):
    """
    Un client authentifié. Pour un super administrateur, l'académie active
    est PERSISTÉE en base : un navigateur ne peut pas élargir sa portée en
    forgeant un en-tête.
    """
    if user.is_superadmin():
        user.active_organization = (
            School.objects.filter(code=scope).first() if scope else None)
        user.save(update_fields=["active_organization"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── 1. La chaîne d'écriture ──────────────────────────────────────────────


@pytest.mark.django_db
class TestChaineEcriture:

    def test_le_formulaire_public_accepte_tous_les_champs(self, academies):
        response = APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        assert response.status_code == 201, response.data

    def test_chaque_champ_arrive_reellement_en_base(self, demande):
        """
        LE CŒUR DU DÉFAUT. Un champ absent de `fields` du serializer est
        JETÉ EN SILENCE par DRF : la requête réussit, la famille croit
        avoir répondu, la valeur n'existe pas.
        """
        for champ, attendu in CHAMPS_ATTENDUS.items():
            assert getattr(demande, champ) == attendu, (
                f"« {champ} » n'est pas arrivé en base : "
                f"{getattr(demande, champ)!r} au lieu de {attendu!r}"
            )

    def test_le_message_long_n_est_pas_rogne(self, demande):
        """DRF retire par défaut les espaces de début et de fin."""
        assert demande.message == MESSAGE_5000
        assert len(demande.message) == len(MESSAGE_5000)

    def test_l_adresse_conserve_ses_retours_a_la_ligne(self, demande):
        assert demande.address.count("\n") == ADRESSE.count("\n")

    def test_l_academie_est_fixee_par_le_serveur(self, demande, academies):
        """Le formulaire public ne choisit pas son académie."""
        feba, _ = academies
        assert demande.entity_id == feba.pk

    def test_une_academie_envoyee_par_le_client_est_ignoree(self, academies):
        feba, fha = academies
        payload = dict(PAYLOAD, entity=fha.pk)
        APIClient().post(PUBLIC_URL, payload, format="json")
        assert PreRegistration.objects.get().entity_id == feba.pk

    def test_une_date_de_naissance_future_est_refusee(self, academies):
        payload = dict(PAYLOAD, child_birth_date="2099-01-01")
        response = APIClient().post(PUBLIC_URL, payload, format="json")
        assert response.status_code == 400
        assert "child_birth_date" in response.data

    def test_un_age_hors_bornes_est_refuse(self, academies):
        response = APIClient().post(PUBLIC_URL, dict(PAYLOAD, child_age=42),
                                    format="json")
        assert response.status_code == 400

    def test_la_reponse_publique_donne_le_numero_de_dossier(self, academies):
        response = APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        assert response.data["reference"].startswith("FEBA-")


# ── 2. Le numéro de dossier ──────────────────────────────────────────────


@pytest.mark.django_db
class TestNumeroDeDossier:

    def test_le_format_est_stable(self, demande):
        assert re.fullmatch(r"FEBA-\d{4}-\d{4}", demande.reference)

    def test_deux_demandes_ne_partagent_jamais_un_numero(self, academies):
        for _ in range(5):
            APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        references = list(PreRegistration.objects.values_list("reference", flat=True))
        assert len(set(references)) == len(references)
        assert all(references)

    def test_le_numero_ne_derive_pas_d_un_comptage(self, academies):
        """
        Un `count() + 1` redonnerait un numéro déjà attribué dès qu'une
        demande est supprimée : deux dossiers différents porteraient la
        même référence dans les échanges avec deux familles.
        """
        APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        deuxieme = PreRegistration.objects.order_by("-pk").first().reference
        PreRegistration.objects.order_by("pk").first().delete()

        APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        troisieme = PreRegistration.objects.order_by("-pk").first().reference
        assert troisieme != deuxieme
        assert PreRegistration.objects.filter(reference=troisieme).count() == 1

    def test_la_fenetre_entre_insertion_et_numerotation_ne_collisionne_pas(
            self, academies):
        """
        NON-RÉGRESSION D'UN DÉFAUT DE CETTE ITÉRATION.

        La référence dérive de la clé primaire : elle ne peut donc être
        écrite qu'APRÈS l'insertion. Entre les deux, la ligne porte une
        valeur transitoire. Avec `blank=True` et le défaut `""`, deux
        insertions simultanées se retrouvaient toutes deux à `""` — et la
        contrainte d'unicité les refusait. NULL, lui, n'est égal à rien,
        pas même à un autre NULL.
        """
        premiere = PreRegistration.objects.create(
            entity=academies[0], parent_name="A", phone="+229",
            child_name="EA", desired_level="ci")
        # On replace la première ligne dans son état transitoire.
        PreRegistration.objects.filter(pk=premiere.pk).update(reference=None)
        seconde = PreRegistration.objects.create(
            entity=academies[0], parent_name="B", phone="+229",
            child_name="EB", desired_level="ci")
        assert seconde.reference
        assert seconde.reference != premiere.reference


# ── 3. La chaîne de lecture ──────────────────────────────────────────────


@pytest.mark.django_db
class TestChaineLecture:

    def test_l_api_admin_renvoie_chaque_champ(self, demande, utilisateurs):
        client = client_de(utilisateurs["admin_feba"])
        ligne = client.get(f"{ADMIN_URL}{demande.pk}/").data
        for champ, attendu in CHAMPS_ATTENDUS.items():
            valeur = ligne.get(champ)
            assert valeur is not None, f"« {champ} » absent de la réponse admin"
            assert str(valeur) == str(attendu), (
                f"« {champ} » altéré : {valeur!r} au lieu de {attendu!r}")

    def test_le_message_complet_traverse_l_api(self, demande, utilisateurs):
        client = client_de(utilisateurs["admin_feba"])
        ligne = client.get(f"{ADMIN_URL}{demande.pk}/").data
        assert ligne["message"] == MESSAGE_5000
        assert "Famille Adjovi-Bokô" in ligne["message"]

    def test_la_liste_porte_l_academie_de_chaque_ligne(self, demande, utilisateurs):
        client = client_de(utilisateurs["admin_feba"])
        lignes = client.get(ADMIN_URL).data
        lignes = lignes.get("results", lignes)
        assert lignes[0]["academy_code"] == School.CODE_FEBA
        assert lignes[0]["academy_name"]

    def test_l_etat_de_la_fiche_est_constate_pas_deduit(self, demande, utilisateurs):
        """
        `sheet_available` regarde le DISQUE. Un booléen calculé côté écran
        à partir de `sheet_path` dirait « oui » pour un fichier effacé.
        """
        client = client_de(utilisateurs["admin_feba"])
        assert client.get(f"{ADMIN_URL}{demande.pk}/").data["sheet_available"] is True

        import os
        os.remove(demande.sheet_absolute_path)
        assert client.get(f"{ADMIN_URL}{demande.pk}/").data["sheet_available"] is False

    def test_le_statut_est_modifiable(self, demande, utilisateurs):
        client = client_de(utilisateurs["admin_feba"])
        response = client.patch(f"{ADMIN_URL}{demande.pk}/",
                                {"status": "processing"}, format="json")
        assert response.status_code == 200
        demande.refresh_from_db()
        assert demande.status == "processing"

    def test_les_donnees_deposees_ne_sont_pas_modifiables(self, demande, utilisateurs):
        """
        Une demande est une DÉCLARATION de la famille. La corriger depuis
        le back-office ferait dire à la famille ce qu'elle n'a pas dit.
        """
        client = client_de(utilisateurs["admin_feba"])
        client.patch(f"{ADMIN_URL}{demande.pk}/",
                     {"child_name": "Autre enfant"}, format="json")
        demande.refresh_from_db()
        assert demande.child_name == PAYLOAD["child_name"]


# ── 4. La fiche PDF ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFichePdf:

    def test_la_fiche_est_produite_a_l_enregistrement(self, demande):
        assert demande.has_sheet, "aucune fiche produite"
        assert demande.sheet_sha256
        assert demande.sheet_generated_at
        assert demande.sheet_error == ""

    def test_la_fiche_est_rangee_hors_du_repertoire_public(self, demande):
        from django.conf import settings

        chemin = demande.sheet_absolute_path
        media = str(getattr(settings, "MEDIA_ROOT", "/media-absent"))
        assert not chemin.startswith(media), (
            "la fiche est dans le répertoire servi publiquement : une URL "
            "devinée suffirait à exposer l'adresse d'une famille")
        assert "feba_preregistrations" in chemin

    def test_la_fiche_contient_toutes_les_informations(self, demande):
        contenu = open(demande.sheet_absolute_path, "rb").read()
        texte, _ = texte_du_pdf(contenu)
        plat = texte.replace("\n", "")
        for valeur in (demande.reference, "Adjovi-Bokô", "+229 05 06 07 08",
                       "chris.adjovi@example.org", "2026-2027",
                       "Saint-Michel", "12/04/2017"):
            assert valeur.replace(" ", "") in plat.replace(" ", ""), (
                f"« {valeur} » absent de la fiche officielle")

    def test_la_fiche_porte_l_identite_feba_et_elle_seule(self, demande):
        texte, _ = texte_du_pdf(open(demande.sheet_absolute_path, "rb").read())
        assert "Faith & Excellence Bilingual Academy" in texte.replace("\n", " ")
        assert "French Heritage" not in texte, (
            "une fiche de l'école de Cotonou porte l'identité de l'académie "
            "en ligne : ce sont deux établissements, deux directions.")

    def test_un_message_de_5000_caracteres_ne_casse_pas_la_fiche(self, demande):
        texte, pages = texte_du_pdf(open(demande.sheet_absolute_path, "rb").read())
        assert pages >= 2
        assert "Famille Adjovi-Bokô" in texte.replace("\n", "")

    def test_un_mot_de_300_caracteres_reste_dans_le_cadre(self, academies):
        from apps.website.feba_prereg_pdf import generate_prereg_sheet
        from reportlab.lib.units import cm

        demande = PreRegistration.objects.create(
            entity=academies[0], parent_name="A", phone="+229",
            child_name="E", desired_level="ci", message=MOT_300)
        contenu = generate_prereg_sheet(demande)
        document = fitz.open(stream=contenu, filetype="pdf")
        try:
            marge = document[0].rect.width - 1.6 * cm
            debordements = [m[4] for page in document
                            for m in page.get_text("words") if m[2] > marge + 0.5]
            plat = "".join(p.get_text() for p in document).replace("\n", "")
        finally:
            document.close()
        assert not debordements, f"{len(debordements)} mots hors cadre"
        assert len(re.search(r"Mo+T", plat).group(0)) == 300

    def test_une_url_tres_longue_reste_dans_le_cadre(self, academies):
        from apps.website.feba_prereg_pdf import generate_prereg_sheet
        from reportlab.lib.units import cm

        demande = PreRegistration.objects.create(
            entity=academies[0], parent_name="A", phone="+229",
            child_name="E", desired_level="ci", message=URL_LONGUE)
        document = fitz.open(stream=generate_prereg_sheet(demande), filetype="pdf")
        try:
            marge = document[0].rect.width - 1.6 * cm
            debordements = [m[4] for page in document
                            for m in page.get_text("words") if m[2] > marge + 0.5]
            plat = "".join(p.get_text() for p in document).replace("\n", "")
        finally:
            document.close()
        assert not debordements
        assert "token=" + "a" * 120 in plat

    def test_les_accents_et_entites_survivent(self, academies):
        from apps.website.feba_prereg_pdf import generate_prereg_sheet

        demande = PreRegistration.objects.create(
            entity=academies[0], parent_name="Kofí Ọ̀ṣun", phone="+229",
            child_name="Amélie", desired_level="ci",
            message="Coût « 25 000 F » & <urgent> — à Cotonou")
        texte, _ = texte_du_pdf(generate_prereg_sheet(demande))
        plat = texte.replace("\n", "")
        assert "Amélie" in plat
        assert "& <urgent>" in plat
        assert "25 000 F" in plat

    def test_aucune_page_n_est_vide(self, demande):
        document = fitz.open(demande.sheet_absolute_path)
        try:
            vides = [p.number + 1 for p in document if not p.get_text().strip()]
        finally:
            document.close()
        assert not vides, f"pages vides : {vides}"

    def test_un_echec_de_production_est_ecrit_et_signale(self, academies, monkeypatch):
        """
        Une demande dont la fiche échoue reste ENREGISTRÉE — la famille a
        rempli le formulaire — mais l'échec doit se voir, pas se taire.
        """
        from apps.notifications.models import Notification
        from apps.website import feba_prereg

        User.objects.create_user(username="sa2", email="sa2@test", password="x",
                                 role="superadmin", school=academies[0])

        def echoue(_):
            raise RuntimeError("police introuvable")

        monkeypatch.setattr(
            "apps.website.feba_prereg_pdf.generate_prereg_sheet", echoue)

        response = APIClient().post(PUBLIC_URL, PAYLOAD, format="json")
        assert response.status_code == 201, "la demande a été perdue"

        demande = PreRegistration.objects.get()
        assert not demande.has_sheet
        assert "police introuvable" in demande.sheet_error
        assert Notification.objects.filter(
            title__contains=demande.reference).exists(), (
            "l'échec est consigné dans une colonne que personne ne regarde")

    def test_la_fiche_est_regenerable(self, demande, utilisateurs):
        import os

        os.remove(demande.sheet_absolute_path)
        client = client_de(utilisateurs["admin_feba"])
        response = client.post(f"{ADMIN_URL}{demande.pk}/regenerate-sheet/")
        assert response.status_code == 200
        demande.refresh_from_db()
        assert demande.has_sheet


# ── 5. Le téléchargement sécurisé ────────────────────────────────────────


@pytest.mark.django_db
class TestTelechargementSecurise:

    def test_l_administrateur_de_l_academie_telecharge_la_fiche(
            self, demande, utilisateurs):
        client = client_de(utilisateurs["admin_feba"])
        response = client.get(f"{ADMIN_URL}{demande.pk}/sheet/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert demande.reference in response["Content-Disposition"]

    def test_la_fiche_n_est_pas_mise_en_cache(self, demande, utilisateurs):
        client = client_de(utilisateurs["admin_feba"])
        response = client.get(f"{ADMIN_URL}{demande.pk}/sheet/")
        assert "no-store" in response["Cache-Control"]

    def test_un_anonyme_n_obtient_rien(self, demande):
        response = APIClient().get(f"{ADMIN_URL}{demande.pk}/sheet/")
        assert response.status_code in (401, 403)

    def test_le_fichier_n_est_pas_servi_par_une_url_publique(self, demande):
        """
        Le chemin privé ne doit correspondre à aucune route publique. On
        vérifie la seule chose vérifiable ici : le fichier est hors de
        MEDIA_ROOT, donc le serveur statique ne le publie pas.
        """
        from django.conf import settings

        media = str(getattr(settings, "MEDIA_ROOT", "/media-absent"))
        assert not demande.sheet_absolute_path.startswith(media)

    def test_les_permissions_du_fichier_sont_restreintes(self, demande):
        import os
        import stat

        mode = stat.S_IMODE(os.stat(demande.sheet_absolute_path).st_mode)
        assert mode & 0o077 == 0, (
            f"mode {oct(mode)} : lisible par les autres comptes de la machine")


# ── 6. Les permissions multi-académies ───────────────────────────────────


@pytest.mark.django_db
class TestPermissions:

    def test_l_administrateur_feba_voit_les_demandes(self, demande, utilisateurs):
        response = client_de(utilisateurs["admin_feba"]).get(ADMIN_URL)
        assert response.status_code == 200
        lignes = response.data.get("results", response.data)
        assert len(lignes) == 1

    def test_l_administrateur_de_l_academie_en_ligne_est_refuse(
            self, demande, utilisateurs):
        """
        Masquer l'onglet côté React ne suffit pas : l'URL reste
        atteignable à la main.
        """
        response = client_de(utilisateurs["admin_fha"]).get(ADMIN_URL)
        assert response.status_code == 403

    def test_l_administrateur_en_ligne_ne_telecharge_aucune_fiche(
            self, demande, utilisateurs):
        response = client_de(utilisateurs["admin_fha"]).get(
            f"{ADMIN_URL}{demande.pk}/sheet/")
        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["teacher", "parent", "student"])
    def test_les_autres_profils_sont_refuses(self, demande, utilisateurs, role):
        response = client_de(utilisateurs[role]).get(ADMIN_URL)
        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["teacher", "parent", "student"])
    def test_les_autres_profils_n_obtiennent_pas_la_fiche(
            self, demande, utilisateurs, role):
        response = client_de(utilisateurs[role]).get(
            f"{ADMIN_URL}{demande.pk}/sheet/")
        assert response.status_code == 403

    def test_le_super_admin_filtre_sur_feba_voit_les_demandes(
            self, demande, utilisateurs):
        client = client_de(utilisateurs["superadmin"], School.CODE_FEBA)
        lignes = client.get(ADMIN_URL).data
        lignes = lignes.get("results", lignes)
        assert len(lignes) == 1

    def test_le_super_admin_filtre_sur_l_academie_en_ligne_ne_voit_rien(
            self, demande, utilisateurs):
        """
        La page doit obéir au sélecteur placé juste au-dessus d'elle.
        Afficher les demandes de Cotonou pendant que l'en-tête annonce
        l'académie en ligne, c'est contredire l'écran lui-même.
        """
        client = client_de(utilisateurs["superadmin"], School.CODE_FEBA_FHA)
        lignes = client.get(ADMIN_URL).data
        lignes = lignes.get("results", lignes)
        assert len(lignes) == 0

    def test_un_identifiant_d_une_autre_academie_donne_404(
            self, demande, utilisateurs):
        """
        Anti-IDOR. 404 et non 403 : répondre « interdit » confirmerait
        que le dossier existe — c'est déjà une fuite.
        """
        client = client_de(utilisateurs["superadmin"], School.CODE_FEBA_FHA)
        response = client.get(f"{ADMIN_URL}{demande.pk}/")
        assert response.status_code == 404

    def test_un_admin_ne_peut_pas_elargir_sa_portee_par_un_parametre(
            self, demande, utilisateurs, academies):
        _, fha = academies
        client = client_de(utilisateurs["admin_feba"])
        response = client.get(f"{ADMIN_URL}?entity_code={fha.code}")
        lignes = response.data.get("results", response.data)
        assert all(l["academy_code"] == School.CODE_FEBA for l in lignes)


# ── 7. L'export CSV ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExportCsv:

    def _lignes(self, response):
        contenu = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(contenu), delimiter=";"))

    def test_l_export_porte_des_intitules_francais_explicites(
            self, demande, utilisateurs):
        """
        DÉFAUT TROUVÉ EN OUVRANT LE FICHIER, PAS EN LISANT LE CODE.

        L'export dérivait ses intitulés de `field.verbose_name`, que
        Django fabrique à partir du nom de l'attribut quand on ne lui en
        donne pas. Le secrétariat recevait « Address », « Phone secondary »,
        « Child birth date » — dans un établissement dont toute
        l'administration travaille en français.

        La version précédente de ce test comparait l'en-tête produit à
        `field.verbose_name.capitalize()`, c'est-à-dire à lui-même : elle
        passait sans rien prouver. Les intitulés attendus sont désormais
        ÉCRITS ICI, ce qui est la seule façon d'attraper la régression.
        """
        response = client_de(utilisateurs["admin_feba"]).get(f"{ADMIN_URL}export/")
        assert response.status_code == 200
        entete = self._lignes(response)[0]

        attendus = [
            "Académie", "Numéro de dossier", "Nom du parent",
            "Téléphone principal", "Téléphone secondaire", "WhatsApp",
            "Adresse électronique", "Adresse du domicile", "Nom de l'enfant",
            "Âge déclaré", "Date de naissance", "Niveau demandé",
            "Année scolaire souhaitée", "Message de la famille", "Statut",
            "Reçue le", "Fiche PDF produite",
        ]
        manquants = [c for c in attendus if c not in entete]
        assert not manquants, f"colonnes absentes de l'export : {manquants}"

    def test_chaque_colonne_exportee_a_un_intitule_ecrit(
            self, demande, utilisateurs):
        """
        Un champ ajouté au modèle sans intitulé fait échouer l'export au
        lieu de sortir un en-tête anglais au milieu du tableau.
        """
        from apps.website.views import _PREREG_EXPORT_EXCLUDED, _PREREG_EXPORT_LABELS

        for field in PreRegistration._meta.fields:
            if field.name in _PREREG_EXPORT_EXCLUDED or field.name == "entity":
                continue
            assert field.name in _PREREG_EXPORT_LABELS, (
                f"« {field.name} » n'a pas d'intitulé français pour l'export")

    def test_aucun_intitule_n_est_en_anglais_par_defaut(
            self, demande, utilisateurs):
        response = client_de(utilisateurs["admin_feba"]).get(f"{ADMIN_URL}export/")
        entete = self._lignes(response)[0]
        for intrus in ("Address", "Phone secondary", "Child birth date",
                       "Parent name", "Child name", "Desired level"):
            assert intrus not in entete, (
                f"intitulé anglais « {intrus} » dans l'export")

    def test_les_valeurs_sont_celles_de_la_demande(self, demande, utilisateurs):
        response = client_de(utilisateurs["admin_feba"]).get(f"{ADMIN_URL}export/")
        lignes = self._lignes(response)
        assert len(lignes) >= 2
        cellules = ";".join(lignes[1])
        for valeur in (demande.reference, PAYLOAD["email"],
                       PAYLOAD["whatsapp"], PAYLOAD["phone_secondary"],
                       "2026-2027"):
            assert valeur in cellules, f"« {valeur} » absent de l'export"

    def test_l_export_porte_le_bom_utf8(self, demande, utilisateurs):
        """Sans lui, Excel affiche « Ã© » à la place de « é »."""
        response = client_de(utilisateurs["admin_feba"]).get(f"{ADMIN_URL}export/")
        assert response.content.startswith(b"\xef\xbb\xbf")

    def test_l_export_ne_divulgue_aucun_chemin_serveur(self, demande, utilisateurs):
        response = client_de(utilisateurs["admin_feba"]).get(f"{ADMIN_URL}export/")
        contenu = response.content.decode("utf-8-sig")
        assert "private_media" not in contenu
        assert demande.sheet_sha256 not in contenu

    def test_l_export_respecte_l_academie(self, demande, utilisateurs):
        client = client_de(utilisateurs["superadmin"], School.CODE_FEBA_FHA)
        lignes = self._lignes(client.get(f"{ADMIN_URL}export/"))
        assert len(lignes) <= 1, "des demandes FEBA sortent sous l'académie en ligne"

    def test_l_administrateur_en_ligne_ne_peut_pas_exporter(
            self, demande, utilisateurs):
        response = client_de(utilisateurs["admin_fha"]).get(f"{ADMIN_URL}export/")
        assert response.status_code == 403

    def test_creer_une_demande_depuis_l_administration_reste_interdit(
            self, academies, utilisateurs):
        """
        Ouvrir `post` pour l'action « régénérer » ouvre aussi la création
        d'objets. Une préinscription est une DÉCLARATION de la famille :
        une demande saisie par un administrateur ferait dire à une
        famille ce qu'elle n'a pas dit, avec un numéro officiel à l'appui.
        """
        client = client_de(utilisateurs["admin_feba"])
        response = client.post(ADMIN_URL, PAYLOAD, format="json")
        assert response.status_code == 405
        assert PreRegistration.objects.count() == 0
