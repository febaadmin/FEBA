"""
Tests V4 — Priorité 4 (backend site vitrine).

Couvre : endpoints publics en lecture, formulaires publics (validations,
honeypot anti-spam), non-exposition publique des soumissions, permissions
admin sur le CRUD de contenu, seed idempotent sans donnée fictive.
"""
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School
from apps.website.models import (
    SiteSettings, HeroSlide, NewsPost, GalleryAlbum,
    ContactMessage, PreRegistration,
)

CONTACT_PAYLOAD = {
    "name": "Jean K", "email": "jean@exemple.bj", "phone": "+229 01 02 03 04",
    "subject": "Demande d'information", "message": "Bonjour, je souhaite des informations.",
    "consent": True,
}
PREREG_PAYLOAD = {
    "parent_name": "Awa T", "phone": "+229 05 06 07 08", "whatsapp": "+229 05 06 07 08",
    "email": "awa@exemple.bj", "child_name": "Bintou T", "child_age": 6,
    "desired_level": "cp", "school_year": "2026-2027", "message": "Merci.",
}


class PublicContentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        call_command("seed_website", verbosity=0)

    def test_settings_public(self):
        resp = self.client.get("/api/website/settings/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["school_name"], "Faith & Excellence Bilingual Academy")
        # Aucune donnée fictive : coordonnées et stats vides par défaut
        self.assertEqual(resp.data["phone"], "")
        self.assertIsNone(resp.data["stat_students"])

    def test_hero_slides_public(self):
        resp = self.client.get("/api/website/hero-slides/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 5)
        self.assertTrue(all(s["image_src"].startswith("/site/img/") for s in resp.data))

    def test_gallery_public(self):
        resp = self.client.get("/api/website/gallery/")
        self.assertEqual(resp.status_code, 200)
        titles = [a["title"] for a in resp.data]
        self.assertIn("Notre campus", titles)
        moments = next(a for a in resp.data if a["title"] == "Moments FEBA")
        kinds = {i["kind"] for i in moments["items"]}
        self.assertIn("video", kinds)

    def test_news_empty_by_default_no_fake_content(self):
        resp = self.client.get("/api/website/news/")
        self.assertEqual(resp.status_code, 200)
        rows = resp.data["results"] if "results" in resp.data else resp.data
        self.assertEqual(len(rows), 0)  # pas de fausses actualités seedées

    def test_news_publication_flow(self):
        post = NewsPost.objects.create(
            title="Rentrée scolaire", excerpt="Infos rentrée", body="Détails…",
            is_published=True,
        )
        self.assertTrue(post.slug)
        resp = self.client.get("/api/website/news/")
        rows = resp.data["results"] if "results" in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        detail = self.client.get(f"/api/website/news/{post.slug}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["body"], "Détails…")
        # Un brouillon n'est pas exposé
        draft = NewsPost.objects.create(title="Brouillon", is_published=False)
        self.assertEqual(self.client.get(f"/api/website/news/{draft.slug}/").status_code, 404)

    def test_seed_idempotent(self):
        call_command("seed_website", verbosity=0)
        self.assertEqual(HeroSlide.objects.count(), 5)
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(
            GalleryAlbum.objects.count(),
            GalleryAlbum.objects.filter(is_active=True).count(),
        )


class PublicFormsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_contact_valid_submission(self):
        resp = self.client.post("/api/website/contact/", CONTACT_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.name, "Jean K")
        self.assertFalse(msg.is_read)

    def test_contact_missing_fields(self):
        resp = self.client.post("/api/website/contact/", {"name": "X"}, format="json")
        self.assertEqual(resp.status_code, 400)
        for field in ("email", "subject", "message"):
            self.assertIn(field, resp.data)

    def test_contact_invalid_email(self):
        payload = {**CONTACT_PAYLOAD, "email": "pas-un-email"}
        resp = self.client.post("/api/website/contact/", payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("email", resp.data)

    def test_contact_honeypot_rejected(self):
        payload = {**CONTACT_PAYLOAD, "website": "http://spam.example"}
        resp = self.client.post("/api/website/contact/", payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_prereg_valid_submission(self):
        resp = self.client.post("/api/website/preregistrations/", PREREG_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        p = PreRegistration.objects.get()
        self.assertEqual(p.status, "new")
        self.assertEqual(p.desired_level, "cp")

    def test_prereg_invalid_level_and_age(self):
        bad = {**PREREG_PAYLOAD, "desired_level": "université", "child_age": 42}
        resp = self.client.post("/api/website/preregistrations/", bad, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("desired_level", resp.data)

    def test_prereg_honeypot_rejected(self):
        bad = {**PREREG_PAYLOAD, "website": "spam"}
        resp = self.client.post("/api/website/preregistrations/", bad, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(PreRegistration.objects.count(), 0)

    def test_submissions_never_public(self):
        """Les soumissions ne sont accessibles par AUCUN endpoint public."""
        self.client.post("/api/website/contact/", CONTACT_PAYLOAD, format="json")
        for url in ("/api/website/contact/", "/api/website/preregistrations/"):
            self.assertNotEqual(self.client.get(url).status_code, 200)


class AdminContentPermissionTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="FEBA", address="Cotonou")
        self.admin = CustomUser.objects.create_user(
            username="wadmin", email="wadmin@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=self.school,
        )
        self.parent = CustomUser.objects.create_user(
            username="wparent", email="wparent@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="A", school=self.school,
        )
        self.client = APIClient()

    def _auth(self, email):
        resp = self.client.post("/api/auth/login/", {"email": email, "password": "Pass1234!"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    def test_anonymous_cannot_access_admin_endpoints(self):
        for url in ("/api/website/admin/settings/", "/api/website/admin/news/",
                    "/api/website/admin/contact-messages/",
                    "/api/website/admin/preregistrations/"):
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_parent_cannot_access_admin_endpoints(self):
        self._auth("wparent@test.bj")
        for url in ("/api/website/admin/settings/", "/api/website/admin/news/",
                    "/api/website/admin/contact-messages/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_admin_crud_news_and_reads_submissions(self):
        self._auth("wadmin@test.bj")
        create = self.client.post("/api/website/admin/news/", {
            "title": "Journée portes ouvertes", "kind": "event",
            "excerpt": "Venez nous rencontrer", "is_published": True,
        }, format="json")
        self.assertEqual(create.status_code, 201, create.data)

        APIClient().post("/api/website/contact/", CONTACT_PAYLOAD, format="json")
        msgs = self.client.get("/api/website/admin/contact-messages/")
        self.assertEqual(msgs.status_code, 200)
        rows = msgs.data["results"] if "results" in msgs.data else msgs.data
        self.assertEqual(len(rows), 1)
        # Marquage lu
        patch = self.client.patch(
            f"/api/website/admin/contact-messages/{rows[0]['id']}/",
            {"is_read": True}, format="json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertTrue(ContactMessage.objects.get().is_read)

    def test_admin_updates_settings(self):
        self._auth("wadmin@test.bj")
        resp = self.client.patch("/api/website/admin/settings/", {
            "phone": "+229 00 00 00 00", "stat_students": 250,
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        s = SiteSettings.load()
        self.assertEqual(s.phone, "+229 00 00 00 00")
        self.assertEqual(s.stat_students, 250)
        # visible côté public ensuite
        pub = APIClient().get("/api/website/settings/")
        self.assertEqual(pub.data["stat_students"], 250)

    def test_prereg_status_workflow(self):
        APIClient().post("/api/website/preregistrations/", PREREG_PAYLOAD, format="json")
        self._auth("wadmin@test.bj")
        rows = self.client.get("/api/website/admin/preregistrations/").data
        rows = rows["results"] if "results" in rows else rows
        pk = rows[0]["id"]
        resp = self.client.patch(
            f"/api/website/admin/preregistrations/{pk}/",
            {"status": "processing"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PreRegistration.objects.get().status, "processing")
        # Les champs saisis par la famille sont en lecture seule côté admin
        resp2 = self.client.patch(
            f"/api/website/admin/preregistrations/{pk}/",
            {"child_name": "Modifié"}, format="json",
        )
        self.assertEqual(PreRegistration.objects.get().child_name, "Bintou T", resp2.data)


class FocalPointTests(TestCase):
    """V5 — point focal administrable des médias du site vitrine."""

    def setUp(self):
        self.client = APIClient()
        call_command("seed_website", verbosity=0)

    def test_hero_slides_expose_focal(self):
        resp = self.client.get("/api/website/hero-slides/")
        self.assertEqual(resp.status_code, 200)
        by_order = {s["order"]: s for s in resp.data}
        # Slide 4 (ronde d'enfants, crème en haut) : cadrage bas administré
        self.assertEqual(by_order[4]["focal"], "55% 78%")
        # Slide 5 (famille à droite, crème à gauche) : cadrage droite
        self.assertEqual(by_order[5]["focal"], "72% 45%")
        for s in resp.data:
            self.assertRegex(s["focal"], r"^\d{1,3}% \d{1,3}%$")

    def test_gallery_items_expose_focal(self):
        resp = self.client.get("/api/website/gallery/")
        self.assertEqual(resp.status_code, 200)
        items = [i for a in resp.data for i in a["items"]]
        self.assertTrue(items)
        for i in items:
            self.assertRegex(i["focal"], r"^\d{1,3}% \d{1,3}%$")
        # Valeur seedée spécifique (V6 : l'enseignante est en bas-gauche du
        # visuel, un grand mur crème occupe le haut-droite → cadrage sur elle)
        participation = [i for i in items
                        if "academique-participation" in (i["image_src"] or "")]
        self.assertTrue(participation)
        self.assertEqual(participation[0]["focal"], "26% 64%")

    def test_focal_bounds_validated(self):
        from django.core.exceptions import ValidationError
        from apps.website.models import HeroSlide
        slide = HeroSlide(title="X", image_path="/site/img/hero-campus-1600.webp",
                          focal_x=140, focal_y=50)
        with self.assertRaises(ValidationError):
            slide.full_clean()

    def test_admin_can_update_focal(self):
        from apps.schools.models import School
        School.objects.create(name="FEBA", address="Cotonou")
        admin = CustomUser.objects.create_user(
            username="focaladmin", email="focaladmin@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="F",
            school=School.objects.first(),
        )
        login = self.client.post("/api/auth/login/",
                                 {"email": "focaladmin@test.bj", "password": "Pass1234!"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        slide_id = self.client.get("/api/website/hero-slides/").data[0]["id"]
        resp = self.client.patch(f"/api/website/admin/hero-slides/{slide_id}/",
                                 {"focal_x": 30, "focal_y": 60}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        pub = APIClient().get("/api/website/hero-slides/")
        updated = [s for s in pub.data if s["id"] == slide_id][0]
        self.assertEqual(updated["focal"], "30% 60%")
