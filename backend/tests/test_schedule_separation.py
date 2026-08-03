"""
Tests de SÉPARATION DES EMPLOIS DU TEMPS (P3).

Les deux académies ne planifient pas la même chose :
  - FEBA planifie un cours dans une SALLE PHYSIQUE ;
  - FEBA FHA planifie une séance en direct pour un GROUPE EN LIGNE, suivie
    depuis plusieurs fuseaux horaires, donc stockée en UTC.

Ces tests verrouillent quatre exigences :

  1. les deux emplois du temps sont servis par deux endpoints distincts ;
  2. aucun créneau ne peut relier des objets de deux académies ;
  3. une académie ne peut pas utiliser l'emploi du temps de l'autre ;
  4. rien ne peut être créé sans académie explicitement active.

Le point 2 est celui qui ne se voit pas à l'écran : une classe FEBA reliée
à une matière FHA produirait un bulletin incohérent des mois plus tard.
"""
import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schedule.models import ClassSchedule, OnlineSessionSchedule
from apps.schools.models import Level, School, SchoolYear
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class ScheduleSeparationTests(TestCase):
    """Deux académies complètes, chacune avec son propre emploi du temps."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa",
            entity_type="campus", code="SEP-FEBA",
        )
        cls.fha = School.objects.create(
            name="FEBA French Heritage Academy", address="En ligne",
            entity_type="online", code="SEP-FHA",
        )

        cls.ref = {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            level = Level.objects.create(school=school, name=f"Niveau {key}", order=1)
            klass = Class.objects.create(
                school_year=year, level=level, name=f"Groupe {key.upper()}",
            )
            subject = Subject.objects.create(
                school=school, name=f"Français {key}", code=f"FR-{key.upper()}",
            )
            teacher_user = CustomUser.objects.create_user(
                username=f"sep_teacher_{key}", email=f"sep.teacher.{key}@test.io",
                password="Pass1234!", role="teacher", school=school,
                first_name="Prof", last_name=key.upper(),
            )
            teacher = Teacher.objects.create(user=teacher_user)
            admin = CustomUser.objects.create_user(
                username=f"sep_admin_{key}", email=f"sep.admin.{key}@test.io",
                password="Pass1234!", role="admin", school=school,
                first_name="Admin", last_name=key.upper(),
            )
            cls.ref[key] = {
                "school": school, "year": year, "level": level, "class": klass,
                "subject": subject, "teacher": teacher, "admin": admin,
            }

        cls.superadmin = CustomUser.objects.create_user(
            username="sep_super", email="sep.super@test.io", password="Pass1234!",
            role="superadmin", first_name="Super", last_name="Admin",
        )

    # ── 1. Deux endpoints, deux métiers ──────────────────────────────────

    def test_l_emploi_du_temps_feba_ne_contient_aucune_seance_en_ligne(self):
        feba = self.ref["feba"]
        ClassSchedule.objects.create(
            cls=feba["class"], subject=feba["subject"], teacher=feba["teacher"],
            school_year=feba["year"], day_of_week=0,
            start_time=datetime.time(8, 0), end_time=datetime.time(10, 0),
            room="Salle 101",
        )
        fha = self.ref["fha"]
        OnlineSessionSchedule.objects.create(
            academy=self.fha, group=fha["class"], subject=fha["subject"],
            teacher=fha["teacher"], school_year=fha["year"],
            day_of_week=2, start_time_utc=datetime.time(21, 0),
            duration_minutes=60, display_timezone="America/New_York",
        )

        client = auth(APIClient(), "sep.admin.feba@test.io")
        resp = client.get("/api/schedule/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]["room"], "Salle 101")

    def test_les_seances_en_ligne_ont_leur_propre_endpoint(self):
        fha = self.ref["fha"]
        OnlineSessionSchedule.objects.create(
            academy=self.fha, group=fha["class"], subject=fha["subject"],
            school_year=fha["year"], day_of_week=2,
            start_time_utc=datetime.time(21, 0), duration_minutes=90,
        )
        client = auth(APIClient(), "sep.admin.fha@test.io")
        resp = client.get("/api/schedule/online-sessions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]["duration_minutes"], 90)
        self.assertEqual(rows(resp)[0]["academy_code"], "SEP-FHA")

    def test_chaque_ligne_porte_son_academie(self):
        """Sans cette information, le mode consolidé serait illisible."""
        feba = self.ref["feba"]
        ClassSchedule.objects.create(
            cls=feba["class"], subject=feba["subject"], school_year=feba["year"],
            day_of_week=1, start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
        )
        client = auth(APIClient(), "sep.admin.feba@test.io")
        row = rows(client.get("/api/schedule/"))[0]
        self.assertEqual(row["academy_code"], "SEP-FEBA")
        self.assertEqual(row["academy_short_name"], "SEP-FEBA")
        self.assertEqual(row["academy_name"], "FEBA Cotonou")

    # ── 2. Aucune relation inter-académies ───────────────────────────────

    def test_creneau_feba_avec_matiere_fha_est_refuse(self):
        feba, fha = self.ref["feba"], self.ref["fha"]
        with self.assertRaises(ValidationError) as ctx:
            ClassSchedule.objects.create(
                cls=feba["class"], subject=fha["subject"],
                school_year=feba["year"], day_of_week=0,
                start_time=datetime.time(8, 0), end_time=datetime.time(9, 0),
            )
        self.assertIn("inter-académies", str(ctx.exception))

    def test_creneau_feba_avec_enseignant_fha_est_refuse(self):
        feba, fha = self.ref["feba"], self.ref["fha"]
        with self.assertRaises(ValidationError):
            ClassSchedule.objects.create(
                cls=feba["class"], subject=feba["subject"], teacher=fha["teacher"],
                school_year=feba["year"], day_of_week=0,
                start_time=datetime.time(8, 0), end_time=datetime.time(9, 0),
            )

    def test_seance_fha_avec_groupe_feba_est_refusee(self):
        feba, fha = self.ref["feba"], self.ref["fha"]
        with self.assertRaises(ValidationError):
            OnlineSessionSchedule.objects.create(
                academy=self.fha, group=feba["class"], subject=fha["subject"],
                school_year=fha["year"], day_of_week=1,
                start_time_utc=datetime.time(20, 0),
            )

    def test_l_api_refuse_une_relation_inter_academies(self):
        """La règle doit tenir aussi par l'API, pas seulement en Python."""
        feba, fha = self.ref["feba"], self.ref["fha"]
        client = auth(APIClient(), "sep.admin.feba@test.io")
        resp = client.post("/api/schedule/", {
            "cls": feba["class"].id,
            "subject": fha["subject"].id,       # matière de l'AUTRE académie
            "school_year": feba["year"].id,
            "day_of_week": 0,
            "start_time": "08:00", "end_time": "09:00",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 3. Chaque académie reste dans son modèle ─────────────────────────

    def test_une_academie_en_ligne_ne_peut_pas_utiliser_l_emploi_du_temps_presentiel(self):
        fha = self.ref["fha"]
        with self.assertRaises(ValidationError) as ctx:
            ClassSchedule.objects.create(
                cls=fha["class"], subject=fha["subject"], school_year=fha["year"],
                day_of_week=0, start_time=datetime.time(8, 0),
                end_time=datetime.time(9, 0), room="Salle 1",
            )
        self.assertIn("académie en ligne", str(ctx.exception))

    def test_une_ecole_presentielle_ne_peut_pas_creer_de_seance_en_ligne(self):
        feba = self.ref["feba"]
        with self.assertRaises(ValidationError) as ctx:
            OnlineSessionSchedule.objects.create(
                academy=self.feba, group=feba["class"], subject=feba["subject"],
                school_year=feba["year"], day_of_week=0,
                start_time_utc=datetime.time(8, 0),
            )
        self.assertIn("présentielle", str(ctx.exception))

    def test_l_api_des_seances_en_ligne_est_refusee_a_une_academie_presentielle(self):
        """
        Masquer l'onglet dans React ne protégerait rien : l'URL reste
        appelable à la main. Le refus doit venir du serveur.
        """
        client = auth(APIClient(), "sep.admin.feba@test.io")
        resp = client.get("/api/schedule/online-sessions/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_un_admin_fha_ne_voit_pas_les_creneaux_feba(self):
        feba = self.ref["feba"]
        ClassSchedule.objects.create(
            cls=feba["class"], subject=feba["subject"], school_year=feba["year"],
            day_of_week=0, start_time=datetime.time(8, 0), end_time=datetime.time(9, 0),
        )
        client = auth(APIClient(), "sep.admin.fha@test.io")
        self.assertEqual(len(rows(client.get("/api/schedule/"))), 0)

    def test_un_admin_feba_ne_voit_pas_les_seances_fha_par_identifiant(self):
        fha = self.ref["fha"]
        session = OnlineSessionSchedule.objects.create(
            academy=self.fha, group=fha["class"], subject=fha["subject"],
            school_year=fha["year"], day_of_week=3,
            start_time_utc=datetime.time(22, 0),
        )
        client = auth(APIClient(), "sep.admin.feba@test.io")
        resp = client.get(f"/api/schedule/online-sessions/{session.id}/")
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    # ── 4. Rien n'est créé dans une académie implicite ───────────────────

    def test_superadmin_en_mode_consolide_ne_peut_pas_creer_de_creneau(self):
        feba = self.ref["feba"]
        client = auth(APIClient(), "sep.super@test.io")
        client.post("/api/auth/entity-context/switch/", {"entity_id": ""})
        resp = client.post("/api/schedule/", {
            "cls": feba["class"].id, "subject": feba["subject"].id,
            "school_year": feba["year"].id, "day_of_week": 0,
            "start_time": "08:00", "end_time": "09:00",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Toutes les Académies", str(resp.data))

    def test_superadmin_en_mode_consolide_voit_l_union_des_academies(self):
        """
        Exigence explicite : le total du mode consolidé doit être la somme
        des académies, jamais le contenu d'une seule.
        """
        feba, fha = self.ref["feba"], self.ref["fha"]
        autre_campus = School.objects.create(
            name="Campus B", address="Ailleurs", entity_type="campus", code="SEP-B",
        )
        year_b = SchoolYear.objects.create(
            school=autre_campus, name="2025-2026-b", is_current=True,
            start_date="2025-09-01", end_date="2026-07-01",
        )
        level_b = Level.objects.create(school=autre_campus, name="Niveau B", order=1)
        class_b = Class.objects.create(school_year=year_b, level=level_b, name="B1")
        subject_b = Subject.objects.create(school=autre_campus, name="Maths", code="MA-B")

        ClassSchedule.objects.create(
            cls=feba["class"], subject=feba["subject"], school_year=feba["year"],
            day_of_week=0, start_time=datetime.time(8, 0), end_time=datetime.time(9, 0),
        )
        ClassSchedule.objects.create(
            cls=class_b, subject=subject_b, school_year=year_b,
            day_of_week=0, start_time=datetime.time(8, 0), end_time=datetime.time(9, 0),
        )

        client = auth(APIClient(), "sep.super@test.io")

        client.post("/api/auth/entity-context/switch/", {"entity_id": self.feba.id})
        total_feba = len(rows(client.get("/api/schedule/")))

        client.post("/api/auth/entity-context/switch/", {"entity_id": autre_campus.id})
        total_b = len(rows(client.get("/api/schedule/")))

        client.post("/api/auth/entity-context/switch/", {"entity_id": ""})
        total_all = len(rows(client.get("/api/schedule/")))

        self.assertEqual(total_all, total_feba + total_b)
        self.assertEqual(total_all, 2)
        codes = {row["academy_code"] for row in rows(client.get("/api/schedule/"))}
        self.assertEqual(codes, {"SEP-FEBA", "SEP-B"})
        self.assertTrue(fha)  # l'académie en ligne n'apparaît pas ici


class OnlineSessionTimeTests(TestCase):
    """
    Conversion horaire des séances en ligne.

    Une séance suivie depuis Philadelphie, Vancouver et Cotonou doit
    désigner le MÊME instant pour tout le monde : l'heure de référence est
    donc en UTC, et la conversion peut changer le jour affiché.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fha = School.objects.create(
            name="FEBA FHA", address="En ligne", entity_type="online", code="TZ-FHA",
            timezone="America/New_York",
        )
        year = SchoolYear.objects.create(
            school=cls.fha, name="2025-2026", is_current=True,
            start_date="2025-09-01", end_date="2026-07-01",
        )
        level = Level.objects.create(school=cls.fha, name="French Explorers", order=1)
        group = Class.objects.create(school_year=year, level=level, name="French Explorers")
        subject = Subject.objects.create(school=cls.fha, name="Français", code="FR")
        cls.session = OnlineSessionSchedule.objects.create(
            academy=cls.fha, group=group, subject=subject, school_year=year,
            # Mardi 00 h 30 UTC = lundi 19 h 30 à New York (heure d'hiver).
            day_of_week=1, start_time_utc=datetime.time(0, 30),
            duration_minutes=75, display_timezone="America/New_York",
        )

    def test_l_heure_de_fin_est_derivee_de_la_duree(self):
        self.assertEqual(self.session.end_time_utc, datetime.time(1, 45))

    def test_la_conversion_locale_peut_changer_de_jour(self):
        """
        Sans cela, l'interface annoncerait « mardi » à des familles dont la
        séance a lieu le lundi soir.
        """
        local = self.session.local_start("America/New_York")
        self.assertEqual(local.weekday(), 0)  # lundi
        self.assertEqual(local.strftime("%H:%M"), "19:30")

    def test_deux_fuseaux_voient_le_meme_instant(self):
        est = self.session.local_start("America/New_York")
        cotonou = self.session.local_start("Africa/Porto-Novo")
        self.assertEqual(est.utctimetuple(), cotonou.utctimetuple())

    def test_un_fuseau_inconnu_retombe_sur_l_utc_sans_planter(self):
        local = self.session.local_start("Mars/Olympus_Mons")
        self.assertIsNotNone(local)
        self.assertEqual(local.strftime("%H:%M"), "00:30")

    def test_une_duree_hors_bornes_est_refusee(self):
        with self.assertRaises(ValidationError):
            OnlineSessionSchedule.objects.create(
                academy=self.fha, group=self.session.group,
                subject=self.session.subject, school_year=self.session.school_year,
                day_of_week=4, start_time_utc=datetime.time(10, 0),
                duration_minutes=600,
            )

    def test_aucun_lien_de_visioconference_permanent_n_est_publie(self):
        """
        Rejoindre exige un jeton signé, lié à l'utilisateur et valable
        quinze minutes. Publier une URL Jitsi fixe dans l'emploi du temps
        la rendrait utilisable par quiconque la recopie.
        """
        self.assertEqual(self.session.join_endpoint, "")


class ScheduleCrudSeparationTests(TestCase):
    """
    CRUD complet, académie par académie.

    Lire séparément ne suffit pas : si la modification ou la suppression
    traversent la frontière, deux académies partagent en pratique le même
    emploi du temps. Ces tests couvrent les quatre opérations.
    """

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa", entity_type="campus", code="CRUD-FEBA",
        )
        cls.fha = School.objects.create(
            name="FEBA FHA", address="En ligne", entity_type="online", code="CRUD-FHA",
        )
        cls.ref = {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            level = Level.objects.create(school=school, name=f"N-{key}", order=1)
            klass = Class.objects.create(school_year=year, level=level, name=f"G-{key}")
            subject = Subject.objects.create(school=school, name=f"FR {key}", code=f"C-{key}")
            CustomUser.objects.create_user(
                username=f"crud_admin_{key}", email=f"crud.admin.{key}@test.io",
                password="Pass1234!", role="admin", school=school,
                first_name="Admin", last_name=key.upper(),
            )
            cls.ref[key] = {"year": year, "class": klass, "subject": subject}

    def test_creation_lecture_modification_suppression_cote_feba(self):
        feba = self.ref["feba"]
        client = auth(APIClient(), "crud.admin.feba@test.io")

        created = client.post("/api/schedule/", {
            "cls": feba["class"].id, "subject": feba["subject"].id,
            "school_year": feba["year"].id, "day_of_week": 0,
            "start_time": "08:00", "end_time": "09:00", "room": "Salle 12",
        })
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        slot_id = created.data["id"]

        self.assertEqual(len(rows(client.get("/api/schedule/"))), 1)

        updated = client.patch(f"/api/schedule/{slot_id}/", {"room": "Salle 13"})
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["room"], "Salle 13")

        removed = client.delete(f"/api/schedule/{slot_id}/")
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(rows(client.get("/api/schedule/"))), 0)

    def test_creation_lecture_modification_suppression_cote_fha(self):
        fha = self.ref["fha"]
        client = auth(APIClient(), "crud.admin.fha@test.io")

        created = client.post("/api/schedule/online-sessions/", {
            "group": fha["class"].id, "subject": fha["subject"].id,
            "school_year": fha["year"].id, "day_of_week": 2,
            "start_time_utc": "21:00", "duration_minutes": 60,
            "display_timezone": "America/New_York",
            "reminders_enabled": True, "reminder_minutes_before": 30,
        })
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        session_id = created.data["id"]
        # L'académie n'est jamais lue depuis le payload : elle vient du serveur.
        self.assertEqual(created.data["academy_code"], "CRUD-FHA")

        self.assertEqual(len(rows(client.get("/api/schedule/online-sessions/"))), 1)

        updated = client.patch(f"/api/schedule/online-sessions/{session_id}/",
                               {"duration_minutes": 45})
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["duration_minutes"], 45)
        self.assertEqual(updated.data["end_time_utc"], "21:45")

        removed = client.delete(f"/api/schedule/online-sessions/{session_id}/")
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(rows(client.get("/api/schedule/online-sessions/"))), 0)

    def test_un_admin_ne_peut_pas_modifier_le_creneau_de_l_autre_academie(self):
        feba = self.ref["feba"]
        slot = ClassSchedule.objects.create(
            cls=feba["class"], subject=feba["subject"], school_year=feba["year"],
            day_of_week=0, start_time=datetime.time(8, 0), end_time=datetime.time(9, 0),
        )
        client = auth(APIClient(), "crud.admin.fha@test.io")
        resp = client.patch(f"/api/schedule/{slot.id}/", {"room": "Piraté"})
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        slot.refresh_from_db()
        self.assertNotEqual(slot.room, "Piraté")

    def test_un_admin_ne_peut_pas_supprimer_la_seance_de_l_autre_academie(self):
        fha = self.ref["fha"]
        session = OnlineSessionSchedule.objects.create(
            academy=self.fha, group=fha["class"], subject=fha["subject"],
            school_year=fha["year"], day_of_week=1, start_time_utc=datetime.time(20, 0),
        )
        client = auth(APIClient(), "crud.admin.feba@test.io")
        resp = client.delete(f"/api/schedule/online-sessions/{session.id}/")
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertTrue(OnlineSessionSchedule.objects.filter(pk=session.pk).exists())

    def test_l_academie_d_une_seance_ne_peut_pas_etre_deplacee(self):
        """
        Déplacer une séance vers l'autre académie casserait toutes ses
        relations (groupe, matière, enseignant, salle virtuelle) sans
        qu'aucune d'elles ne soit signalée comme incohérente.
        """
        fha = self.ref["fha"]
        session = OnlineSessionSchedule.objects.create(
            academy=self.fha, group=fha["class"], subject=fha["subject"],
            school_year=fha["year"], day_of_week=1, start_time_utc=datetime.time(20, 0),
        )
        client = auth(APIClient(), "crud.admin.fha@test.io")
        resp = client.patch(f"/api/schedule/online-sessions/{session.id}/",
                            {"academy": self.feba.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.academy_id, self.fha.id)
