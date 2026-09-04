"""
V10 — portée d'académie, parcours linguistiques, accès aux salles.

CE QUE CE FICHIER VERROUILLE
----------------------------
Quatre anomalies signalées, dont deux partageaient une seule cause :

  * « Nouvelle salle virtuelle » ne proposait que « Toute l'école » ;
  * « Classes assignées » d'un enseignant affichait « Aucun résultat » ;
  * une classe monolingue était déclarée incomplète pour toujours ;
  * une salle « générale » était ouverte à tous, faute de ciblage par rôle.

La cause des deux premières était mesurable, et elle l'est encore ici :

    GET /api/classes/              →  0 classe
    GET /api/classes/?all_years=1  →  3 classes

Même utilisateur, même académie, même instant. Le filtre par défaut portait
sur `school_year__is_current=True` et supposait un invariant que rien ne
garantissait — « chaque académie a exactement une année active ».
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.academic_year import active_year, has_explicit_active_year
from apps.schools.models import Level, School, SchoolYear
from apps.subjects.models import Subject


def academy(code, name, **extra):
    """
    L'académie de code `code`, créée si besoin.

    `update_or_create` et non `create` : les deux académies du groupe sont
    posées par une migration de données (`schools.0013`). Les recréer
    violerait l'unicité du slug — et surtout, on veut tester les entités
    réelles, pas des jumelles.
    """
    defaults = dict(name=name, currency_code="XOF", address="Cotonou",
                    slug=code.lower().replace("_", "-"))
    defaults.update(extra)
    school, _ = School.objects.update_or_create(code=code, defaults=defaults)
    # Chaque test part d'une académie sans année : les fixtures des
    # migrations n'en créent pas, mais une exécution antérieure a pu en
    # laisser dans la base de test réutilisée.
    SchoolYear.objects.filter(school=school).delete()
    return school


def year(school, name, start, current=False):
    y = SchoolYear.objects.create(
        school=school, name=name, start_date=start,
        end_date=date(start.year + 1, 7, 31), is_current=current)
    return y


def klass(school_year, name, track=Class.TRACK_BILINGUAL):
    level, _ = Level.objects.get_or_create(
        school=school_year.school, name="Niveau", defaults={"order": 1})
    return Class.objects.create(
        name=name, level=level, school_year=school_year, language_track=track)


def user(school, role, email, **extra):
    return CustomUser.objects.create_user(
        username=email, email=email, password="Pass1234!", role=role,
        school=school, first_name="P", last_name="N", **extra)


class BaseDeuxAcademies(TestCase):
    """Deux académies réelles, comme en production."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = academy("FEBA", "Faith & Excellence Bilingual Academy")
        cls.fha = academy("FEBA_FHA", "FEBA French Heritage Academy")

        # FEBA : trois années, une active — le cas qui a motivé le filtre.
        cls.feba_2024 = year(cls.feba, "2024-2025", date(2024, 9, 1))
        cls.feba_2025 = year(cls.feba, "2025-2026", date(2025, 9, 1))
        cls.feba_2026 = year(cls.feba, "2026-2027", date(2026, 9, 1), current=True)
        for y in (cls.feba_2024, cls.feba_2025, cls.feba_2026):
            klass(y, "CP1-A")

        # FEBA FHA : une année, et — c'est tout l'objet — elle n'a jamais
        # été activée par un clic sur « Activer ».
        cls.fha_2026 = year(cls.fha, "2026-2027", date(2026, 9, 1))
        cls.fha_ambassadors = klass(cls.fha_2026, "French Ambassadors")
        cls.fha_explorers = klass(cls.fha_2026, "French Explorers")
        cls.fha_juniors = klass(cls.fha_2026, "Junior Roots")

        cls.admin_feba = user(cls.feba, "admin", "admin@feba.test")
        cls.admin_fha = user(cls.fha, "admin", "admin@fha.test")

    def api(self, u):
        client = APIClient()
        client.force_authenticate(u)
        return client

    def classes_listees(self, u, **params):
        response = self.api(u).get("/api/classes/", {"page_size": 1000, **params})
        self.assertEqual(response.status_code, 200, response.content[:300])
        data = response.json()
        return data.get("results", data)


