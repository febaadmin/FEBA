"""
Service JWT Jitsi — instance AUTO-HÉBERGÉE uniquement.

Seul le backend FEBA connaît `JITSI_APP_SECRET` : aucune salle ne peut être
ouverte sans un jeton signé, émis après vérification des permissions Django.

CHANGEMENT DE CONTRAT (V5)
--------------------------
L'ancienne implémentation retournait `None` lorsque l'instance n'était pas
configurée, et le client rejoignait alors `meet.jit.si` SANS jeton. Une
classe d'enfants basculait donc sur un serveur public non authentifié dès
qu'une variable manquait.

Désormais, une configuration incomplète lève `JitsiNotConfigured`. L'appelant
transforme cette exception en erreur d'infrastructure explicite (HTTP 503) —
jamais en session publique.
"""
import time

from django.conf import settings


class JitsiNotConfigured(RuntimeError):
    """L'instance Jitsi auto-hébergée n'est pas configurée ou est interdite."""


class JitsiAccessDenied(PermissionError):
    """L'utilisateur n'a pas le droit de rejoindre cette salle."""


def jitsi_domain():
    """Domaine de l'instance auto-hébergée, ou lève JitsiNotConfigured."""
    domain = (getattr(settings, "JITSI_DOMAIN", "") or "").strip()
    host = domain.split(":")[0].lower()
    forbidden = getattr(settings, "JITSI_FORBIDDEN_DOMAINS", ())

    if not domain:
        raise JitsiNotConfigured(
            "JITSI_DOMAIN n'est pas configuré. Lancez « make install » (ou "
            "« make jitsi-up ») pour démarrer l'instance auto-hébergée."
        )
    if host in forbidden:
        raise JitsiNotConfigured(
            f"Le domaine « {host} » est une instance PUBLIQUE, interdite par "
            "la politique de protection des mineurs de FEBA. Configurez une "
            "instance auto-hébergée."
        )
    return domain


def assert_jitsi_configured():
    """Vérifie la configuration complète. Lève JitsiNotConfigured sinon."""
    jitsi_domain()
    if not getattr(settings, "JITSI_APP_ID", "") or not getattr(settings, "JITSI_APP_SECRET", ""):
        raise JitsiNotConfigured(
            "JITSI_APP_ID / JITSI_APP_SECRET manquants : aucun jeton ne peut "
            "être signé, donc aucune salle ne peut être protégée. Lancez "
            "« make install » pour générer les secrets."
        )


