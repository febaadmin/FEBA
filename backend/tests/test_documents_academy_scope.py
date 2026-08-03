"""
P8 — Les documents officiels respectent l'académie sélectionnée.

LE DÉFAUT
---------
Le filtrage regardait `user.school`. Pour un super administrateur, la page
renvoyait donc TOUS les documents des deux académies, quelle que soit
l'académie choisie dans l'en-tête : sélectionner FEBA affichait quand même
les diplômes de FEBA French Heritage Academy. La page contredisait le
sélecteur placé juste au-dessus d'elle.

La liste d'élèves de la fenêtre « Produire un document » avait le même
défaut : elle mélangeait les deux académies. Produire un diplôme au fond
FEBA pour un élève de l'académie en ligne ne demandait alors qu'une erreur
de frappe — et le document sortait complet, plausible, à l'effigie de la
mauvaise académie.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student

User = get_user_model()

#: L'académie active d'un super administrateur est PERSISTÉE EN BASE, pas
#: lue dans la requête : un navigateur ne peut pas élargir sa portée en
#: forgeant un en-tête. Les tests basculent donc comme l'application le
#: fait — en changeant `active_organization`.


class DocumentsAcademyScopeTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", city="Cotonou",
                          country="Bénin", currency_code="XOF"),
        )
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD"),
        )
        cls.feba_student = cls._student(cls.feba, "Ana", "Ba")
        cls.fha_student = cls._student(cls.fha, "Marie", "Dupont")

        cls.superadmin = User.objects.create_user(
            username="super", email="super@test", password="x",
            role="superadmin", school=cls.feba,
        )
        cls.feba_admin = User.objects.create_user(
            username="admin.feba", email="admin.feba@test", password="x",
            role="admin", school=cls.feba,
        )

    @classmethod
    def _student(cls, school, first, last):
        year, _ = SchoolYear.objects.get_or_create(
            school=school, name="2025-2026",
            defaults=dict(start_date=date(2025, 9, 1), end_date=date(2026, 7, 31),
                          is_current=True),
        )
        level = Level.objects.create(school=school, name=f"N-{school.pk}", order=9)
        klass = Class.objects.create(name=f"C-{school.pk}", level=level,
                                     school_year=year)
        return Student.objects.create(
            school=school, first_name=first, last_name=last,
            current_class=klass, school_year=year,
        )

    def _client(self, user, scope=None):
        if user.is_superadmin():
            user.active_organization = (
                School.objects.filter(code=scope).first() if scope else None
            )
            user.save(update_fields=["active_organization"])
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    # ── Élèves ───────────────────────────────────────────────────────

    def test_la_liste_d_eleves_suit_l_academie_selectionnee(self):
        """
        Le super administrateur sélectionne FEBA : il ne doit voir que des
        élèves FEBA dans la fenêtre de production.
        """
        client = self._client(self.superadmin, School.CODE_FEBA)
        response = client.get("/api/students/")
        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        names = {f"{r['first_name']} {r['last_name']}" for r in rows}
        self.assertIn("Ana Ba", names)
        self.assertNotIn("Marie Dupont", names)

    # ── Gabarits ─────────────────────────────────────────────────────

    def test_les_gabarits_declarent_leurs_academies(self):
        client = self._client(self.superadmin, School.CODE_FEBA)
        response = client.get("/api/documents/templates/")
        self.assertEqual(response.status_code, 200)
        for template in response.data["templates"]:
            with self.subTest(gabarit=template["id"]):
                self.assertIn("academies", template)
                self.assertIn("allowed_for_academy", template)

    def test_un_gabarit_feba_n_est_pas_proposable_a_l_academie_en_ligne(self):
        """
        P1 — Chaque académie ne voit que SES gabarits.

        Avant l'intégration des visuels FEBA FHA, ce test vérifiait
        qu'AUCUN gabarit n'était proposé à l'académie en ligne : il n'en
        existait aucun à son nom, et proposer ceux de Cotonou aurait
        produit un document au nom de l'une et à l'effigie de l'autre.

        Depuis, l'académie en ligne a ses propres fonds. La règle n'a pas
        changé — elle se vérifie simplement dans les deux sens : les
        gabarits FEBA restent refusés, les gabarits FHA sont utilisables.
        """
        client = self._client(self.superadmin, School.CODE_FEBA_FHA)
        response = client.get("/api/documents/templates/")

        proposes = set()
        for template in response.data["templates"]:
            with self.subTest(gabarit=template["id"]):
                if template["id"].endswith("_feba_fha"):
                    self.assertTrue(
                        template["allowed_for_academy"],
                        "Le gabarit propre à l'académie en ligne devrait lui "
                        "être proposé.",
                    )
                    proposes.add(template["id"])
                else:
                    self.assertFalse(
                        template["allowed_for_academy"],
                        "Un gabarit au fond FEBA est proposé à l'académie en "
                        "ligne : le document sortirait au nom de l'une et à "
                        "l'effigie de l'autre.",
                    )
                    self.assertFalse(template["can_issue"])
                    self.assertTrue(
                        any("réservé à" in b for b in template["blockers"]))

        self.assertEqual(
            proposes, {"diploma_feba_fha", "certificate_feba_fha"},
            "L'académie en ligne doit disposer de son diplôme ET de son "
            "certificat.",
        )

    def test_le_gabarit_reste_utilisable_pour_son_academie(self):
        client = self._client(self.superadmin, School.CODE_FEBA)
        response = client.get("/api/documents/templates/")
        allowed = [t for t in response.data["templates"] if t["allowed_for_academy"]]
        self.assertTrue(allowed, "Aucun gabarit utilisable pour FEBA.")

    def test_la_reponse_dit_sous_quelle_academie_l_ecran_travaille(self):
        client = self._client(self.superadmin, School.CODE_FEBA)
        response = client.get("/api/documents/templates/")
        self.assertEqual(response.data["academy"]["code"], School.CODE_FEBA)
        self.assertFalse(response.data["consolidated"])

    def test_en_mode_consolide_aucune_academie_n_est_supposee(self):
        """
        Sans académie choisie, l'API ne DEVINE pas. Elle le déclare, et
        l'interface impose alors une confirmation avant de produire.
        """
        client = self._client(self.superadmin)
        response = client.get("/api/documents/templates/")
        self.assertIsNone(response.data["academy"])
        self.assertTrue(response.data["consolidated"])

    # ── Production ───────────────────────────────────────────────────

    def test_produire_un_document_feba_pour_un_eleve_en_ligne_est_refuse(self):
        client = self._client(self.superadmin)
        response = client.post("/api/documents/", {
            "student": self.fha_student.pk, "template": "diploma_feba",
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("réservé à", response.data["detail"])

    def test_produire_pour_un_eleve_de_son_academie_reste_possible(self):
        client = self._client(self.superadmin, School.CODE_FEBA)
        response = client.post("/api/documents/", {
            "student": self.feba_student.pk, "template": "diploma_feba",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["academy_code"], School.CODE_FEBA)

    def test_un_eleve_hors_academie_selectionnee_est_introuvable(self):
        """Anti-IDOR : l'identifiant d'un élève de l'autre académie ne suffit pas."""
        client = self._client(self.superadmin, School.CODE_FEBA)
        response = client.post("/api/documents/", {
            "student": self.fha_student.pk, "template": "diploma_feba",
        }, format="json")
        self.assertEqual(response.status_code, 404)

    # ── Liste des documents produits ─────────────────────────────────

    def test_la_liste_des_documents_suit_l_academie_selectionnee(self):
        producer = self._client(self.superadmin, School.CODE_FEBA)
        producer.post("/api/documents/", {
            "student": self.feba_student.pk, "template": "diploma_feba",
        }, format="json")

        feba_view = self._client(self.superadmin, School.CODE_FEBA)
        rows = feba_view.get("/api/documents/").data
        self.assertTrue(rows)
        self.assertTrue(all(r["academy_code"] == School.CODE_FEBA for r in rows))

        fha_view = self._client(self.superadmin, School.CODE_FEBA_FHA)
        self.assertEqual(fha_view.get("/api/documents/").data, [])

    def test_chaque_ligne_porte_son_academie_en_mode_consolide(self):
        producer = self._client(self.superadmin, School.CODE_FEBA)
        producer.post("/api/documents/", {
            "student": self.feba_student.pk, "template": "diploma_feba",
        }, format="json")

        rows = self._client(self.superadmin).get("/api/documents/").data
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(document=row["id"]):
                self.assertTrue(row["academy_code"])
                self.assertTrue(row["academy_name"])

    def test_un_admin_feba_ne_voit_pas_les_documents_de_l_autre_academie(self):
        producer = self._client(self.superadmin, School.CODE_FEBA)
        producer.post("/api/documents/", {
            "student": self.feba_student.pk, "template": "diploma_feba",
        }, format="json")

        rows = self._client(self.feba_admin).get("/api/documents/").data
        self.assertTrue(all(r["academy_code"] == School.CODE_FEBA for r in rows))

    def test_un_admin_ne_peut_pas_elargir_sa_portee(self):
        """
        Un administrateur reste sur SON académie, quoi qu'il envoie.

        La bascule d'académie passe par un endpoint dédié qui vérifie
        l'appartenance et journalise. Aucun paramètre de requête, aucun
        en-tête, aucun champ de payload ne peut la remplacer.
        """
        client = APIClient()
        client.force_authenticate(user=self.feba_admin)
        response = client.get("/api/documents/?school_id=%d" % self.fha.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            all(r["academy_code"] == School.CODE_FEBA for r in response.data))


