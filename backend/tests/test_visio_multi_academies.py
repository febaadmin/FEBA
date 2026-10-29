"""
Visioconférence pour TOUTES les académies, FEBA comprise, sans fuite.

Défauts reproduits sur le code livré (FEBA_VERSION_FINALE_VALIDEE_PRODUCTION) :
  - FEBA (type « campus ») : virtual_classrooms et video_conferencing
    désactivés par défaut → 403 sur toute l'API des salles, menu masqué ;
  - une salle pouvait viser la classe, la matière ou l'année scolaire
    d'une AUTRE académie (aucun contrôle des relations écrites) ;
  - un super administrateur sans académie sélectionnée créait une salle
    sans académie (erreur serveur) ;
  - un enseignant pouvait modifier, supprimer ou fermer n'importe quelle
    salle de l'académie, y compris celles de l'administration.

Le serveur plugNmeet est simulé au niveau du transport HTTP (même
technique que test_plugnmeet_integration) ; la validation réelle est
faite séparément contre une instance plugNmeet locale.
"""
import datetime
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher
from apps.virtualclass import plugnmeet
from apps.virtualclass.models import VirtualRoom, VirtualRoomAttendance, VirtualRoomEvent
from tests.test_plugnmeet_integration import PNM, FakePlugNmeet, event, signed_webhook


class Acad:
    def __init__(self, code, entity_type, slug):
        self.school = School.objects.create(name=f"Académie {code}", code=code, slug=slug,
                                            address="X", entity_type=entity_type)
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 31), is_current=True)
        level = Level.objects.create(school=self.school, name="CE1", order=1)
        self.cls = Class.objects.create(name=f"CE1-{code}", level=level, school_year=self.year)
        self.other_cls = Class.objects.create(name=f"CE2-{code}", level=level, school_year=self.year)
        self.subject = Subject.objects.create(school=self.school, name="Français", code=f"FR{code}",
                                              coefficient=1, language="fr")
        mk = lambda role, tag: CustomUser.objects.create_user(  # noqa: E731
            username=f"{tag}{code}", email=f"{tag}@{code.lower()}.test", password="Pass1234!",
            role=role, first_name=tag, last_name=code, school=self.school)
        self.admin = mk("admin", "admin")
        self.teacher_user = mk("teacher", "prof")
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.teacher.classes.add(self.cls)
        self.other_teacher_user = mk("teacher", "prof2")
        Teacher.objects.create(user=self.other_teacher_user).classes.add(self.other_cls)
        self.student_user = mk("student", "eleve")
        self.student = Student.objects.create(user=self.student_user, school=self.school, first_name="E",
                                              last_name=code, current_class=self.cls, school_year=self.year)
        self.parent_user = mk("parent", "parent")
        ParentStudent.objects.create(parent=Parent.objects.create(user=self.parent_user), student=self.student)


def api(user, **extra):
    c = APIClient()
    c.force_authenticate(user)
    return c