# ── Le défaut principal ──────────────────────────────────────────────────


class ClassesVisiblesDansLesListesTests(BaseDeuxAcademies):

    def test_une_academie_sans_annee_activee_voit_ses_classes(self):
        """
        LE TEST CENTRAL.

        L'année FHA existe mais n'a jamais été activée. Avant correction,
        cet appel — celui exact que font « Nouvelle salle virtuelle » et
        « Classes assignées » — renvoyait zéro.
        """
        # L'état est bien celui des captures : aucune année explicitement
        # active, mais des classes bien présentes.
        SchoolYear.objects.filter(school=self.fha).update(is_current=False)
        self.assertFalse(has_explicit_active_year(self.fha))

        noms = {c["name"] for c in self.classes_listees(self.admin_fha)}
        self.assertEqual(
            noms, {"French Ambassadors", "French Explorers", "Junior Roots"},
            "Les listes déroulantes retombent à zéro dès qu'aucune année "
            "n'est activée — c'est le défaut signalé.")

    def test_l_ecran_et_le_formulaire_montrent_la_meme_chose(self):
        """
        Un objet visible dans un écran ne doit pas manquer du formulaire
        qui lui correspond. C'était l'écart exact : la page Classes
        interroge une année précise, les menus n'en interrogeaient aucune.
        """
        SchoolYear.objects.filter(school=self.fha).update(is_current=False)
        menus = {c["name"] for c in self.classes_listees(self.admin_fha)}
        ecran = {c["name"] for c in self.classes_listees(self.admin_fha, all_years=1)}
        self.assertEqual(menus, ecran)

    def test_la_premiere_annee_d_une_academie_est_active(self):
        """L'invariant est réparé à la source, pas seulement contourné."""
        nouvelle = academy("FEBA_TEST", "Académie de test")
        creee = year(nouvelle, "2027-2028", date(2027, 9, 1))
        creee.refresh_from_db()
        self.assertTrue(
            creee.is_current,
            "Une académie ne doit pas pouvoir exister avec des classes et "
            "aucune année active.")

    def test_creer_une_seconde_annee_ne_deplace_pas_l_annee_de_travail(self):
        """
        Le corollaire, et il compte autant : activer automatiquement la
        SECONDE année changerait ce que voient tous les écrans d'un
        établissement en service, sans que personne l'ait demandé.
        """
        avant = active_year(self.feba)
        year(self.feba, "2027-2028", date(2027, 9, 1))
        self.assertEqual(active_year(self.feba), avant)


class NonRegressionFebaTests(BaseDeuxAcademies):
    """
    FEBA fonctionne déjà. Le correctif ne doit rien y changer.
    """

    def test_feba_ne_voit_que_l_annee_active_dans_ses_menus(self):
        # Le motif que le filtre d'origine évitait : « CP1-A » trois fois.
        noms = [c["name"] for c in self.classes_listees(self.admin_feba)]
        self.assertEqual(len(noms), 1, f"attendu 1 classe, obtenu {noms}")
        self.assertEqual(len(noms), len(set(noms)), "doublons réapparus")

    def test_feba_garde_l_acces_a_toutes_ses_annees_sur_demande(self):
        toutes = self.classes_listees(self.admin_feba, all_years=1)
        self.assertEqual(len(toutes), 3)

    def test_le_filtre_par_annee_precise_fonctionne_toujours(self):
        ciblees = self.classes_listees(
            self.admin_feba, school_year=self.feba_2024.id)
        self.assertEqual(len(ciblees), 1)
        self.assertEqual(ciblees[0]["school_year"], self.feba_2024.id)


