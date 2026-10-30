"""
Intégration plugNmeet : contrat d'API, droits FEBA, présences, webhooks.

Les appels sortants sont interceptés au niveau du transport HTTP
(`urllib.request.urlopen`) : on vérifie la REQUÊTE réellement émise
(chemin, en-têtes, signature HMAC du corps exact), pas un mock de haut
niveau. Le comportement réel du serveur plugNmeet (v2.5.3) est vérifié
séparément par `PlugNmeetLiveTests`, exécuté contre une instance réelle
quand PLUGNMEET_TEST_URL est défini.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import time
import uuid
from datetime import timedelta
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.virtualclass import meetings, plugnmeet
from apps.virtualclass.models import VirtualRoom, VirtualRoomAttendance, VirtualRoomEvent
from tests import test_v10_academy_scope_and_rooms as base

KEY = "APIfebatest"
SECRET = "secret-plugnmeet-de-test-uniquement-000000"
PNM = dict(VIDEO_PROVIDER="plugnmeet", PLUGNMEET_SERVER_URL="https://meet.globalfeba.test",
           PLUGNMEET_INTERNAL_URL="", PLUGNMEET_API_KEY=KEY, PLUGNMEET_API_SECRET=SECRET,
           PLUGNMEET_WEBHOOK_URL="https://globalfeba.test/api/virtual-rooms/webhook/",
           PUBLIC_BASE_URL="https://globalfeba.test", PLUGNMEET_RECORDING_ENABLED=False)


class FakePlugNmeet:
    """Transport HTTP simulé : enregistre chaque requête, répond comme plugNmeet."""

    def __init__(self):
        self.requests = []
        self.active = {}
        self.fail = None
        self.recordings = []

    def __call__(self, request, timeout=None):
        if self.fail:
            raise self.fail
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/healthCheck"):
            return _resp({"status": True})
        body = request.data
        self.requests.append({"url": url, "headers": dict(request.header_items()), "body": body})
        data = json.loads(body)
        method = url.split("/auth", 1)[1]
        if method == "/room/create":
            rid = data["room_id"]
            sid = self.active.setdefault(rid, str(uuid.uuid4()))
            return _resp({"status": True, "msg": "success", "room_info": {"room_id": rid, "sid": sid}})
        if method == "/room/getJoinToken":
            return _resp({"status": True, "token": f"tok-{uuid.uuid4().hex}"})
        if method == "/room/isRoomActive":
            return _resp({"status": True, "is_active": data["room_id"] in self.active})
        if method == "/room/endRoom":
            if self.active.pop(data["room_id"], None) is None:
                # Réponse réelle de plugNmeet v2.5.3 (mesurée sur l'instance).
                return _resp({"status": False, "msg": "room not found or not active",
                              "status_code": "ROOM_NOT_FOUND"})
            return _resp({"status": True})
        if method == "/recording/fetch":
            return _resp({"status": True, "result": {"recordings_list": self.recordings}})
        if method == "/recording/info":
            match = [r for r in self.recordings if r["record_id"] == data["record_id"]]
            if not match:
                return _resp({"status": False, "msg": "not found", "status_code": "NOT_FOUND"})
            return _resp({"status": True, "recording_info": match[0]})
        if method == "/recording/getDownloadToken":
            return _resp({"status": True, "token": "dl-token"})
        raise AssertionError(f"méthode inattendue {method}")


class _Ctx(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _resp(payload):
    return _Ctx(json.dumps(payload).encode())


def signed_webhook(event, *, secret=SECRET, key=KEY, exp_delta=300, tamper=False):
    body = json.dumps(event).encode()
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    token = jwt.encode({"iss": key, "exp": int(time.time()) + exp_delta, "nbf": int(time.time()) - 5,
                        "sha256": digest}, secret, algorithm="HS256")
    if tamper:
        body = body.replace(b"participant", b"participanT", 1)
    return body, token


def event(name, room, identity=None, at=None, sid="sid-1", event_id=None, metadata=None):
    payload = {"event": name, "id": event_id or str(uuid.uuid4()),
               "created_at": int((at or timezone.now()).timestamp()),
               "room": {"room_id": room if isinstance(room, str) else room.room_code, "sid": sid}}
    if metadata is not None:
        payload["room"]["metadata"] = json.dumps(metadata)
    if identity:
        payload["participant"] = {"identity": identity, "sid": f"PA_{identity}"}
    return payload


@override_settings(**PNM)
class PlugNmeetBase(base.BaseSalles):
    def setUp(self):
        super().setUp()
        self.fake = FakePlugNmeet()
        patcher = mock.patch("apps.virtualclass.plugnmeet.urllib.request.urlopen", side_effect=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post_webhook(self, payload, **kw):
        body, token = signed_webhook(payload, **kw)
        return self.client.post("/api/virtual-rooms/webhook/", data=body, content_type="application/json",
                                HTTP_HASH_TOKEN=token)


class ApiContractTests(PlugNmeetBase):
    def test_signature_hmac_du_corps_exact_et_aucun_secret_transmis(self):
        info = plugnmeet.create_room(self.salle_classe)
        sent = self.fake.requests[0]
        self.assertEqual(sent["url"], "https://meet.globalfeba.test/auth/room/create")
        headers = {k.lower(): v for k, v in sent["headers"].items()}
        self.assertEqual(headers["api-key"], KEY)
        expected = hmac.new(SECRET.encode(), sent["body"], hashlib.sha256).hexdigest()
        self.assertEqual(headers["hash-signature"], expected)
        self.assertNotIn(SECRET.encode(), sent["body"])
        self.assertTrue(info["sid"])

    def test_toutes_les_fonctions_declarees_explicitement(self):
        """Vérifié sur l'instance réelle : une fonction omise est ACTIVÉE par défaut."""
        f = plugnmeet.room_features(self.salle_classe)
        for block in ("recording_features", "chat_features", "shared_note_pad_features",
                      "whiteboard_features", "external_media_player_features",
                      "external_broadcasting_features", "waiting_room_features",
                      "breakout_room_features", "display_external_link_features",
                      "ingress_features", "polls_features", "insights_features",
                      "sip_dial_in_features", "end_to_end_encryption_features"):
            self.assertIn(block, f)
        self.assertFalse(f["recording_features"]["is_allow"])
        self.assertFalse(f["recording_features"]["is_allow_local"])
        self.assertFalse(f["external_broadcasting_features"]["is_allow_rtmp"])
        self.assertFalse(f["ingress_features"]["is_allow"])
        self.assertFalse(f["insights_features"]["is_allow"])
        self.assertFalse(f["insights_features"]["ai_features"]["meeting_summarization_features"]["is_allow"])
        self.assertTrue(f["breakout_room_features"]["is_allow"])
        self.assertTrue(f["polls_features"]["is_allow"])
        self.assertTrue(f["whiteboard_features"]["is_allow"])
        # Etherpad absent : pas de bouton sans effet.
        self.assertFalse(f["shared_note_pad_features"]["is_allow"])

    def test_enregistrement_seulement_si_service_ET_salle(self):
        self.salle_classe.allow_recording = True
        self.assertFalse(plugnmeet.room_features(self.salle_classe)["recording_features"]["is_allow"])
        with override_settings(PLUGNMEET_RECORDING_ENABLED=True):
            self.assertTrue(plugnmeet.room_features(self.salle_classe)["recording_features"]["is_allow"])
            self.salle_classe.allow_recording = False
            self.assertFalse(plugnmeet.room_features(self.salle_classe)["recording_features"]["is_allow"])

    def test_identifiant_de_salle_limite_a_64(self):
        self.salle_classe.room_code = "x" * 80
        rid = plugnmeet.room_id_for(self.salle_classe)
        self.assertEqual(len(rid), 64)
        self.assertEqual(rid, plugnmeet.room_id_for(self.salle_classe))