@override_settings(**PNM)
class VisioBase(TestCase):
    def setUp(self):
        self.feba = Acad("FEBAX", "campus", "feba-x")          # l'académie exclue jusqu'ici
        self.fha = Acad("FHAX", "online", "feba-fha-x")
        self.fake = FakePlugNmeet()
        patcher = mock.patch("apps.virtualclass.plugnmeet.urllib.request.urlopen", side_effect=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create_room(self, acad, user=None, **data):
        payload = {"name": "Cours de français", "duration_minutes": 60, **data}
        return api(user or acad.admin).post("/api/virtual-rooms/", payload, format="json")


class ActivationTests(VisioBase):
    def test_toutes_les_academies_ont_la_visio(self):
        """1, 2 : académies existantes et nouvelle académie."""
        nouvelle = School.objects.create(name="Nouvelle", address="X")
        for school in (self.feba.school, self.fha.school, nouvelle):
            self.assertTrue(school.has_feature("virtual_classrooms"), school.name)
            self.assertTrue(school.has_feature("video_conferencing"), school.name)
        ctx = api(self.feba.admin).get("/api/auth/entity-context/")
        self.assertTrue(ctx.data["features"]["virtual_classrooms"])

    def test_migration_reactive_une_desactivation_explicite_sans_toucher_le_reste(self):
        """19 : la migration de données sur une base existante, réversible."""
        import importlib
        from django.apps import apps as django_apps
        mig = importlib.import_module("apps.schools.migrations.0017_enable_video_for_all_academies")
        self.feba.school.settings = {"features": {"virtual_classrooms": False, "video_conferencing": False,
                                                  "placement_tests": True}, "autre": 1}
        self.feba.school.save(update_fields=["settings"])
        room = VirtualRoom.objects.create(school=self.fha.school, name="Existante", created_by=self.fha.admin)
        mig.enable(django_apps, None)
        self.feba.school.refresh_from_db()
        self.assertTrue(self.feba.school.has_feature("virtual_classrooms"))
        self.assertTrue(self.feba.school.has_feature("placement_tests"))     # autre drapeau intact
        self.assertEqual(self.feba.school.settings["autre"], 1)
        self.assertTrue(VirtualRoom.objects.filter(pk=room.pk, room_code=room.room_code).exists())
        mig.enable(django_apps, None)        # rejouable sans effet
        mig.restore(django_apps, None)
        self.feba.school.refresh_from_db()
        self.assertFalse(self.feba.school.has_feature("virtual_classrooms"))
        self.assertNotIn("features_before_0017", self.feba.school.settings)


class FebaManagesItsRoomsTests(VisioBase):
    def test_admin_feba_cree_modifie_supprime(self):
        """3, 4, 9."""
        r = self.create_room(self.feba, class_obj=self.feba.cls.pk, subject=self.feba.subject.pk,
                             target_roles=["teacher", "student"])
        self.assertEqual(r.status_code, 201, r.data)
        room = VirtualRoom.objects.get(pk=r.data["id"])
        self.assertEqual(room.school, self.feba.school)
        self.assertEqual(room.school_year, self.feba.year)
        self.assertTrue(room.room_code.startswith("feba-x-"))
        c = api(self.feba.admin)
        self.assertEqual(c.patch(f"/api/virtual-rooms/{room.pk}/", {"name": "Renommée"},
                                 format="json").status_code, 200)
        self.assertEqual(c.get("/api/virtual-rooms/").status_code, 200)
        self.assertEqual(c.delete(f"/api/virtual-rooms/{room.pk}/").status_code, 204)

    def test_enseignant_feba_cree_et_ouvre_sa_salle(self):
        """5, 6 : création, ouverture (modérateur), élève et parent rejoignent."""
        r = self.create_room(self.feba, user=self.feba.teacher_user, class_obj=self.feba.cls.pk)
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data["id"]
        j = api(self.feba.teacher_user).post(f"/api/virtual-rooms/{rid}/join/")
        self.assertEqual(j.status_code, 200, j.data)
        self.assertTrue(j.data["moderator"])
        self.assertIn("access_token=", j.data["join_url"])
        for u in (self.feba.student_user, self.feba.parent_user):
            j = api(u).post(f"/api/virtual-rooms/{rid}/join/")
            self.assertEqual(j.status_code, 200, (u.role, j.data))
            self.assertFalse(j.data["moderator"])
        self.assertEqual(VirtualRoomAttendance.objects.filter(room_id=rid).count(), 3)
        # Fermeture par l'enseignant.
        e = api(self.feba.teacher_user).post(f"/api/virtual-rooms/{rid}/end/")
        self.assertEqual(e.status_code, 200)
        self.assertEqual(VirtualRoom.objects.get(pk=rid).status, "ended")

    def test_les_autres_academies_ont_les_memes_fonctions(self):
        """7."""
        for acad in (self.feba, self.fha):
            r = self.create_room(acad, class_obj=acad.cls.pk)
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual(api(acad.student_user).post(f"/api/virtual-rooms/{r.data['id']}/join/")
                             .status_code, 200)
            self.assertEqual(api(acad.admin).get(f"/api/virtual-rooms/{r.data['id']}/participants/")
                             .status_code, 200)

    def test_une_desactivation_explicite_reste_appliquee(self):
        self.feba.school.settings = {"features": {"virtual_classrooms": False, "video_conferencing": False}}
        self.feba.school.save(update_fields=["settings"])
        self.assertEqual(api(self.feba.admin).get("/api/virtual-rooms/").status_code, 403)
        self.assertEqual(self.create_room(self.feba).status_code, 403)


class IsolationTests(VisioBase):
    def setUp(self):
        super().setUp()
        self.room_feba = VirtualRoom.objects.create(
            school=self.feba.school, school_year=self.feba.year, name="FEBA", class_obj=self.feba.cls,
            created_by=self.feba.admin)
        self.room_fha = VirtualRoom.objects.create(
            school=self.fha.school, school_year=self.fha.year, name="FHA", class_obj=self.fha.cls,
            created_by=self.fha.admin)

    def test_listes_cloisonnees(self):
        """10."""
        for acad, mine, other in ((self.feba, self.room_feba, self.room_fha),
                                  (self.fha, self.room_fha, self.room_feba)):
            for u in (acad.admin, acad.teacher_user, acad.student_user, acad.parent_user):
                data = api(u).get("/api/virtual-rooms/", {"page_size": 500}).json()
                ids = {r["id"] for r in data.get("results", data)}
                self.assertIn(mine.id, ids, u.email)
                self.assertNotIn(other.id, ids, u.email)

    def test_acces_par_identifiant_refuse_sans_reveler_l_existence(self):
        """11, 12."""
        for u in (self.feba.admin, self.feba.teacher_user, self.feba.student_user, self.feba.parent_user):
            c = api(u)
            pk = self.room_fha.pk
            self.assertEqual(c.get(f"/api/virtual-rooms/{pk}/").status_code, 404, u.role)
            self.assertEqual(c.post(f"/api/virtual-rooms/{pk}/join/").status_code, 404, u.role)
            self.assertEqual(c.get(f"/api/virtual-rooms/{pk}/participants/").status_code, 404, u.role)
            self.assertIn(c.get(f"/api/virtual-rooms/{pk}/recordings/").status_code, (404,), u.role)
        c = api(self.feba.admin)
        self.assertEqual(c.patch(f"/api/virtual-rooms/{self.room_fha.pk}/", {"name": "x"},
                                 format="json").status_code, 404)
        self.assertEqual(c.delete(f"/api/virtual-rooms/{self.room_fha.pk}/").status_code, 404)
        self.assertEqual(c.post(f"/api/virtual-rooms/{self.room_fha.pk}/end/").status_code, 404)
        c.post("/api/virtual-rooms/bulk-delete/", {"ids": [self.room_fha.pk]}, format="json")
        self.assertTrue(VirtualRoom.objects.filter(pk=self.room_fha.pk).exists())
        self.assertFalse(VirtualRoomAttendance.objects.filter(room=self.room_fha).exists())

    def test_classe_matiere_annee_etrangeres_refusees(self):
        """13 — défaut corrigé : la création acceptait ces identifiants."""
        for field, value in (("class_obj", self.fha.cls.pk), ("subject", self.fha.subject.pk),
                             ("school_year", self.fha.year.pk)):
            r = self.create_room(self.feba, **{field: value})
            self.assertEqual(r.status_code, 400, (field, r.data))
        r = api(self.feba.admin).patch(f"/api/virtual-rooms/{self.room_feba.pk}/",
                                       {"class_obj": self.fha.cls.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(VirtualRoom.objects.filter(school=self.feba.school).count(), 1)

    def test_evenements_et_presences_restent_dans_la_bonne_academie(self):
        """14, 15, 20 : même serveur plugNmeet, aucun mélange."""
        def hook(payload):
            body, token = signed_webhook(payload)
            return self.client.post("/api/virtual-rooms/webhook/", data=body,
                                    content_type="application/json", HTTP_HASH_TOKEN=token)
        hook(event("room_started", self.room_feba, sid="S-FEBA"))
        hook(event("room_started", self.room_fha, sid="S-FHA"))
        ident = lambda u: plugnmeet.identity_for(u)   # noqa: E731
        hook(event("participant_joined", self.room_feba, ident(self.feba.student_user), sid="S-FEBA"))
        # Un élève FHA annoncé dans la salle FEBA (identité forgée ou erreur) : rattaché à personne.
        hook(event("participant_joined", self.room_feba, ident(self.fha.student_user), sid="S-FEBA"))
        hook(event("participant_joined", self.room_fha, ident(self.fha.student_user), sid="S-FHA"))
        feba_att = VirtualRoomAttendance.objects.filter(room=self.room_feba)
        self.assertEqual({a.user_id for a in feba_att}, {self.feba.student_user.id})
        self.assertEqual({a.user_id for a in VirtualRoomAttendance.objects.filter(room=self.room_fha)},
                         {self.fha.student_user.id})
        forged = VirtualRoomEvent.objects.filter(room=self.room_feba,
                                                 identity=ident(self.fha.student_user)).get()
        self.assertIsNone(forged.user)
        # Chaque réunion a son identifiant externe propre.
        self.assertNotEqual(plugnmeet.room_id_for(self.room_feba), plugnmeet.room_id_for(self.room_fha))
        # Les participants d'une salle ne sont visibles que dans son académie.
        self.assertEqual(api(self.fha.admin).get(f"/api/virtual-rooms/{self.room_feba.pk}/participants/")
                         .status_code, 404)

    @override_settings(PLUGNMEET_RECORDING_ENABLED=True)
    def test_enregistrements_proteges(self):
        """16."""
        self.fake.recordings = [{"record_id": "REC-FHA", "room_id": plugnmeet.room_id_for(self.room_fha),
                                 "file_size": 1}]
        r = api(self.feba.admin).post(f"/api/virtual-rooms/{self.room_feba.pk}/recordings/REC-FHA/download/")
        self.assertEqual(r.status_code, 404)        # enregistrement d'une autre salle
        r = api(self.feba.admin).get(f"/api/virtual-rooms/{self.room_fha.pk}/recordings/")
        self.assertEqual(r.status_code, 404)

    def test_tache_de_reconciliation_par_salle(self):
        """17 : la tâche ne ferme que les salles inactives côté plugNmeet, chacune pour soi."""
        from apps.virtualclass.meetings import reconcile_live_rooms
        VirtualRoom.objects.filter(pk__in=[self.room_feba.pk, self.room_fha.pk]).update(status="live")
        self.fake.active = {plugnmeet.room_id_for(self.room_fha): "S-FHA"}
        reconcile_live_rooms()
        self.assertEqual(VirtualRoom.objects.get(pk=self.room_feba.pk).status, "ended")
        self.assertEqual(VirtualRoom.objects.get(pk=self.room_fha.pk).status, "live")


class SuperAdminAndTeacherScopeTests(VisioBase):
    def setUp(self):
        super().setUp()
        self.su = CustomUser.objects.create_user(username="su", email="su@x.test", password="Pass1234!",
                                                 role="superadmin", first_name="S", last_name="U")

    def test_superadmin_sans_academie_ne_cree_rien(self):
        """18."""
        r = api(self.su).post("/api/virtual-rooms/", {"name": "Sans académie"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(VirtualRoom.objects.exists())

    def test_superadmin_dans_le_contexte_d_une_academie(self):
        r = api(self.su).post(f"/api/virtual-rooms/?school_id={self.feba.school.pk}",
                              {"name": "Conseil", "class_obj": self.feba.cls.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(VirtualRoom.objects.get(pk=r.data["id"]).school, self.feba.school)
        r = api(self.su).post(f"/api/virtual-rooms/?school_id={self.feba.school.pk}",
                              {"name": "Mélange", "class_obj": self.fha.cls.pk}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_enseignant_limite_a_ses_salles_et_ses_classes(self):
        admin_room = VirtualRoom.objects.create(school=self.feba.school, school_year=self.feba.year,
                                                name="Assemblée", created_by=self.feba.admin)
        colleague_room = VirtualRoom.objects.create(school=self.feba.school, school_year=self.feba.year,
                                                    name="CE2", class_obj=self.feba.other_cls,
                                                    created_by=self.feba.other_teacher_user)
        own_class_room = VirtualRoom.objects.create(school=self.feba.school, school_year=self.feba.year,
                                                    name="CE1", class_obj=self.feba.cls,
                                                    created_by=self.feba.admin)
        c = api(self.feba.teacher_user)
        listed = c.get("/api/virtual-rooms/", {"page_size": 500}).json()
        flags = {r["id"]: r["can_manage"] for r in listed.get("results", listed)}
        self.assertEqual(flags.get(admin_room.pk), False)
        self.assertEqual(flags.get(own_class_room.pk), True)
        self.assertEqual(c.patch(f"/api/virtual-rooms/{admin_room.pk}/", {"name": "x"},
                                 format="json").status_code, 403)
        self.assertEqual(c.delete(f"/api/virtual-rooms/{admin_room.pk}/").status_code, 403)
        self.assertEqual(c.post(f"/api/virtual-rooms/{admin_room.pk}/end/").status_code, 403)
        self.assertEqual(c.patch(f"/api/virtual-rooms/{own_class_room.pk}/", {"name": "CE1 bis"},
                                 format="json").status_code, 200)
        # Une salle pour une classe qui ne lui est pas confiée : refusée.
        r = self.create_room(self.feba, user=self.feba.teacher_user, class_obj=self.feba.other_cls.pk)
        self.assertEqual(r.status_code, 403)
        c.post("/api/virtual-rooms/bulk-delete/", {"ids": [admin_room.pk, colleague_room.pk]}, format="json")
        self.assertEqual(VirtualRoom.objects.filter(pk__in=[admin_room.pk, colleague_room.pk]).count(), 2)

    def test_eleve_et_parent_ne_creent_pas(self):
        for u in (self.feba.student_user, self.feba.parent_user):
            self.assertEqual(self.create_room(self.feba, user=u).status_code, 403)


class MeetingTabIdentityTests(VisioBase):
    """Titre exact et favicon de l'onglet plugNmeet, d'après la salle (jeton signé)."""

    def setUp(self):
        super().setUp()
        # Les codes réels peuvent déjà exister (migration de données) : ces
        # lignes sont renommées pour que les académies du test les portent.
        School.objects.filter(code__in=["FEBA", "FEBA_FHA"]).exclude(
            pk__in=[self.feba.school.pk, self.fha.school.pk]).update(code=None)
        School.objects.filter(pk=self.feba.school.pk).update(code="FEBA")
        School.objects.filter(pk=self.fha.school.pk).update(code="FEBA_FHA")
        self.feba.school.refresh_from_db()
        self.fha.school.refresh_from_db()
        self.room_feba = VirtualRoom.objects.create(school=self.feba.school, name="Cours CE1",
                                                    created_by=self.feba.admin)
        self.room_fha = VirtualRoom.objects.create(school=self.fha.school, name="French Explorers",
                                                   created_by=self.fha.admin)

    def token(self, room, *, secret=None, exp_delta=600, room_id=None):
        import time
        import jwt
        from tests.test_plugnmeet_integration import KEY, SECRET
        now = int(time.time())
        return jwt.encode({"iss": KEY, "exp": now + exp_delta, "nbf": now - 5, "user_id": "feba-1",
                           "room_id": room_id or plugnmeet.room_id_for(room)}, secret or SECRET,
                          algorithm="HS256")

    def ask(self, token):
        return self.client.post("/api/virtual-rooms/meeting-branding/", {"access_token": token},
                                content_type="application/json")

    def test_titres_exacts_par_academie(self):
        r = self.ask(self.token(self.room_feba))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["meeting_title"], "FEBA - Faith & Excellence Bilingual Academy")
        self.assertIn("/api/schools/public-branding/FEBA/favicon-32.png?v=", r.json()["favicon_32_url"])
        r = self.ask(self.token(self.room_fha))
        self.assertEqual(r.json()["meeting_title"], "FEBA FHA - FEBA")
        self.assertIn("/public-branding/FEBA_FHA/", r.json()["favicon_16_url"])
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://meet.globalfeba.test")
        self.assertNotIn("room", r.json())                     # rien sur la salle elle-même

    def test_jeton_modifie_ou_faux_refuse(self):
        # Même salle FHA, mais jeton re-signé avec un autre secret : refusé.
        self.assertEqual(self.ask(self.token(self.room_fha, secret="autre-secret-" * 4)).status_code, 404)
        # Charge utile modifiée à la main (room_id d'une autre salle) : signature invalide.
        good = self.token(self.room_feba)
        import base64, json
        head, body, sig = good.split(".")
        claims = json.loads(base64.urlsafe_b64decode(body + "=="))
        claims["room_id"] = plugnmeet.room_id_for(self.room_fha)
        forged_body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        self.assertEqual(self.ask(f"{head}.{forged_body}.{sig}").status_code, 404)
        self.assertEqual(self.ask("n'importe quoi").status_code, 404)
        self.assertEqual(self.ask(self.token(None, room_id="salle-inexistante")).status_code, 404)

    def test_onglet_recharge_apres_expiration_mais_pas_au_dela_de_24_h(self):
        self.assertEqual(self.ask(self.token(self.room_fha, exp_delta=-3600)).status_code, 200)
        self.assertEqual(self.ask(self.token(self.room_fha, exp_delta=-3 * 86400)).status_code, 404)

    def test_preflight_cors(self):
        r = self.client.options("/api/virtual-rooms/meeting-branding/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://meet.globalfeba.test")

    def test_la_reponse_d_adhesion_porte_le_titre_de_l_academie(self):
        r = api(self.fha.admin).post(f"/api/virtual-rooms/{self.room_fha.pk}/join/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["meeting_title"], "FEBA FHA - FEBA")
        r = api(self.feba.admin).post(f"/api/virtual-rooms/{self.room_feba.pk}/join/")
        self.assertEqual(r.data["meeting_title"], "FEBA - Faith & Excellence Bilingual Academy")

    def test_le_script_client_est_installe_par_le_script_de_preparation(self):
        """Personnalisation reproductible : fichier versionné + injection idempotente."""
        from tests.repo_root import read_repo_file
        js = read_repo_file("plugnmeet/client-branding/feba-branding.js")
        self.assertIn("/api/virtual-rooms/meeting-branding/", js)
        self.assertIn("pnm_access_token", js)
        setup = read_repo_file("scripts/plugnmeet_setup.sh")
        self.assertIn("feba-branding:start", setup)
        self.assertIn("client-branding/feba-branding.js", setup)
