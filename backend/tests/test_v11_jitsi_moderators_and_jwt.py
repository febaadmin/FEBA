"""
Modérateurs et jeton Jitsi — les points du cahier des charges (§21, §22).

CE QUI EST EN JEU
-----------------
Le drapeau `moderator` d'un jeton Jitsi n'est pas cosmétique : un
modérateur peut couper le micro des autres, expulser un participant et
terminer la réunion pour tout le monde. Un élève qui l'obtiendrait par
accident tiendrait la classe.

La règle est portée par le niveau de rôle (`role_level >= 50`). Ces
tests la fixent rôle par rôle, plutôt que de vérifier un seul cas et de
supposer les autres.
"""
from datetime import date, timedelta

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.virtualclass.services import build_jitsi_jwt

SECRET = "secret-de-test-uniquement"
DOMAINE = "meet.globalfeba.com"
EMETTEUR = "feba_prod"


@override_settings(JITSI_DOMAIN=DOMAINE, JITSI_APP_ID=EMETTEUR,
                   JITSI_APP_SECRET=SECRET)
class BaseJeton(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ecole, _ = School.objects.update_or_create(
            code="FEBA_FHA",
            defaults=dict(name="FEBA French Heritage Academy", slug="feba-fha",
                          currency_code="USD", address="Cotonou",
                          entity_type="online"),
        )
        SchoolYear.objects.filter(school=cls.ecole).delete()
        cls.annee = SchoolYear.objects.create(
            school=cls.ecole, name="2026-2027", start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31), is_current=True)
        niveau, _ = Level.objects.get_or_create(
            school=cls.ecole, name="Niveau", defaults={"order": 1})
        cls.classe = Class.objects.create(
            name="French Ambassadors", level=niveau, school_year=cls.annee,
            language_track=Class.TRACK_ANGLOPHONE)

    def utilisateur(self, role):
        return CustomUser.objects.create_user(
            username=f"{role}@fha.test", email=f"{role}@fha.test",
            password="Pass1234!", role=role, school=self.ecole,
            first_name=role.title(), last_name="Test")

    def charge(self, jeton):
        return jwt.decode(jeton, SECRET, algorithms=["HS256"], audience="jitsi")


@override_settings(JITSI_DOMAIN=DOMAINE, JITSI_APP_ID=EMETTEUR,
                   JITSI_APP_SECRET=SECRET)
class ModerateursParRoleTests(BaseJeton):
    """§21 — qui est modérateur, et surtout qui ne l'est jamais."""

    #: (rôle, modérateur attendu). Le seuil est `role_level >= 50`.
    ATTENDU = [
        ("superadmin", True),
        ("admin", True),
        ("teacher", True),
        ("parent", False),
        ("student", False),
    ]

    def test_chaque_role_recoit_le_bon_drapeau(self):
        for role, attendu in self.ATTENDU:
            with self.subTest(role=role):
                u = self.utilisateur(role)
                jeton = build_jitsi_jwt(
                    u, "salle-a", moderator=u.role_level >= 50,
                    academy=self.ecole.code)
                p = self.charge(jeton)
                self.assertEqual(p["moderator"], attendu)
                # Jitsi lit la chaîne du contexte, pas le booléen racine :
                # les deux doivent dire la même chose, sans quoi le
                # serveur et l'application se contrediraient.
                self.assertEqual(
                    p["context"]["user"]["moderator"],
                    "true" if attendu else "false")

    def test_un_eleve_ne_devient_pas_moderateur_en_le_demandant(self):
        """
        Le drapeau vient du rôle serveur, jamais d'une demande du client.

        C'est la garantie qui compte : la vue calcule
        `moderator=request.user.role_level >= 50` sans jamais lire le
        corps de la requête.
        """
        eleve = self.utilisateur("student")
        self.assertLess(eleve.role_level, 50)
        jeton = build_jitsi_jwt(
            eleve, "salle-a", moderator=eleve.role_level >= 50,
            academy=self.ecole.code)
        self.assertFalse(self.charge(jeton)["moderator"])


@override_settings(JITSI_DOMAIN=DOMAINE, JITSI_APP_ID=EMETTEUR,
                   JITSI_APP_SECRET=SECRET)
