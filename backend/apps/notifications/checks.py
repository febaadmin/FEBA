"""
Contrôles de configuration de la messagerie (`manage.py check`).

Une adresse d'expédition retirée, ou qui n'appartient pas au compte SMTP,
ne fait pas échouer l'application : elle fait échouer chaque envoi, en
silence pour l'utilisateur. On le signale dès le démarrage.
"""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def email_sender_configuration(app_configs, **kwargs):
    from .mailer import OBSOLETE_SENDERS, OFFICIAL_NOREPLY, _address_of, transport_backend

    issues = []
    senders = {
        name: getattr(settings, name, "")
        for name in ("DEFAULT_FROM_EMAIL", "FEBA_FROM_EMAIL", "FHA_FROM_EMAIL", "SERVER_EMAIL")
    }
    for name, value in senders.items():
        if _address_of(value) in OBSOLETE_SENDERS:
            issues.append(Warning(
                f"{name} vaut encore l'adresse retirée « {_address_of(value)} ». Elle est remplacée "
                f"à l'envoi par « {OFFICIAL_NOREPLY} » ; corrigez la variable d'environnement.",
                id="notifications.W001",
            ))
    login = (getattr(settings, "EMAIL_HOST_USER", "") or "").lower()
    if "smtp" in transport_backend().lower() and "@" in login:
        login_domain = login.rsplit("@", 1)[1]
        for name in ("DEFAULT_FROM_EMAIL", "FEBA_FROM_EMAIL", "FHA_FROM_EMAIL"):
            address = _address_of(senders[name])
            if address in OBSOLETE_SENDERS:
                address = OFFICIAL_NOREPLY
            if address and address.rsplit("@", 1)[-1] != login_domain:
                issues.append(Warning(
                    f"{name} (« {address} ») n'est pas du domaine du compte SMTP « {login_domain} » : "
                    "la plupart des fournisseurs (Hostinger compris) refusent un expéditeur qui "
                    "n'appartient pas au compte authentifié.",
                    id="notifications.W002",
                ))
    return issues