class CloisonnementDesClassesTests(BaseDeuxAcademies):

    def test_un_admin_feba_ne_voit_aucune_classe_fha(self):
        ids_feba = {c["id"] for c in self.classes_listees(self.admin_feba, all_years=1)}
        ids_fha = {c["id"] for c in self.classes_listees(self.admin_fha, all_years=1)}
        self.assertTrue(ids_feba and ids_fha)
        self.assertEqual(ids_feba & ids_fha, set())

    def test_un_admin_ne_lit_pas_une_classe_de_l_autre_academie(self):
        response = self.api(self.admin_feba).get(
            f"/api/classes/{self.fha_ambassadors.id}/")
        self.assertIn(response.status_code, (403, 404))


# ── Parcours linguistiques (§2, §3) ──────────────────────────────────────


class ParcoursLinguistiqueTests(BaseDeuxAcademies):

    def test_le_parcours_par_defaut_est_bilingue(self):
        """
        C'est ce qui garantit que FEBA ne bouge pas : toutes les classes
        existantes conservent exactement leur comportement.
        """
        self.assertEqual(self.fha_ambassadors.language_track,
                         Class.TRACK_BILINGUAL)
        for c in Class.objects.filter(school_year__school=self.feba):
            self.assertEqual(c.language_track, Class.TRACK_BILINGUAL)

    def test_une_classe_bilingue_attend_les_deux_langues(self):
        c = self.fha_ambassadors
        self.assertEqual(set(c.expected_subject_languages()), {"fr", "en"})
        self.assertEqual(set(c.missing_subject_languages()), {"fr", "en"})
        self.assertFalse(c.is_language_configuration_complete())

    def test_une_classe_francophone_n_attend_que_le_francais(self):
        c = klass(self.fha_2026, "Francophones", track=Class.TRACK_FRANCOPHONE)
        fr = Subject.objects.create(school=self.fha, name="Français", language="fr")
        c.subjects.add(fr)
        self.assertEqual(list(c.expected_subject_languages()), ["fr"])
        self.assertEqual(c.missing_subject_languages(), [])
        self.assertTrue(
            c.is_language_configuration_complete(),
            "Une classe francophone était déclarée incomplète pour "
            "toujours, faute d'une langue qu'elle n'enseigne pas.")

    def test_une_classe_anglophone_n_attend_que_l_anglais(self):
        c = klass(self.fha_2026, "Anglophones", track=Class.TRACK_ANGLOPHONE)
        en = Subject.objects.create(school=self.fha, name="English", language="en")
        c.subjects.add(en)
        self.assertEqual(list(c.expected_subject_languages()), ["en"])
        self.assertEqual(c.missing_subject_languages(), [])
        self.assertTrue(c.is_language_configuration_complete())

    def test_une_classe_monolingue_incomplete_est_signalee_pour_SA_langue(self):
        c = klass(self.fha_2026, "Anglophones vides", track=Class.TRACK_ANGLOPHONE)
        # On lui donne une matière FRANÇAISE : elle reste incomplète, mais
        # ce qui lui manque est l'anglais — pas « les deux langues ».
        c.subjects.add(Subject.objects.create(
            school=self.fha, name="Français", language="fr"))
        self.assertEqual(c.missing_subject_languages(), ["en"])

    def test_l_api_expose_le_parcours_et_ce_qui_manque(self):
        c = klass(self.fha_2026, "Anglo API", track=Class.TRACK_ANGLOPHONE)
        données = self.api(self.admin_fha).get(
            f"/api/classes/{c.id}/").json()
        self.assertEqual(données["language_track"], Class.TRACK_ANGLOPHONE)
        self.assertEqual(données["expected_languages"], ["en"])
        self.assertEqual(données["missing_languages"], ["en"])
        self.assertFalse(données["language_config_ok"])

    def test_le_parcours_est_modifiable_par_l_api(self):
        response = self.api(self.admin_fha).patch(
            f"/api/classes/{self.fha_juniors.id}/",
            {"language_track": Class.TRACK_FRANCOPHONE}, format="json")
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.fha_juniors.refresh_from_db()
        self.assertEqual(self.fha_juniors.language_track, Class.TRACK_FRANCOPHONE)


