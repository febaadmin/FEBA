"""
Campagne d'isolation multi-académies, réutilisable pour 2, 7, 19… académies.

Trois volets, tous exécutés par l'API réelle (APIClient, sans simulation de
permission) :

  1. LISTES — chaque route GET sans paramètre du routeur Django, demandée par
     des comptes de chaque rôle : la réponse ne doit contenir AUCUNE
     étiquette d'une autre académie (les étiquettes figurent dans les noms,
     e-mails, codes et matricules créés par `academy_fixtures`).
  2. DÉTAILS — les identifiants vus par l'administrateur de A, demandés par
     les comptes de B : jamais un 200 portant l'étiquette de A.
  3. ÉCRITURES CROISÉES — remplacer un identifiant dans une requête
     (note, élève, bulletin, paiement, académie, appréciations) : refusé, et
     la donnée de l'autre académie reste intacte.

Les routes publiques, de téléchargement et de webhooks sont exclues des
volets 1 et 2 (elles ont leurs propres tests) ; les erreurs 5xx sont
comptées comme des échecs.
"""
import re

from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.test import APIClient

SKIP = re.compile(
    r"(health|webhook|logout|export|download|pdf|csv|xlsx|print|stripe|kkiapay|fedapay|"
    r"media|schema|swagger|docs|/ws|entity-context/log|auth/me|public|website/fha/enroll|"
    r"preview|token|password|reset|verify|login|register)", re.I)


