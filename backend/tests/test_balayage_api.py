"""
Balayage de toute l'API : aucune donnée mal formée ne doit produire d'erreur 500.

Origine : le 04/11/2026, ce balayage (alors manuel) a trouvé 14 endpoints qui
répondaient 500 quand un champ avait un type inattendu (objet, liste, nombre
hors limites, date impossible) : identifiants passés bruts à un filtre,
valeurs non hachables testées dans un ensemble, dates « 2026-02-30 »,
textes trop longs enregistrés sans validation.

Le test découvre seul :
- les routes de l'API (liste, et détail à un seul identifiant) ;
- les clés lues dans le code (`request.data.get("…")`, `data.get("…")`…),
  pour qu'un endpoint ajouté demain soit couvert sans modifier ce fichier.

Chaque requête est jouée dans une transaction annulée : aucune écriture ne
reste. Une réponse 503 (service externe absent, ex. visioconférence) est
tolérée ; toute autre réponse 5xx échoue.
"""
import logging
import re
from pathlib import Path

from django.core.management import call_command
from django.db import transaction
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser

APPS = Path(__file__).resolve().parent.parent / "apps"
EXCLUS = ("webhook", "logout", "deliver", "resend", "retry", "send", "run", "download", "pdf", "preview",
          "original", "background", "receipt", "import", "upload", "sms", "email", "check", "test-smtp")


def _routes(resolver, prefixe=""):
    for p in resolver.url_patterns:
        if isinstance(p, URLResolver):
            yield from _routes(p, prefixe + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefixe + str(p.pattern)


def routes_api():
    listes, details = set(), set()
    for r in _routes(get_resolver()):
        if not r.startswith("api/") or "format" in r:
            continue
        r = r.replace("^", "").replace("$", "").replace("\\Z", "")
        r = re.sub(r"\(\?P<(\w+)>[^)]*\)", r"<\1>", r)
        params = re.findall(r"<(?:(\w+):)?(\w+)>", r)
        if any(x in r for x in EXCLUS):
            continue
        if not params:
            listes.add("/" + r)
        elif len(params) == 1 and params[0][0] in ("int", ""):
            details.add("/" + re.sub(r"<[^>]+>", "1", r))
    return sorted(listes), sorted(details)


def cles_lues():
    motif = re.compile(r"""(?:request\.data|data|ligne|row|d)\.get\(['"]([a-z_]+)['"]""")
    return sorted({m for f in APPS.rglob("*.py") if "migrations" not in f.parts for m in motif.findall(f.read_text())})


class BalayageApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_data", verbosity=0)
        from apps.schools.models import School
        for ecole in School.objects.all():
            reglages = ecole.settings or {}
            reglages["features"] = {**reglages.get("features", {}), **{m: True for m in (
                "suivi_pedagogique", "suivi_familles", "evaluations_en_ligne", "monthly_reports",
                "online_admissions", "virtual_classrooms")}}
            ecole.settings = reglages
            ecole.save(update_fields=["settings"])

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        cles = cles_lues()
        self.assertGreater(len(cles), 100, "extraction des clés : le motif ne trouve plus rien")
        self.charges = {
            "objet": {k: {"a": 1} for k in cles},
            "liste": {k: [1, {"b": 2}] for k in cles},
            "grand": {k: 10 ** 30 for k in cles},
            "date": {k: "2026-02-30" for k in cles},
        }
        self.listes, self.details = routes_api()
        self.assertGreater(len(self.listes) + len(self.details), 200, "découverte des routes en panne")

    def client_pour(self, role):
        user = CustomUser.objects.filter(role=role, is_active=True).order_by("pk").first()
        self.assertIsNotNone(user, role)
        c = APIClient(SERVER_NAME="localhost")
        c.force_authenticate(user)
        return c

    def jouer(self, client, methode, url, corps):
        with transaction.atomic():
            r = getattr(client, methode)(url, corps, format="json") if corps is not None else client.get(url)
            transaction.set_rollback(True)
        return r.status_code

    def test_aucune_erreur_500(self):
        erreurs, total = [], 0
        for role in ("superadmin", "admin", "teacher", "parent", "student"):
            client = self.client_pour(role)
            for url in self.listes + self.details:
                essais = [("get", None)]
                if role in ("superadmin", "admin"):
                    essais += [(m, c) for m in ("post", "patch") for c in self.charges.values()]
                for methode, corps in essais:
                    code = self.jouer(client, methode, url, corps)
                    total += 1
                    if code >= 500 and code != 503:
                        erreurs.append(f"{role} {methode.upper()} {url} → {code}")
        self.assertGreater(total, 1000)
        self.assertEqual(erreurs, [], f"{len(erreurs)} erreur(s) 500 sur {total} requêtes")