class JoinTests(PlugNmeetBase):
    def join(self, u, room=None):
        return self.api(u).post(f"/api/virtual-rooms/{(room or self.salle_classe).pk}/join/")

    def test_eleve_de_la_classe_recoit_une_url_a_usage_unique(self):
        r = self.join(self.eleve_membre)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(data["provider"], "plugnmeet")
        self.assertTrue(data["join_url"].startswith("https://meet.globalfeba.test/?access_token=tok-"))
        self.assertFalse(data["moderator"])
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertNotIn(SECRET, r.content.decode())
        self.assertNotIn(KEY, r.content.decode())
        token_req = json.loads(self.fake.requests[1]["body"])
        self.assertEqual(token_req["user_info"]["user_id"], f"feba-{self.eleve_membre.pk}")
        self.assertFalse(token_req["user_info"]["is_admin"])
        att = VirtualRoomAttendance.objects.get(user=self.eleve_membre)
        self.salle_classe.refresh_from_db()
        self.assertEqual(att.session_sid, self.salle_classe.meeting_sid)
        self.assertEqual(self.salle_classe.status, "live")

    def test_enseignant_affecte_est_moderateur(self):
        self.join(self.prof_affecte)
        token_req = json.loads(self.fake.requests[1]["body"])
        self.assertTrue(token_req["user_info"]["is_admin"])

    def test_refus_classe_autre_academie_et_aucun_appel_plugnmeet(self):
        self.assertEqual(self.join(self.eleve_autre).status_code, 403)
        self.assertEqual(self.join(self.prof_autre).status_code, 403)
        # Autre académie : refus AVANT toute recherche de salle (403 : FEBA
        # n'a pas les salles virtuelles) ou 404 (existence non révélée).
        self.assertIn(self.join(self.eleve_feba).status_code, (403, 404))
        self.assertEqual(self.fake.requests, [])

    def test_autre_academie_dotee_des_salles_404_sans_reveler_la_salle(self):
        settings_ = dict(self.feba.settings or {})
        settings_["features"] = {**settings_.get("features", {}), "virtual_classrooms": True,
                                 "video_conferencing": True}
        self.feba.settings = settings_
        self.feba.save(update_fields=["settings"])
        self.assertEqual(self.join(self.eleve_feba).status_code, 404)
        self.assertEqual(self.fake.requests, [])

    def test_double_adhesion_meme_reunion_une_seule_presence(self):
        self.join(self.eleve_membre)
        self.join(self.eleve_membre)
        self.assertEqual(VirtualRoomAttendance.objects.filter(user=self.eleve_membre).count(), 1)

    def test_salle_fermee_eleve_refuse_enseignant_rouvre(self):
        self.salle_classe.status = "ended"
        self.salle_classe.save()
        r = self.join(self.eleve_membre)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(self.join(self.prof_affecte).status_code, 200)
        self.salle_classe.refresh_from_db()
        self.assertEqual(self.salle_classe.status, "live")

    def test_serveur_injoignable_503_explicite(self):
        import urllib.error
        self.fake.fail = urllib.error.URLError("connexion refusée")
        r = self.join(self.eleve_membre)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["code"], "video_unavailable")
        self.assertFalse(VirtualRoomAttendance.objects.exists())

    @override_settings(PLUGNMEET_API_SECRET="")
    def test_non_configure_503_jamais_de_repli_public(self):
        r = self.join(self.eleve_membre)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["code"], "video_not_configured")