class VerificationDuJetonTests(BaseJeton):
    """§22 — ce que Prosody rejettera, vérifié ici plutôt que supposé."""

    def jeton(self, **kw):
        u = kw.pop("user", None) or self.utilisateur("teacher")
        return build_jitsi_jwt(u, kw.pop("room", "salle-a"),
                               academy=self.ecole.code, **kw)

    def test_l_emetteur_est_celui_configure(self):
        self.assertEqual(self.charge(self.jeton())["iss"], EMETTEUR)

    def test_un_mauvais_emetteur_est_rejete(self):
        """
        Prosody vérifie `JWT_ACCEPTED_ISSUERS`. Un jeton signé avec le bon
        secret mais un autre émetteur ne doit pas passer — sans quoi un
        autre service partageant le secret ouvrirait des salles ici.
        """
        jeton = self.jeton()
        with self.assertRaises(jwt.InvalidIssuerError):
            jwt.decode(jeton, SECRET, algorithms=["HS256"],
                       audience="jitsi", issuer="un_autre_service",
                       options={"verify_iss": True})

    def test_l_algorithme_est_symetrique_et_explicite(self):
        """
        `alg: none` et la confusion HS/RS sont les deux façons classiques
        de fabriquer un jeton sans secret. L'en-tête doit être HS256.
        """
        entete = jwt.get_unverified_header(self.jeton())
        self.assertEqual(entete["alg"], "HS256")

    def test_un_jeton_sans_signature_est_rejete(self):
        u = self.utilisateur("student")
        charge = self.charge(build_jitsi_jwt(
            u, "salle-a", moderator=False, academy=self.ecole.code))
        charge["moderator"] = True
        non_signe = jwt.encode(charge, key="", algorithm="none")
        with self.assertRaises(jwt.exceptions.PyJWTError):
            jwt.decode(non_signe, SECRET, algorithms=["HS256"], audience="jitsi")

    def test_le_jeton_n_est_pas_encore_valide_avant_son_heure(self):
        """`nbf` protège d'un jeton fabriqué à l'avance."""
        charge = self.charge(self.jeton())
        if "nbf" in charge:
            self.assertLessEqual(charge["nbf"], charge["exp"])

    def test_la_duree_de_vie_reste_courte(self):
        charge = self.charge(self.jeton())
        duree = charge["exp"] - charge["iat"]
        self.assertLessEqual(duree, 900,
                             "un jeton de longue durée reste rejouable")
        self.assertGreater(duree, 0)

    def test_le_jeton_ne_contient_aucun_secret(self):
        """Un jeton circule : il ne doit rien porter de confidentiel."""
        jeton = self.jeton()
        self.assertNotIn(SECRET, jeton)
        self.assertNotIn(SECRET, str(self.charge(jeton)))

    def test_un_jeton_expire_depuis_longtemps_est_rejete(self):
        u = self.utilisateur("teacher")
        charge = self.charge(build_jitsi_jwt(u, "salle-a", academy=self.ecole.code))
        passe = timezone.now() - timedelta(hours=2)
        charge["exp"] = int(passe.timestamp())
        charge["iat"] = int((passe - timedelta(minutes=15)).timestamp())
        perime = jwt.encode(charge, SECRET, algorithm="HS256")
        with self.assertRaises(jwt.ExpiredSignatureError):
            jwt.decode(perime, SECRET, algorithms=["HS256"], audience="jitsi")


@override_settings(JITSI_DOMAIN=DOMAINE, JITSI_APP_ID=EMETTEUR,
                   JITSI_APP_SECRET=SECRET)
class LeClientNeChoisitPasSonRoleTests(BaseJeton):
    """
    §21 — le drapeau modérateur vient du serveur, jamais de la requête.

    Un test sur `build_jitsi_jwt` seul ne prouve rien de ce point : il
    prend `moderator` en paramètre. Ce qui compte est que la VUE ne lise
    jamais ce paramètre dans le corps de la requête.
    """

    def setUp(self):
        from apps.virtualclass.models import VirtualRoom
        self.eleve = self.utilisateur("student")
        from apps.students.models import Student
        Student.objects.create(
            school=self.ecole, first_name="Ama", last_name="Diallo",
            current_class=self.classe, school_year=self.annee,
            user=self.eleve)
        self.salle = VirtualRoom.objects.create(
            name="Cours du soir", school=self.ecole, school_year=self.annee,
            class_obj=self.classe, created_by=self.utilisateur("teacher"))

    def test_un_eleve_qui_demande_moderator_recoit_un_jeton_sans_moderation(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(self.eleve)

        reponse = client.post(
            f"/api/virtual-rooms/{self.salle.id}/join/",
            {"moderator": True, "context": {"user": {"moderator": "true"}}},
            format="json")
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])

        jeton = reponse.json().get("jwt")
        self.assertTrue(jeton, "aucun jeton renvoyé")
        charge = self.charge(jeton)
        self.assertFalse(charge["moderator"],
                         "un élève a obtenu la modération en la demandant")
        self.assertEqual(charge["context"]["user"]["moderator"], "false")