# ── Salles virtuelles : ciblage et contrôle d'accès (§1, §16, §18) ───────


class BaseSalles(BaseDeuxAcademies):
    """Une salle par classe, plus les utilisateurs qui gravitent autour."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.students.models import Student
        from apps.teachers.models import Teacher
        from apps.virtualclass.models import VirtualRoom

        cls.fha.settings = {**(cls.fha.settings or {})}
        cls.fha.save(update_fields=["settings"])

        # Enseignant AFFECTÉ à French Ambassadors, et un autre qui ne l'est pas.
        cls.prof_affecte = user(cls.fha, "teacher", "prof.affecte@fha.test")
        cls.t_affecte = Teacher.objects.create(user=cls.prof_affecte)
        cls.t_affecte.classes.add(cls.fha_ambassadors)

        cls.prof_autre = user(cls.fha, "teacher", "prof.autre@fha.test")
        cls.t_autre = Teacher.objects.create(user=cls.prof_autre)
        cls.t_autre.classes.add(cls.fha_explorers)

        # Élèves : l'un dans la classe de la salle, l'autre non.
        cls.eleve_membre = user(cls.fha, "student", "eleve.membre@fha.test")
        Student.objects.create(
            user=cls.eleve_membre, school=cls.fha, first_name="A", last_name="B",
            current_class=cls.fha_ambassadors, school_year=cls.fha_2026)
        cls.eleve_autre = user(cls.fha, "student", "eleve.autre@fha.test")
        Student.objects.create(
            user=cls.eleve_autre, school=cls.fha, first_name="C", last_name="D",
            current_class=cls.fha_explorers, school_year=cls.fha_2026)

        # Élève d'une AUTRE académie.
        cls.eleve_feba = user(cls.feba, "student", "eleve@feba.test")
        Student.objects.create(
            user=cls.eleve_feba, school=cls.feba, first_name="E", last_name="F",
            school_year=cls.feba_2026)

        cls.salle_classe = VirtualRoom.objects.create(
            school=cls.fha, school_year=cls.fha_2026, name="Cours Ambassadors",
            class_obj=cls.fha_ambassadors, created_by=cls.admin_fha)
        cls.salle_academie = VirtualRoom.objects.create(
            school=cls.fha, school_year=cls.fha_2026, name="Assemblée FHA",
            created_by=cls.admin_fha)


class AccesAuxSallesTests(BaseSalles):

    def refuse(self, u, salle, motif=""):
        from apps.virtualclass.services import JitsiAccessDenied, assert_can_join
        with self.assertRaises(JitsiAccessDenied, msg=motif):
            assert_can_join(u, salle)

    def autorise(self, u, salle):
        from apps.virtualclass.services import assert_can_join
        self.assertTrue(assert_can_join(u, salle))

    def test_un_eleve_de_la_classe_entre(self):
        self.autorise(self.eleve_membre, self.salle_classe)

    def test_un_eleve_d_une_AUTRE_classe_est_refuse(self):
        """Le contrôle est côté serveur : masquer le bouton ne suffit pas."""
        self.refuse(self.eleve_autre, self.salle_classe,
                    "un élève d'une autre classe a pu entrer")

    def test_un_eleve_d_une_AUTRE_ACADEMIE_est_refuse(self):
        self.refuse(self.eleve_feba, self.salle_classe)

    def test_un_enseignant_AFFECTE_entre(self):
        self.autorise(self.prof_affecte, self.salle_classe)

    def test_un_enseignant_NON_AFFECTE_est_refuse(self):
        """
        Le contrôle ne portait que sur les élèves et les parents : tout
        enseignant de l'académie pouvait entrer dans n'importe quel cours.
        """
        self.refuse(self.prof_autre, self.salle_classe,
                    "un enseignant non affecté a pu entrer")

    def test_une_salle_d_academie_accueille_les_membres_de_l_academie(self):
        self.autorise(self.eleve_autre, self.salle_academie)
        self.autorise(self.prof_autre, self.salle_academie)

    def test_une_salle_d_academie_reste_fermee_a_l_autre_academie(self):
        self.refuse(self.eleve_feba, self.salle_academie)

    def test_le_ciblage_par_role_est_applique(self):
        self.salle_academie.target_roles = ["teacher", "admin"]
        self.salle_academie.save(update_fields=["target_roles"])
        self.refuse(self.eleve_membre, self.salle_academie,
                    "une salle réservée à l'équipe était ouverte aux élèves")
        self.autorise(self.prof_autre, self.salle_academie)

    def test_une_salle_annulee_n_accueille_plus_personne(self):
        self.salle_classe.status = "cancelled"
        self.salle_classe.save(update_fields=["status"])
        self.refuse(self.eleve_membre, self.salle_classe)

    def test_un_compte_desactive_est_refuse(self):
        self.eleve_membre.is_active = False
        self.eleve_membre.save(update_fields=["is_active"])
        self.refuse(self.eleve_membre, self.salle_classe)


class IdorParLApiTests(BaseSalles):
    """
    Le contrôle doit tenir face à un appel direct, pas seulement à l'écran.
    """

    def join(self, u, salle):
        client = APIClient()
        client.force_authenticate(u)
        return client.post(f"/api/virtual-rooms/{salle.id}/join/")

    def test_un_eleve_d_une_autre_classe_recoit_403(self):
        response = self.join(self.eleve_autre, self.salle_classe)
        self.assertIn(response.status_code, (403, 404),
                      f"obtenu {response.status_code} : {response.content[:200]}")

    def test_un_utilisateur_d_une_autre_academie_ne_voit_pas_la_salle(self):
        response = self.join(self.eleve_feba, self.salle_classe)
        self.assertIn(response.status_code, (403, 404))

    def test_un_enseignant_non_affecte_recoit_403(self):
        response = self.join(self.prof_autre, self.salle_classe)
        self.assertIn(response.status_code, (403, 404))

    def test_la_visio_est_refusee_a_une_academie_qui_ne_l_a_pas_activee(self):
        """
        FEBA est une académie de type « campus » : `video_conferencing` y
        est désactivé par défaut. Le refus est donc la bonne réponse — et
        c'est une isolation plus forte encore qu'une liste vide.
        """
        client = APIClient()
        client.force_authenticate(self.admin_feba)
        response = client.get("/api/virtual-rooms/", {"page_size": 1000})
        self.assertEqual(response.status_code, 403)

    def test_la_liste_des_salles_est_cloisonnee_par_academie(self):
        """
        Le cloisonnement doit tenir MÊME quand l'autre académie a la
        fonctionnalité : sans cela, on ne testerait que le drapeau
        `video_conferencing`, pas la portée d'académie.
        """
        from apps.virtualclass.models import VirtualRoom

        features = dict((self.feba.settings or {}).get("features") or {})
        features["video_conferencing"] = True
        features["virtual_classrooms"] = True
        self.feba.settings = {**(self.feba.settings or {}), "features": features}
        self.feba.save(update_fields=["settings"])

        salle_feba = VirtualRoom.objects.create(
            school=self.feba, school_year=self.feba_2026,
            name="Salle FEBA", created_by=self.admin_feba)

        client = APIClient()
        client.force_authenticate(self.admin_feba)
        response = client.get("/api/virtual-rooms/", {"page_size": 1000})
        self.assertEqual(response.status_code, 200, response.content[:300])
        data = response.json()
        ids = {r["id"] for r in data.get("results", data)}

        self.assertIn(salle_feba.id, ids, "l'admin ne voit pas sa propre salle")
        self.assertNotIn(self.salle_classe.id, ids)
        self.assertNotIn(self.salle_academie.id, ids)


class JetonJitsiTests(BaseSalles):
    """
    Le jeton est signé par le backend, nomme sa salle, et expire.
    """

    SETTINGS = dict(JITSI_DOMAIN="meet.globalfeba.com",
                    JITSI_APP_ID="feba_prod",
                    JITSI_APP_SECRET="s" * 64,
                    JITSI_INTERNAL_URL="")

    def decode(self, token, **kwargs):
        import jwt
        return jwt.decode(token, "s" * 64, algorithms=["HS256"],
                          audience="jitsi", **kwargs)

    def emettre(self, u, room, **kwargs):
        from django.test import override_settings
        from apps.virtualclass.services import build_jitsi_jwt
        with override_settings(**self.SETTINGS):
            return build_jitsi_jwt(u, room, **kwargs)

    def test_le_jeton_nomme_sa_salle(self):
        payload = self.decode(self.emettre(self.eleve_membre, "salle-a"))
        self.assertEqual(payload["room"], "salle-a")
        self.assertEqual(payload["sub"], "meet.globalfeba.com")
        self.assertEqual(payload["iss"], "feba_prod")

    def test_un_jeton_pour_la_salle_A_ne_vaut_pas_pour_la_salle_B(self):
        payload = self.decode(self.emettre(self.eleve_membre, "salle-a"))
        self.assertNotEqual(payload["room"], "salle-b")

    def test_un_eleve_n_est_jamais_moderateur(self):
        payload = self.decode(self.emettre(self.eleve_membre, "salle-a"))
        self.assertFalse(payload["moderator"])
        self.assertEqual(payload["context"]["user"]["moderator"], "false")

    def test_un_enseignant_peut_etre_moderateur(self):
        payload = self.decode(
            self.emettre(self.prof_affecte, "salle-a", moderator=True))
        self.assertTrue(payload["moderator"])

    def test_le_jeton_expire(self):
        payload = self.decode(self.emettre(self.eleve_membre, "salle-a"))
        self.assertLessEqual(payload["exp"] - payload["iat"], 900)

    def test_un_jeton_expire_est_rejete(self):
        import jwt
        token = self.emettre(self.eleve_membre, "salle-a", ttl_seconds=-60)
        with self.assertRaises(jwt.ExpiredSignatureError):
            self.decode(token)

    def test_un_jeton_altere_est_rejete(self):
        import jwt
        token = self.emettre(self.eleve_membre, "salle-a")
        entete, charge, signature = token.split(".")
        altere = f"{entete}.{charge}.{'A' * len(signature)}"
        with self.assertRaises(jwt.InvalidSignatureError):
            self.decode(altere)

    def test_une_signature_d_un_AUTRE_secret_est_rejetee(self):
        import jwt
        from django.test import override_settings
        from apps.virtualclass.services import build_jitsi_jwt
        with override_settings(**{**self.SETTINGS, "JITSI_APP_SECRET": "x" * 64}):
            token = build_jitsi_jwt(self.eleve_membre, "salle-a")
        with self.assertRaises(jwt.InvalidSignatureError):
            self.decode(token)

    def test_un_mauvais_public_est_rejete(self):
        import jwt
        token = self.emettre(self.eleve_membre, "salle-a")
        with self.assertRaises(jwt.InvalidAudienceError):
            jwt.decode(token, "s" * 64, algorithms=["HS256"],
                       audience="autre-public")

    def test_aucun_jeton_sans_instance_configuree(self):
        from django.test import override_settings
        from apps.virtualclass.services import (
            JitsiNotConfigured, build_jitsi_jwt,
        )
        with override_settings(**{**self.SETTINGS, "JITSI_DOMAIN": ""}):
            with self.assertRaises(JitsiNotConfigured):
                build_jitsi_jwt(self.eleve_membre, "salle-a")


class JoinLeaveIdempotentsTests(BaseSalles):
    """
    Un double clic ne doit pas produire deux participations, et un départ
    signalé deux fois ne doit pas fausser les durées.
    """

    def client_de(self, u):
        client = APIClient()
        client.force_authenticate(u)
        return client

    def participations(self, u, salle):
        from apps.virtualclass.models import VirtualRoomAttendance
        return VirtualRoomAttendance.objects.filter(room=salle, user=u)

    def test_deux_join_ne_font_qu_une_participation_ouverte(self):
        client = self.client_de(self.eleve_membre)
        client.post(f"/api/virtual-rooms/{self.salle_classe.id}/join/")
        client.post(f"/api/virtual-rooms/{self.salle_classe.id}/join/")
        ouvertes = self.participations(
            self.eleve_membre, self.salle_classe).filter(left_at__isnull=True)
        self.assertLessEqual(
            ouvertes.count(), 1,
            "Un double clic ouvre deux participations : le participant "
            "apparaît en double dans la réunion.")

    def test_leave_est_idempotent(self):
        client = self.client_de(self.eleve_membre)
        client.post(f"/api/virtual-rooms/{self.salle_classe.id}/join/")
        premier = client.post(f"/api/virtual-rooms/{self.salle_classe.id}/leave/")
        second = client.post(f"/api/virtual-rooms/{self.salle_classe.id}/leave/")
        self.assertIn(premier.status_code, (200, 204))
        self.assertIn(
            second.status_code, (200, 204),
            "Un second départ doit être sans effet, pas une erreur : "
            "l'onglet le signale à la fermeture ET au raccrochage.")
        restantes = self.participations(
            self.eleve_membre, self.salle_classe).filter(left_at__isnull=True)
        self.assertEqual(restantes.count(), 0)


class ActivationAutomatiqueDeLAnneeTests(TestCase):
    """
    La règle « la première année d'une académie est active » et sa limite.

    CE QUE CES TESTS EMPÊCHENT DE REVENIR
    -------------------------------------
    L'activation automatique a d'abord été écrite dans `SchoolYear.save()`
    sans distinguer création et mise à jour. Conséquence : une année qu'on
    ENREGISTRAIT à `is_current=False` était aussitôt réactivée — donc le
    bouton « Clôturer » ne clôturait rien. On fermait l'année, elle se
    rouvrait dans le même appel, en silence.

    La correction d'un menu déroulant vide ne doit pas coûter la clôture
    d'une année scolaire. Ces deux tests tiennent les deux bouts.
    """

    def setUp(self):
        self.school = academy("V10_ACT", "Académie activation")

    def test_la_premiere_annee_creee_devient_active(self):
        # Le cas réel : personne ne clique jamais sur « Activer ».
        a = year(self.school, "2025-2026", date(2025, 10, 1))
        a.refresh_from_db()
        self.assertTrue(a.is_current)
        self.assertEqual(active_year(self.school), a)
        self.assertTrue(has_explicit_active_year(self.school))

    def test_une_seconde_annee_ne_vole_pas_l_annee_de_travail(self):
        a = year(self.school, "2025-2026", date(2025, 10, 1))
        b = year(self.school, "2026-2027", date(2026, 9, 1))
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertTrue(a.is_current)
        self.assertFalse(b.is_current)

    def test_cloturer_une_annee_la_laisse_close(self):
        # LE DÉFAUT CORRIGÉ. `is_current=False` sur une année EXISTANTE
        # est une décision de l'administrateur, jamais un oubli à rattraper.
        a = year(self.school, "2025-2026", date(2025, 10, 1))
        a.refresh_from_db()
        self.assertTrue(a.is_current)

        a.is_current = False
        a.save()
        a.refresh_from_db()

        self.assertFalse(a.is_current, "une année clôturée s'est rouverte toute seule")
        self.assertFalse(has_explicit_active_year(self.school))

    def test_une_academie_sans_annee_active_garde_des_classes_visibles(self):
        # Le repli de lecture prend le relais : aucune année n'est
        # rouverte, mais les listes déroulantes ne tombent pas à zéro.
        a = year(self.school, "2025-2026", date(2025, 10, 1))
        a.is_current = False
        a.save()

        c = klass(a, "CM2-A")
        self.assertFalse(has_explicit_active_year(self.school))
        self.assertEqual(active_year(self.school), a)
        self.assertIn(c, Class.objects.filter(school_year=active_year(self.school)))