def build_jitsi_jwt(user, room, moderator=False, ttl_seconds=900, academy=None,
                    group=None):
    """
    Jeton Jitsi signé pour `user` sur la salle `room`.

    Le jeton porte l'ACADÉMIE et le GROUPE, en plus de l'identité et du
    rôle. Le champ `room` nomme la salle : Prosody rejette un jeton présenté
    sur une autre salle, ce qui interdit de le rejouer ailleurs.

    Durée de vie courte (15 min par défaut) : un jeton intercepté n'ouvre
    pas un accès permanent.

    Lève `JitsiNotConfigured` si l'instance n'est pas prête — jamais de
    repli silencieux vers un serveur public.
    """
    assert_jitsi_configured()

    import jwt  # PyJWT (épinglé dans requirements/base.txt)

    secret = settings.JITSI_APP_SECRET
    app_id = settings.JITSI_APP_ID
    domain = jitsi_domain().split(":")[0]
    now = int(time.time())

    payload = {
        "iss": app_id,
        "aud": "jitsi",
        "sub": domain,
        # Salle NOMMÉE dans le jeton : il n'est pas rejouable ailleurs.
        "room": room,
        "iat": now,
        "nbf": now - 10,
        "exp": now + ttl_seconds,
        "context": {
            "user": {
                "id": str(user.id),
                "name": user.get_full_name() or user.username,
                "email": user.email or "",
                "moderator": "true" if moderator else "false",
            },
            # Traçabilité applicative : académie et groupe d'origine.
            "feba": {
                "academy": academy or "",
                "group": group or "",
                "role": getattr(user, "role", ""),
            },
        },
        "moderator": bool(moderator),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def assert_can_join(user, room):
    """
    Vérifie qu'un utilisateur a le droit de rejoindre une salle.

    Règles, dans l'ordre :
      1. l'académie de la salle doit être celle de l'utilisateur — un
         utilisateur FEBA ne rejoint JAMAIS une salle FEBA FHA ;
      2. l'académie doit avoir la fonctionnalité `video_conferencing` ;
      3. le compte doit être actif ;
      4. la salle doit être active et non annulée ;
      5. un élève ou un parent doit être rattaché à la classe de la salle
         (une salle sans classe est générale à l'académie).

    Lève `JitsiAccessDenied` avec un motif précis.
    """
    if not user.is_active:
        raise JitsiAccessDenied("Compte désactivé.")

    room_academy = room.school
    if room_academy is None:
        raise JitsiAccessDenied("Cette salle n'est rattachée à aucune académie.")

    # 1. Cloisonnement inter-académies — la règle la plus importante.
    if user.is_superadmin():
        user_academy = getattr(user, "active_organization", None)
        if user_academy is not None and user_academy != room_academy:
            raise JitsiAccessDenied(
                "Cette salle appartient à une autre académie que celle "
                "actuellement sélectionnée."
            )
    elif user.school_id != room_academy.id:
        raise JitsiAccessDenied("Cette salle appartient à une autre académie.")

    # 2. Fonctionnalité activée pour cette académie.
    if not room_academy.has_feature("video_conferencing"):
        raise JitsiAccessDenied(
            "La visioconférence n'est pas activée pour cette académie."
        )

    # 4. État de la salle.
    if not room.is_active or room.status == "cancelled":
        raise JitsiAccessDenied("Cette salle n'est plus disponible.")

    # 5. Appartenance au groupe / à la classe.
    if room.class_obj_id is not None:
        if user.role == "student":
            student = getattr(user, "student_profile", None)
            if student is None or student.current_class_id != room.class_obj_id:
                raise JitsiAccessDenied(
                    "Vous n'êtes pas inscrit dans le groupe de cette salle."
                )
        elif user.role == "parent":
            parent = getattr(user, "parent_profile", None)
            allowed = False
            if parent is not None:
                allowed = parent.children_links.filter(
                    student__current_class_id=room.class_obj_id,
                ).exists()
            if not allowed:
                raise JitsiAccessDenied(
                    "Aucun de vos enfants n'appartient au groupe de cette salle."
                )

    return True


def jitsi_health():
    """
    État de l'infrastructure de visioconférence, pour l'écran
    d'administration : « operational », « degraded » ou « unavailable ».

    Ne lève jamais : un incident d'infrastructure ne doit pas casser la
    page qui sert justement à le diagnostiquer.
    """
    import urllib.request

    result = {
        "status": "unavailable",
        "domain": "",
        "configured": False,
        "reachable": False,
        "token_signing": False,
        "probed_url": "",
        "detail": "",
    }

    try:
        assert_jitsi_configured()
        result["configured"] = True
        result["domain"] = jitsi_domain()
    except JitsiNotConfigured as exc:
        result["detail"] = str(exc)
        return result

    # Signature d'un jeton de test : valide la présence et la forme du secret.
    try:
        import jwt
        jwt.encode({"test": 1}, settings.JITSI_APP_SECRET, algorithm="HS256")
        result["token_signing"] = True
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        result["detail"] = f"Signature de jeton impossible : {exc}"
        return result

    # Joignabilité HTTP de l'instance.
    #
    # P7 — On sonde JITSI_INTERNAL_URL (http://jitsi-web:80 en dev), PAS
    # `domain` (JITSI_DOMAIN, ex. localhost:8443) : cette dernière est
    # l'adresse du NAVIGATEUR. Depuis l'intérieur de CE conteneur,
    # « localhost » ne désigne jamais Jitsi — avant ce correctif, cette
    # vérification échouait systématiquement même quand Jitsi tournait
    # parfaitement, un faux « dégradé » permanent.
    internal_url = (getattr(settings, "JITSI_INTERNAL_URL", "") or "").strip()
    if internal_url:
        url = internal_url.rstrip("/") + "/"
    else:
        # Repli : pas d'URL interne distincte configurée (cas légitime en
        # production, où backend et Jitsi partagent la même adresse
        # publique). On reste alors sur l'ancien comportement.
        domain = result["domain"]
        is_local = domain.startswith("localhost") or domain.startswith("127.")
        scheme = "http" if is_local else "https"
        url = f"{scheme}://{domain}/"
    result["probed_url"] = url
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=5) as response:
            result["reachable"] = 200 <= response.status < 500
    except Exception as exc:
        result["detail"] = f"Instance injoignable sur {url} : {exc}"
        result["status"] = "degraded"
        return result

    result["status"] = "operational" if result["reachable"] else "degraded"
    if result["status"] == "operational":
        result["detail"] = "Instance auto-hébergée opérationnelle."
    return result