class ServiceLevelAcademyRuleTests(TestCase):
    """
    La règle d'académie vaut pour TOUT appelant, pas seulement pour HTTP.

    Défaut trouvé en validant l'archive extraite : le contrôle n'existait
    que dans la vue. Une requête HTTP était bien refusée, mais une commande
    de gestion, un script d'import ou un test produisait sans rien signaler
    un diplôme au fond d'une académie pour l'élève d'une autre.

    Une règle posée à la porte d'entrée HTTP n'est pas une règle : c'est un
    filtre que le prochain appelant contournera sans le savoir.
    """

    @classmethod
    def setUpTestData(cls):
        cls.feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", currency_code="XOF"),
        )
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD"),
        )
        cls.feba_student = DocumentsAcademyScopeTests._student.__func__(
            DocumentsAcademyScopeTests, cls.feba, "Ana", "Ba")
        cls.fha_student = DocumentsAcademyScopeTests._student.__func__(
            DocumentsAcademyScopeTests, cls.fha, "Marie", "Dupont")

    def test_le_service_refuse_un_gabarit_interdit_a_l_academie(self):
        from django.core.exceptions import ValidationError

        from apps.documents.services import create_document

        for template_id in ("diploma_feba", "certificate_feba"):
            with self.subTest(gabarit=template_id):
                with self.assertRaises(ValidationError) as raised:
                    create_document(template_id=template_id,
                                    student=self.fha_student)
                self.assertIn("réservé à", " ".join(raised.exception.messages))

    def test_le_service_accepte_le_gabarit_de_son_academie(self):
        from apps.documents.services import create_document

        document = create_document(template_id="diploma_feba",
                                   student=self.feba_student)
        self.assertEqual(document.academy, self.feba)

    def test_aucun_document_n_est_ecrit_quand_la_regle_refuse(self):
        """Le refus doit précéder toute écriture, sinon un brouillon reste."""
        from django.core.exceptions import ValidationError

        from apps.documents.models import GeneratedDocument
        from apps.documents.services import create_document

        before = GeneratedDocument.objects.count()
        with self.assertRaises(ValidationError):
            create_document(template_id="diploma_feba", student=self.fha_student)
        self.assertEqual(GeneratedDocument.objects.count(), before)