class EndAndStatusTests(PlugNmeetBase):
    def test_fermeture_reelle_puis_statut_et_presences(self):
        self.api(self.eleve_membre).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        r = self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/end/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("/auth/room/endRoom", self.fake.requests[-1]["url"])
        # Seconde fermeture : plugNmeet n'est pas rappelé pour une réunion close.
        before = len(self.fake.requests)
        self.assertFalse(plugnmeet.end_room(self.salle_classe))
        self.assertEqual([r["url"].split("/auth")[1] for r in self.fake.requests[before:]], ["/room/isRoomActive"])
        self.salle_classe.refresh_from_db()
        self.assertEqual(self.salle_classe.status, "ended")
        att = VirtualRoomAttendance.objects.get(user=self.eleve_membre)
        self.assertIsNotNone(att.left_at)

    def test_eleve_ne_peut_pas_fermer(self):
        r = self.api(self.eleve_membre).post(f"/api/virtual-rooms/{self.salle_classe.pk}/end/")
        self.assertEqual(r.status_code, 403)

    def test_serveur_injoignable_la_salle_reste_en_cours(self):
        import urllib.error
        self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        self.fake.fail = urllib.error.URLError("down")
        r = self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/end/")
        self.assertEqual(r.status_code, 503)
        self.salle_classe.refresh_from_db()
        self.assertEqual(self.salle_classe.status, "live")

    def test_statut_reel_resynchronise(self):
        self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        self.fake.active.clear()  # réunion fermée côté plugNmeet (vide, délai dépassé)
        r = self.api(self.eleve_membre).get(f"/api/virtual-rooms/{self.salle_classe.pk}/meeting-status/")
        self.assertEqual(r.json(), {"provider": "plugnmeet", "status": "ended", "active": False})

    def test_reconciliation_periodique(self):
        self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        self.fake.active.clear()
        self.assertEqual(meetings.reconcile_live_rooms(), 1)
        self.salle_classe.refresh_from_db()
        self.assertEqual(self.salle_classe.status, "ended")

    def test_reconciliation_ne_conclut_rien_si_plugnmeet_est_en_panne(self):
        import urllib.error
        self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        self.fake.fail = urllib.error.URLError("down")
        self.assertEqual(meetings.reconcile_live_rooms(), 0)
        self.salle_classe.refresh_from_db()
        self.assertEqual(self.salle_classe.status, "live")


