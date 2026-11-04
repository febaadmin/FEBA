"""
Une date fournie par le client, invalide ou d'un autre type, donne 400, jamais 500.

Trouvé par balayage : « 2026-02-30 » (bien formée mais impossible) faisait lever
ValueError à parse_date, et une liste faisait lever TypeError, sur le filtre de
dates des paiements, de la boîte d'envoi et sur l'évaluation collective du suivi.
"""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.core.request_text import date_field, datetime_field


class DateFieldTests(SimpleTestCase):
    def test_valeurs_valides_et_absentes(self):
        self.assertEqual(str(date_field("2026-11-04", "d")), "2026-11-04")
        self.assertEqual(str(date_field(" 2026-11-04 ", "d")), "2026-11-04")
        self.assertIsNone(date_field(None, "d"))
        self.assertIsNone(date_field("", "d"))
        self.assertEqual(datetime_field("2026-11-04T10:00:00+01:00", "t").hour, 10)

    def test_valeurs_invalides_refusees(self):
        for mauvaise in ("2026-02-30", "04/11/2026", "demain", [1], {"a": 1}, 20261104, True):
            with self.assertRaises(ValidationError, msg=repr(mauvaise)):
                date_field(mauvaise, "d")
        for mauvaise in ("2026-02-30T10:00", "10h", [1]):
            with self.assertRaises(ValidationError, msg=repr(mauvaise)):
                datetime_field(mauvaise, "t")


from rest_framework.test import APIClient  # noqa: E402

from tests.test_audit_p1_payment_reminders import ReminderBase  # noqa: E402


class DatesInvalidesEndpointsTests(ReminderBase):
    """Balayage du 04/11/2026 : ces requêtes répondaient 500."""

    def test_filtres_et_saisies_de_dates_400(self):
        reglages = self.feba.settings or {}
        reglages["features"] = {**reglages.get("features", {}), "suivi_pedagogique": True}
        self.feba.settings = reglages
        self.feba.save(update_fields=["settings"])
        client = APIClient()
        client.force_authenticate(self.admin)
        for url in ("/api/payments/?date_from=2026-02-30", "/api/payments/?date_to=xx",
                    "/api/notifications/outbox/?date_from=2026-02-30",
                    "/api/payments/reminders/preview/?on=2026-02-30"):
            r = client.get(url)
            self.assertEqual(r.status_code, 400, f"{url} → {r.status_code}")
        r = client.post("/api/suivi/evaluations-competences/lot/", {"date": [1], "lignes": [{}]}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("date", r.data)


class IdentifiantTests(SimpleTestCase):
    def test_bornes_et_types(self):
        from apps.core.request_text import identifiant, liste_identifiants
        self.assertEqual(identifiant(5), 5)
        self.assertEqual(identifiant(" 7 "), 7)
        for mauvais in (0, -1, 2 ** 63, 10 ** 30, "abc", "1.5", True, None, {"a": 1}, [1], "9" * 30):
            self.assertIsNone(identifiant(mauvais), repr(mauvais))
        self.assertEqual(liste_identifiants([1, "2"]), [1, 2])
        self.assertIsNone(liste_identifiants([1, {"b": 2}]))
        self.assertIsNone(liste_identifiants("1,2"))
