"""
Garde-fou : aucun module applicatif n'envoie d'e-mail hors de la couche
centrale (apps/notifications/mailer.py, backends.py).

Les notifications FHA (`send_mail(..., fail_silently=True)`) et les
rapports mensuels (`EmailMultiAlternatives` direct) contournaient le
journal : leurs échecs étaient invisibles. Ce test empêche le retour d'un
tel chemin ; le backend de traçage en reste le filet de sécurité.
"""
import ast
import pathlib

APPS = pathlib.Path(__file__).resolve().parent.parent / "apps"
ALLOWED = {APPS / "notifications" / "mailer.py", APPS / "notifications" / "backends.py"}
FORBIDDEN_CALLS = {"send_mail", "send_mass_mail", "mail_admins", "mail_managers",
                   "EmailMessage", "EmailMultiAlternatives", "SMTP", "SMTP_SSL"}


def _name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def test_no_email_sent_outside_central_layer():
    offenders = []
    for path in APPS.rglob("*.py"):
        if path in ALLOWED or "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _name(node.func) in FORBIDDEN_CALLS:
                offenders.append(f"{path.relative_to(APPS)}:{node.lineno}: {_name(node.func)}()")
            for kw in node.keywords:
                if kw.arg == "fail_silently" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    offenders.append(f"{path.relative_to(APPS)}:{node.lineno}: fail_silently=True")
    assert offenders == [], "Envoi hors couche centrale :\n" + "\n".join(offenders)