class WebhookSecurityTests(PlugNmeetBase):
    def test_signature_valide_acceptee(self):
        r = self.post_webhook(event("room_started", self.salle_classe))
        self.assertEqual(r.status_code, 200, r.content)

    def test_refus_signature_invalide_corps_altere_expire_mauvais_emetteur(self):
        e = event("participant_joined", self.salle_classe, f"feba-{self.eleve_membre.pk}")
        for kw in ({"secret": "autre-secret-xxxxxxxxxxxxxxxxxxxxxxxx"}, {"tamper": True},
                   {"exp_delta": -120}, {"key": "APIautre"}):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                self.assertEqual(self.post_webhook(e, **kw).status_code, 401)
        self.assertEqual(self.client.post("/api/virtual-rooms/webhook/", data=json.dumps(e),
                                          content_type="application/json").status_code, 401)
        self.assertFalse(VirtualRoomEvent.objects.exists())

    def test_utilisateur_d_une_autre_academie_jamais_rattache(self):
        self.post_webhook(event("participant_joined", self.salle_classe, f"feba-{self.eleve_feba.pk}"))
        ev = VirtualRoomEvent.objects.get()
        self.assertIsNone(ev.user)
        self.assertFalse(VirtualRoomAttendance.objects.exists())


class AttendanceFromEventsTests(PlugNmeetBase):
    def setUp(self):
        super().setUp()
        self.t0 = timezone.now().replace(microsecond=0) - timedelta(hours=2)
        self.ident = f"feba-{self.eleve_membre.pk}"

    def at(self, minutes):
        return self.t0 + timedelta(minutes=minutes)

    def att(self):
        return VirtualRoomAttendance.objects.get(user=self.eleve_membre, session_sid="sid-1")

    def test_reconnexion_duree_effective_et_idempotence(self):
        evts = [event("participant_joined", self.salle_classe, self.ident, self.at(0)),
                event("participant_left", self.salle_classe, self.ident, self.at(20)),
                event("participant_joined", self.salle_classe, self.ident, self.at(22)),
                event("participant_left", self.salle_classe, self.ident, self.at(62))]
        for e in evts:
            self.assertEqual(self.post_webhook(e).status_code, 200)
        for e in evts:  # plugNmeet rejoue (réseau) : aucun effet
            self.assertTrue(self.post_webhook(e).json()["duplicate"])
        a = self.att()
        self.assertEqual(a.reconnections, 1)
        self.assertEqual(a.duration_seconds, 60 * 60)          # 20 + 40 min, pas 62
        self.assertEqual(a.joined_at, self.at(0))
        self.assertEqual(a.left_at, self.at(62))
        self.assertEqual(a.source, "webhook")
        self.assertEqual(VirtualRoomEvent.objects.count(), 4)

    def test_evenements_dans_le_desordre_meme_resultat(self):
        evts = [event("participant_left", self.salle_classe, self.ident, self.at(62)),
                event("participant_joined", self.salle_classe, self.ident, self.at(22)),
                event("participant_left", self.salle_classe, self.ident, self.at(20)),
                event("participant_joined", self.salle_classe, self.ident, self.at(0))]
        for e in evts:
            self.post_webhook(e)
        a = self.att()
        self.assertEqual((a.reconnections, a.duration_seconds, a.left_at), (1, 3600, self.at(62)))

    def test_lien_demande_sans_connexion_duree_nulle(self):
        """
        Constaté en recette locale le 29/10/2026 : un participant qui demande
        le lien sans jamais se connecter recevait toute la durée de la
        réunion (présence « api » close à la fin). Quand les webhooks
        fonctionnent pour la séance, une présence restée « api » signifie
        qu'il n'est jamais entré : durée nulle.
        """
        jamais = VirtualRoomAttendance.objects.create(
            room=self.salle_classe, user=self.prof_affecte, session_sid="sid-1", joined_at=self.at(1))
        self.post_webhook(event("room_started", self.salle_classe, at=self.at(0)))
        self.post_webhook(event("participant_joined", self.salle_classe, self.ident, self.at(2)))
        self.post_webhook(event("room_finished", self.salle_classe, at=self.at(65)))
        jamais.refresh_from_db()
        self.assertEqual((jamais.left_at, jamais.duration_seconds), (self.at(1), 0))
        self.assertEqual(jamais.source, "api")
        self.assertEqual(self.att().duration_seconds, 63 * 60)  # l'élève connecté, inchangé

    def test_sans_aucun_webhook_le_repli_par_appels_est_conserve(self):
        """Webhooks absents (non configurés, refusés) : durée depuis la demande."""
        a = VirtualRoomAttendance.objects.create(
            room=self.salle_classe, user=self.prof_affecte, session_sid="sid-1", joined_at=self.at(1))
        meetings.close_open_attendances(self.salle_classe, at=self.at(31), session_sid="sid-1")
        a.refresh_from_db()
        self.assertEqual((a.left_at, a.duration_seconds), (self.at(31), 30 * 60))

    def test_deconnexion_brutale_close_par_la_fin_de_reunion(self):
        self.post_webhook(event("room_started", self.salle_classe, at=self.at(0)))
        self.post_webhook(event("participant_joined", self.salle_classe, self.ident, self.at(5)))
        self.assertIsNone(self.att().left_at)  # toujours présent
        self.post_webhook(event("room_finished", self.salle_classe, at=self.at(65)))
        a = self.att()
        self.assertEqual(a.left_at, self.at(65))
        self.assertEqual(a.duration_seconds, 60 * 60)
        self.salle_classe.refresh_from_db()
        self.assertEqual(self.salle_classe.status, "ended")

    def test_connexions_simultanees_plusieurs_participants(self):
        prof = f"feba-{self.prof_affecte.pk}"
        for e in (event("participant_joined", self.salle_classe, prof, self.at(0)),
                  event("participant_joined", self.salle_classe, self.ident, self.at(1)),
                  event("participant_left", self.salle_classe, self.ident, self.at(31)),
                  event("participant_left", self.salle_classe, prof, self.at(45))):
            self.post_webhook(e)
        self.assertEqual(self.att().duration_seconds, 30 * 60)
        self.assertEqual(VirtualRoomAttendance.objects.get(user=self.prof_affecte).duration_seconds, 45 * 60)

    def test_sous_groupe_compte_comme_presence_au_cours(self):
        self.salle_classe.meeting_sid = "sid-1"
        self.salle_classe.save()
        meta = {"parent_room_id": self.salle_classe.room_code, "is_breakout_room": True}
        for e in (event("participant_joined", self.salle_classe, self.ident, self.at(0)),
                  event("participant_left", self.salle_classe, self.ident, self.at(10)),
                  event("participant_joined", "breakout-1", self.ident, self.at(10), sid="sid-br", metadata=meta),
                  event("participant_left", "breakout-1", self.ident, self.at(30), sid="sid-br", metadata=meta)):
            self.post_webhook(e)
        a = self.att()
        self.assertEqual(a.duration_seconds, 30 * 60)
        self.assertEqual(a.reconnections, 1)

    def test_entree_perdue_presence_depuis_l_adhesion_feba(self):
        """Constaté en réel : l'entrée refusée (400), seule la sortie arrive."""
        VirtualRoomAttendance.objects.create(room=self.salle_classe, user=self.eleve_membre,
                                             session_sid="sid-1", joined_at=self.at(0))
        self.post_webhook(event("participant_left", self.salle_classe, self.ident, self.at(25)))
        a = self.att()
        self.assertEqual((a.duration_seconds, a.left_at, a.joined_at), (25 * 60, self.at(25), self.at(0)))
        self.post_webhook(event("participant_left", self.salle_classe, self.ident, self.at(25)))
        self.assertEqual(self.att().duration_seconds, 25 * 60)

    def test_evenements_secondaires_non_archives(self):
        r = self.post_webhook(event("track_published", self.salle_classe, self.ident, self.at(1)))
        self.assertEqual(r.json()["stored"], False)
        self.assertFalse(VirtualRoomEvent.objects.exists())

    def test_lie_a_l_inscription_annuelle(self):
        from apps.students.models import StudentEnrollment
        student = self.eleve_membre.student_profile
        enrollment = StudentEnrollment.objects.filter(student=student, school_year=self.fha_2026).first()
        self.post_webhook(event("participant_joined", self.salle_classe, self.ident, self.at(0)))
        self.assertEqual(self.att().enrollment, enrollment)

    def test_depart_navigateur_n_ecrase_pas_les_evenements(self):
        self.post_webhook(event("participant_joined", self.salle_classe, self.ident, self.at(0)))
        r = self.api(self.eleve_membre).post(f"/api/virtual-rooms/{self.salle_classe.pk}/leave/")
        self.assertEqual(r.json()["source"], "webhook")
        self.assertIsNone(self.att().left_at)