def _walk(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def _to_path(route):
    r = route.replace("^", "").replace("$", "").replace("\\.", ".")
    r = re.sub(r"\(\?P<format>[^)]*\)", "", r)
    r = re.sub(r"\.\(\?P<format>.*?\)/?", "", r)
    r = "/" + r.replace("//", "/")
    r = re.sub(r"(?<!\()\?(?!P<)", "", r).replace("//", "/")
    return r if r.endswith("/") else r + "/"


def routes():
    all_routes = sorted({_to_path(r) for r in _walk(get_resolver().url_patterns)
                         if r.startswith("api/")})
    lists = [r for r in all_routes if "<" not in r and "(?P" not in r and not SKIP.search(r)]
    details = sorted({re.sub(r"\(\?P<pk>[^)]*\)|<(int:)?pk>", "{pk}", r) for r in all_routes
                      if re.search(r"\(\?P<pk>|<(int:)?pk>", r) and not SKIP.search(r)})
    details = [d for d in details if "(?P" not in d and "<" not in d]
    return lists, details


def client_for(user):
    c = APIClient(HTTP_HOST="localhost")
    c.force_authenticate(user)
    return c


class Report:
    def __init__(self):
        self.requests = 0
        self.leaks = []
        self.errors = []

    def check_body(self, who, path, response, foreign_tags):
        self.requests += 1
        if response.status_code >= 500:
            self.errors.append(f"{who} {path} → {response.status_code}")
            return
        if response.status_code != 200 or "json" not in response.get("Content-Type", ""):
            return
        body = response.content.decode("utf-8", "replace")
        for tag, pattern in foreign_tags:
            if pattern.search(body):
                self.leaks.append(f"{who} GET {path} contient l'étiquette de {tag}")
                return


def tag_pattern(tag):
    return re.compile(re.escape(tag), re.I)


def run_list_and_detail(academies, *, role_sample):
    """
    `academies` : liste de BuiltAcademy. `role_sample` : nombre d'académies
    dont TOUS les rôles sont sondés (les autres : administrateur seulement).
    """
    report = Report()
    lists, details = routes()
    patterns = {a.tag: tag_pattern(a.tag) for a in academies}

    for index, academy in enumerate(academies):
        foreign = [(t, p) for t, p in patterns.items() if t != academy.tag]
        users = academy.users() if index < role_sample else {"admin": academy.admin}
        for role, user in users.items():
            c = client_for(user)
            for path in lists:
                try:
                    r = c.get(path, {"page_size": 1000})
                except Exception as exc:          # erreur non gérée = défaut
                    report.errors.append(f"{academy.tag}/{role} GET {path} → {type(exc).__name__}")
                    continue
                report.check_body(f"{academy.tag}/{role}", path, r, foreign)

    # Détails : identifiants listés par l'admin de A, demandés par B et C.
    count = len(academies)
    for index, owner in enumerate(academies):
        admin = client_for(owner.admin)
        own_pattern = [(owner.tag, patterns[owner.tag])]
        intruders = {academies[(index + 1) % count], academies[(index + max(1, count // 2)) % count]}
        intruders.discard(owner)
        for path in details:
            base = path.split("{pk}")[0]
            try:
                listing = admin.get(base, {"page_size": 1000})
                data = listing.json() if listing.status_code == 200 else None
            except Exception:
                continue
            items = data.get("results", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                continue
            ids = [i.get("id") for i in items if isinstance(i, dict) and i.get("id") is not None][:3]
            for intruder in intruders:
                users = intruder.users() if academies.index(intruder) < role_sample \
                    else {"admin": intruder.admin}
                for role, user in users.items():
                    c = client_for(user)
                    for pk in ids:
                        target = path.replace("{pk}", str(pk))
                        try:
                            r = c.get(target)
                        except Exception as exc:
                            report.errors.append(f"{intruder.tag}/{role} GET {target} → {type(exc).__name__}")
                            continue
                        report.check_body(f"{intruder.tag}/{role}", target, r, own_pattern)
    return report


def run_cross_writes(attacker, victim):
    """
    Tentatives d'écriture de l'administrateur de `attacker` sur les données
    de `victim`. Retourne la liste des écritures ABOUTIES (doit être vide).
    """
    from decimal import Decimal

    from apps.bulletins.models import Bulletin
    from apps.grades.models import AppreciationRule, Grade
    from apps.payments.models import Payment
    from apps.students.models import Student

    c = client_for(attacker.admin)
    breaches = []
    grade = Grade.objects.filter(student=victim.student).first()
    before_grade = grade.value

    def expect(label, response, ok_codes=(400, 403, 404, 405, 409)):
        if response.status_code not in ok_codes:
            breaches.append(f"{label} → {response.status_code}")

    expect("PATCH note", c.patch(f"/api/grades/{grade.pk}/", {"value": "20"}, format="json"))
    expect("DELETE note", c.delete(f"/api/grades/{grade.pk}/"))
    expect("POST note sur l'élève d'une autre académie", c.post("/api/grades/", {
        "student": victim.student.pk, "subject": attacker.subjects[0].pk,
        "school_year": attacker.year.pk, "period": "T1", "value": "19"}, format="json"))
    expect("POST note avec la matière d'une autre académie", c.post("/api/grades/", {
        "student": attacker.student.pk, "subject": victim.subjects[0].pk,
        "school_year": attacker.year.pk, "period": "T1", "value": "19"}, format="json"))
    expect("PATCH élève", c.patch(f"/api/students/{victim.student.pk}/", {"first_name": "Pirate"},
                                  format="json"))
    expect("GET élève", c.get(f"/api/students/{victim.student.pk}/"), ok_codes=(403, 404))
    expect("GET paiement", c.get(f"/api/payments/{victim.payment.pk}/"), ok_codes=(403, 404))
    expect("PATCH paiement", c.patch(f"/api/payments/{victim.payment.pk}/", {"amount": "1"},
                                     format="json"))
    expect("Commentaire de bulletin", c.post("/api/bulletins/comment-target/", {
        "student_id": victim.student.pk, "school_year_id": victim.year.pk, "period": "T1",
        "comment": "Piraté"}, format="json"))
    expect("Aperçu de bulletin", c.post("/api/bulletins/preview/", {
        "student_id": victim.student.pk, "school_year_id": victim.year.pk, "period": "T1"},
        format="json"))
    bulletin = Bulletin.objects.filter(student=victim.student).first()
    if bulletin is not None:
        expect("GET bulletin", c.get(f"/api/bulletins/{bulletin.pk}/"), ok_codes=(403, 404))
        expect("Commentaire direct", c.post(f"/api/bulletins/{bulletin.pk}/comment/",
                                            {"comment": "Piraté"}, format="json"))
    expect("PATCH académie", c.patch(f"/api/schools/schools/{victim.school.pk}/", {"name": "Piratée"},
                                     format="json"), ok_codes=(403, 404))
    expect("PATCH niveau", c.patch(f"/api/schools/levels/{victim.level.pk}/", {"cycle": "lycee"},
                                   format="json"))
    rules = [{"id": r.id, "min_percent": str(r.min_percent), "label_fr": "PIRATÉ", "is_active": True}
             for r in AppreciationRule.objects.filter(school=victim.school, cycle="")]
    expect("PUT appréciations", c.put("/api/grades/appreciations/", {"rules": rules}, format="json"))

    grade.refresh_from_db()
    if grade.value != before_grade or not Grade.objects.filter(pk=grade.pk).exists():
        breaches.append("la note de l'autre académie a changé")
    if Student.objects.filter(pk=victim.student.pk, first_name="Pirate").exists():
        breaches.append("l'élève de l'autre académie a été modifié")
    if Payment.objects.get(pk=victim.payment.pk).amount == Decimal("1"):
        breaches.append("le paiement de l'autre académie a été modifié")
    if AppreciationRule.objects.filter(school=victim.school, label_fr="PIRATÉ").exists():
        breaches.append("le barème de l'autre académie a été modifié")
    if Bulletin.objects.filter(student=victim.student, general_comment="Piraté").exists():
        breaches.append("le bulletin de l'autre académie a été modifié")
    victim.school.refresh_from_db()
    if victim.school.name == "Piratée":
        breaches.append("l'académie a été renommée")
    return breaches
