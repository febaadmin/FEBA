"""Règles d'écriture vérifiées côté API : messagerie, devoirs, présences."""
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.attendance.models import Attendance
from apps.homework.models import Homework, HomeworkAttachment
from apps.messaging.models import Conversation
from apps.parents.models import Parent, ParentStudent
from tests.test_bulk_grades import BulkGradeFixture, auth
from apps.accounts.models import CustomUser


class Base(BulkGradeFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        def compte(email, role, school):
            return CustomUser.objects.create_user(username=email.split("@")[0], email=email, password="Pass1234!",
                                                  role=role, first_name="X", last_name="Y", school=school)
        cls.eleve = compte("eleve@test.bj", "student", cls.school)
        cls.student.user = cls.eleve
        cls.student.save()
        cls.autre_eleve = compte("autre@test.bj", "student", cls.school)
        cls.student_b.user = cls.autre_eleve
        cls.student_b.save()
        cls.parent = compte("parent@test.bj", "parent", cls.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=cls.parent), student=cls.student)
        cls.admin_autre = compte("admin-autre@test.bj", "admin", cls.other)

    def client_de(self, email):
        client = APIClient()
        auth(client, email)
        return client


class MessagerieTests(Base):
    URL = "/api/messages/conversations/"

    def envoyer(self, email, destinataire, **extra):
        return self.client_de(email).post(self.URL, {"recipient_id": destinataire, "body": "Bonjour", **extra}, format="multipart")

    def test_reproduction_eleve_vers_autre_eleve_refuse(self):
        self.assertEqual(self.envoyer("eleve@test.bj", self.autre_eleve.id).status_code, 404)
        self.assertFalse(Conversation.objects.exists())

    def test_destinataires_autorises(self):
        self.assertEqual(self.envoyer("eleve@test.bj", self.teacher.user_id).status_code, 201)
        self.assertEqual(self.envoyer("eleve@test.bj", self.admin.id).status_code, 201)
        self.assertEqual(self.envoyer("prof@test.bj", self.parent.id).status_code, 201)

    def test_identifiant_invalide_404(self):
        self.assertEqual(self.envoyer("eleve@test.bj", "abc").status_code, 404)

    def test_piece_jointe_dangereuse_refusee(self):
        fichier = SimpleUploadedFile("page.html", b"<script>alert(1)</script>", content_type="text/html")
        reponse = self.envoyer("eleve@test.bj", self.admin.id, attachment=fichier)
        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(Conversation.objects.exists())


class PresencesTests(Base):
    def corps(self, student):
        return {"student": student.id, "date": "2026-01-15", "status": "absent", "school_year": self.year.id}

    def test_enseignant_dans_sa_classe(self):
        self.assertEqual(self.client_de("prof@test.bj").post("/api/attendance/", self.corps(self.student), format="json").status_code, 201)

    def test_reproduction_enseignant_hors_de_sa_classe_refuse(self):
        client = self.client_de("prof@test.bj")
        self.assertEqual(client.post("/api/attendance/", self.corps(self.student_b), format="json").status_code, 403)
        reponse = client.post("/api/attendance/bulk/", {"records": [self.corps(self.student_b)]}, format="json")
        self.assertFalse(Attendance.objects.filter(student=self.student_b).exists(), reponse.data)

    def test_admin_toute_l_academie(self):
        self.assertEqual(self.client_de("adm@test.bj").post("/api/attendance/", self.corps(self.student_b), format="json").status_code, 201)


class DevoirsTests(Base):
    def corps(self, cls):
        return {"title": "Devoir", "description": "Texte", "cls": cls.id, "subject": self.math.id, "school_year": self.year.id,
                "due_date": "2027-01-15"}

    def test_enseignant_hors_de_sa_classe_refuse(self):
        self.assertEqual(self.client_de("prof@test.bj").post("/api/homework/", self.corps(self.cls2), format="json").status_code, 403)

    def test_enseignant_dans_sa_classe(self):
        reponse = self.client_de("prof@test.bj").post("/api/homework/", self.corps(self.cls1), format="json")
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_reproduction_suppression_de_piece_jointe_cloisonnee(self):
        devoir = Homework.objects.create(title="D", cls=self.cls1, subject=self.math, school_year=self.year,
                                         teacher=self.teacher, due_date="2027-01-15")
        piece = HomeworkAttachment.objects.create(homework=devoir, file=SimpleUploadedFile("a.pdf", b"%PDF-1.4"), name="a.pdf")
        url = f"/api/homework/{devoir.id}/attachments/{piece.id}/"
        self.assertIn(self.client_de("admin-autre@test.bj").delete(url).status_code, (403, 404))
        self.assertTrue(HomeworkAttachment.objects.filter(pk=piece.pk).exists())
        self.assertEqual(self.client_de("prof@test.bj").delete(url).status_code, 204)