class RecordingsTests(PlugNmeetBase):
    def test_desactive_par_defaut(self):
        r = self.api(self.eleve_membre).get(f"/api/virtual-rooms/{self.salle_classe.pk}/recordings/")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["code"], "recording_disabled")

    @override_settings(PLUGNMEET_RECORDING_ENABLED=True)
    def test_lien_temporaire_seulement_pour_la_bonne_salle(self):
        rid = plugnmeet.room_id_for(self.salle_classe)
        self.fake.recordings = [{"record_id": "REC-1", "room_id": rid, "file_size": 12},
                                {"record_id": "REC-AUTRE", "room_id": "autre-salle"}]
        lst = self.api(self.eleve_membre).get(f"/api/virtual-rooms/{self.salle_classe.pk}/recordings/")
        self.assertEqual(lst.status_code, 200)
        ok = self.api(self.eleve_membre).post(f"/api/virtual-rooms/{self.salle_classe.pk}/recordings/REC-1/download/")
        self.assertEqual(ok.json()["url"], "https://meet.globalfeba.test/download/recording/dl-token")
        autre = self.api(self.eleve_membre).post(
            f"/api/virtual-rooms/{self.salle_classe.pk}/recordings/REC-AUTRE/download/")
        self.assertEqual(autre.status_code, 404)
        refus = self.api(self.eleve_autre).get(f"/api/virtual-rooms/{self.salle_classe.pk}/recordings/")
        self.assertEqual(refus.status_code, 403)
        hors = self.api(self.eleve_feba).get(f"/api/virtual-rooms/{self.salle_classe.pk}/recordings/")
        self.assertIn(hors.status_code, (403, 404))


class HealthTests(PlugNmeetBase):
    def test_operationnel(self):
        r = self.api(self.prof_affecte).get("/api/virtual-rooms/health/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["provider"], "plugnmeet")
        self.assertNotIn(SECRET, r.content.decode())

    def test_eleve_n_a_pas_acces_au_diagnostic(self):
        self.assertEqual(self.api(self.eleve_membre).get("/api/virtual-rooms/health/").status_code, 403)


@override_settings(**PNM)
class PlugNmeetLiveTests(base.BaseSalles):
    """
    Contre une INSTANCE RÉELLE (plugnmeet/docker-compose.plugnmeet.yml) :
        PLUGNMEET_TEST_URL=http://localhost:18080 PLUGNMEET_TEST_KEY=… PLUGNMEET_TEST_SECRET=…
    Ignoré sinon — jamais présenté comme exécuté.
    """

    def setUp(self):
        super().setUp()
        url = os.environ.get("PLUGNMEET_TEST_URL")
        if not url:
            self.skipTest("PLUGNMEET_TEST_URL non défini : instance plugNmeet réelle absente.")
        override = override_settings(PLUGNMEET_SERVER_URL=url, PLUGNMEET_API_KEY=os.environ["PLUGNMEET_TEST_KEY"],
                                     PLUGNMEET_API_SECRET=os.environ["PLUGNMEET_TEST_SECRET"],
                                     PLUGNMEET_WEBHOOK_URL="")
        override.enable()
        self.addCleanup(override.disable)

    def test_cycle_reel_creation_adhesion_etat_fermeture(self):
        r = self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("access_token=", r.json()["join_url"])
        self.assertTrue(plugnmeet.is_room_active(self.salle_classe))
        r2 = self.api(self.eleve_membre).post(f"/api/virtual-rooms/{self.salle_classe.pk}/join/")
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertNotEqual(r.json()["join_url"], r2.json()["join_url"])
        end = self.api(self.prof_affecte).post(f"/api/virtual-rooms/{self.salle_classe.pk}/end/")
        self.assertEqual(end.status_code, 200, end.content)
        self.assertFalse(plugnmeet.is_room_active(self.salle_classe))
        self.assertFalse(plugnmeet.end_room(self.salle_classe))  # déjà fermée : pas une erreur

    def test_signature_refusee_par_le_vrai_serveur(self):
        with override_settings(PLUGNMEET_API_SECRET="mauvais-secret-000000000000000000000"):
            with self.assertRaises(plugnmeet.PlugNmeetError) as ctx:
                plugnmeet.is_room_active(self.salle_classe)
            self.assertNotIsInstance(ctx.exception, plugnmeet.PlugNmeetUnavailable)

    def test_diagnostic_operationnel(self):
        self.assertEqual(plugnmeet.health()["status"], "operational")


class ConfigurationCheckTests(TestCase):
    @override_settings(VIDEO_PROVIDER="plugnmeet", ALLOWED_HOSTS=["globalfeba.com"],
                       PLUGNMEET_WEBHOOK_URL="http://host.docker.internal:18000/api/virtual-rooms/webhook/")
    def test_hote_du_webhook_absent_d_allowed_hosts_signale(self):
        from apps.virtualclass.checks import plugnmeet_configuration
        self.assertEqual([w.id for w in plugnmeet_configuration(None)], ["virtualclass.W001"])

    @override_settings(VIDEO_PROVIDER="plugnmeet", ALLOWED_HOSTS=[".globalfeba.com"],
                       PLUGNMEET_WEBHOOK_URL="https://globalfeba.com/api/virtual-rooms/webhook/")
    def test_hote_autorise_aucun_avertissement(self):
        from apps.virtualclass.checks import plugnmeet_configuration
        self.assertEqual(plugnmeet_configuration(None), [])
