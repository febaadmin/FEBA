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

    # 5. Ciblage par RÔLE.
    #
    # Une salle réservée à l'équipe pédagogique ne doit pas être ouverte à
    # tous les élèves de l'académie parce qu'elle n'est rattachée à aucune
    # classe. Liste vide = aucun filtre, comportement historique.
    target_roles = list(getattr(room, "target_roles", None) or [])
    if target_roles and not user.is_superadmin():
        if user.role not in target_roles:
            raise JitsiAccessDenied(
                "Cette salle est réservée à d'autres profils "
                f"({', '.join(sorted(target_roles))})."
            )

    # 6. Appartenance au groupe / à la classe.
    if room.class_obj_id is not None:
        # UN ENSEIGNANT N'EST PAS AUTOMATIQUEMENT CHEZ LUI.
        #
        # Le contrôle ne portait que sur les élèves et les parents : tout
        # enseignant de l'académie pouvait donc entrer dans le cours d'une
        # classe qui ne lui est pas confiée. Un enseignant reste
        # modérateur, mais des classes qu'on lui a réellement affectées.
        if user.role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            assigned = False
            if teacher is not None:
                assigned = teacher.classes.filter(pk=room.class_obj_id).exists()
            # Le créateur de la salle y garde accès : il l'a ouverte pour
            # une classe qu'il encadre ponctuellement (remplacement,
            # soutien) sans en être titulaire.
            if not assigned and room.created_by_id != user.id:
                raise JitsiAccessDenied(
                    "Cette classe ne vous est pas affectée."
                )
        elif user.role == "student":
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


def jitsi_probe_url():
    """
    URL que le BACKEND doit interroger pour joindre Jitsi.

    Deux adresses coexistent légitimement : celle du NAVIGATEUR
    (`JITSI_DOMAIN`, ex. « meet.globalfeba.com ») et celle du RÉSEAU
    INTERNE (`JITSI_INTERNAL_URL`, ex. « http://jitsi-web:80 »). Sonder la
    première depuis un conteneur qui ne sort pas, ou la seconde depuis un
    serveur qui n'a pas ce réseau, produit un « dégradé » permanent qui ne
    dit rien de l'état réel de l'instance.
    """
    internal = (getattr(settings, "JITSI_INTERNAL_URL", "") or "").strip()
    if internal:
        return internal.rstrip("/") + "/"
    domain = (getattr(settings, "JITSI_DOMAIN", "") or "").strip()
    host = domain.split(":")[0].lower()
    is_local = host in ("localhost", "127.0.0.1") or host.startswith("127.")
    scheme = "http" if is_local else "https"
    return f"{scheme}://{domain}/"


def jitsi_health(timeout=5):
    """
    État de l'infrastructure de visioconférence : « operational »,
    « degraded » ou « unavailable ».

    Ne lève JAMAIS : un incident d'infrastructure ne doit pas casser la
    page qui sert justement à le diagnostiquer.

    P6 — Le rapport ne se contente plus de « joignable / injoignable ». Un
    « injoignable » a au moins quatre causes qui appellent quatre gestes
    différents : le domaine ne résout pas (DNS à créer), il résout mais
    refuse la connexion (pare-feu, service arrêté), le certificat est
    invalide (Let's Encrypt à renouveler), ou l'instance répond mais n'est
    pas Jitsi (mauvais vhost). `checks` porte ce détail ; les clés
    historiques (`status`, `configured`, `reachable`, `token_signing`,
    `domain`, `detail`) sont conservées telles quelles pour la bannière et
    les tests existants.
    """
    import socket
    import ssl
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse

    result = {
        "status": "unavailable",
        "domain": "",
        "configured": False,
        "reachable": False,
        "token_signing": False,
        "probed_url": "",
        "detail": "",
        # P6 — chaque contrôle porte son verdict et son explication.
        "checks": [],
    }

    def record(name, ok, detail=""):
        result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        return ok

    # 1. Configuration backend : domaine renseigné, non public, secrets là.
    try:
        assert_jitsi_configured()
        result["configured"] = True
        result["domain"] = jitsi_domain()
        record("configuration", True,
               f"Domaine « {result['domain'] } », identifiants JWT présents.")
    except JitsiNotConfigured as exc:
        result["detail"] = str(exc)
        record("configuration", False, str(exc))
        return result

    domain = result["domain"]
    host = domain.split(":")[0]

    # 2. Aucun domaine public. Déjà garanti par `jitsi_domain()` ; répété
    #    ici pour que le rapport l'affirme explicitement plutôt que de le
    #    laisser déduire de l'absence d'erreur.
    record("domaine_non_public", True,
           f"« {host} » n'est pas une instance publique interdite.")

    # 3. Signature d'un jeton : valide la présence ET la forme du secret.
    try:
        import jwt
        jwt.encode({"test": 1}, settings.JITSI_APP_SECRET, algorithm="HS256")
        result["token_signing"] = True
        record("signature_jeton", True, "Un jeton de test a été signé.")
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        result["detail"] = f"Signature de jeton impossible : {exc}"
        record("signature_jeton", False, result["detail"])
        return result

    url = jitsi_probe_url()
    result["probed_url"] = url
    parsed = urlparse(url)
    probe_host = parsed.hostname or host
    probe_port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # ── Diagnostics réseau ───────────────────────────────────────────
    #
    # ORDRE ET AUTORITÉ. DNS et TLS sont contrôlés AVANT la requête HTTP,
    # mais ils ne décident pas du verdict : c'est la réponse HTTP qui fait
    # foi. Un premier jet faisait l'inverse — retour immédiat dès que
    # `getaddrinfo` échouait — et se trompait dans un cas réel : derrière
    # un proxy sortant, le backend ne résout pas lui-même le domaine et
    # joint pourtant l'instance parfaitement. L'instance était déclarée
    # « dégradée » alors que les cours fonctionnaient.
    #
    # DNS et TLS servent donc à EXPLIQUER un échec HTTP, pas à l'anticiper :
    # « injoignable » ne dit pas quoi faire, « le domaine ne résout pas »
    # envoie chez l'hébergeur DNS et « le certificat a expiré » chez
    # Let's Encrypt.

    # 4. Résolution DNS.
    dns_detail = ""
    try:
        addresses = sorted({
            info[4][0] for info in socket.getaddrinfo(probe_host, None)
        })
        record("dns", True, f"{probe_host} → {', '.join(addresses)}")
    except OSError as exc:
        dns_detail = (
            f"Le domaine « {probe_host} » ne résout pas ({exc}). "
            "Créez l'enregistrement DNS A vers l'IP du serveur Jitsi "
            "(voir MANUAL_PRODUCTION_ACTIONS.md)."
        )
        record("dns", False, dns_detail)

    # 5. Certificat TLS — uniquement en HTTPS. Un certificat expiré rend
    #    l'instance inutilisable dans un navigateur alors que le service
    #    tourne : sans ce contrôle, le rapport dirait « injoignable » et
    #    on chercherait au mauvais endroit.
    tls_detail = ""
    if parsed.scheme == "https":
        try:
            context = ssl.create_default_context()
            with socket.create_connection((probe_host, probe_port),
                                          timeout=timeout) as raw:
                with context.wrap_socket(raw, server_hostname=probe_host) as tls:
                    certificate = tls.getpeercert()
            expiry = (certificate or {}).get("notAfter", "")
            record("tls", True,
                   f"Certificat valide pour {probe_host}"
                   + (f", expire le {expiry}." if expiry else "."))
        except ssl.SSLCertVerificationError as exc:
            tls_detail = (
                f"Certificat TLS refusé pour « {probe_host} » : "
                f"{getattr(exc, 'verify_message', exc)}. Renouvelez le "
                "certificat (voir JITSI_PRODUCTION_GUIDE.md)."
            )
            record("tls", False, tls_detail)
        except OSError as exc:
            tls_detail = (
                f"Connexion TLS impossible vers {probe_host}:{probe_port} "
                f"({exc}). Vérifiez que le service tourne et que le "
                "pare-feu laisse passer le port 443."
            )
            record("tls", False, tls_detail)
        except Exception as exc:  # noqa: BLE001 — voir ci-dessous
            # CETTE FONCTION NE DOIT JAMAIS LEVER, c'est sa raison d'être :
            # elle alimente la page qui sert à diagnostiquer une panne. Une
            # exception inattendue ici (bibliothèque TLS d'une plateforme,
            # environnement de test) ferait tomber l'écran de diagnostic au
            # moment précis où l'on en a besoin.
            tls_detail = f"Contrôle TLS impossible pour {probe_host} : {exc}."
            record("tls", False, tls_detail)

    # 6. Réponse HTTP de l'instance — LE contrôle qui fait autorité.
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.status
            try:
                body = response.read(65536).decode("utf-8", "replace")
            except Exception:
                body = ""
        result["reachable"] = 200 <= status_code < 500
        record("http", result["reachable"], f"HTTP {status_code} sur {url}")
    except Exception as exc:
        # Le motif le plus PRÉCIS l'emporte : dire « injoignable » quand on
        # sait déjà que le domaine ne résout pas fait chercher une panne de
        # service là où il manque un enregistrement DNS.
        detail = dns_detail or tls_detail or f"Instance injoignable sur {url} : {exc}"
        record("http", False, f"Requête échouée sur {url} : {exc}")
        result["detail"] = detail
        result["status"] = "degraded"
        return result

    # 7. C'est bien Jitsi qui répond, pas un vhost par défaut. Une page
    #    « Welcome to nginx » satisfait le contrôle HTTP et ne permet
    #    d'ouvrir aucune salle.
    #
    #    Un corps VIDE ne prouve rien dans un sens ni dans l'autre (réponse
    #    tronquée, sonde interne minimale) : on ne transforme pas une
    #    absence de preuve en preuve d'absence.
    if body:
        signature = any(
            marker in body.lower()
            for marker in ("jitsi", "lib-jitsi-meet", "meet.jitsi")
        )
        record("endpoint_jitsi", signature,
               "La page servie est celle de Jitsi Meet." if signature else
               f"L'hôte répond sur {url} mais la page ne semble pas être "
               "celle de Jitsi Meet : vérifiez le vhost du reverse proxy.")
        if not signature:
            result["status"] = "degraded"
            result["detail"] = result["checks"][-1]["detail"]
            return result

    # 8. `external_api.js` — le fichier que le navigateur charge pour
    #    ouvrir une conférence. La page d'accueil peut répondre 200 sans
    #    que ce script soit servi (mauvaise racine, build incomplet) :
    #    l'utilisateur voit alors « Visioconférence indisponible » alors
    #    que tous les contrôles précédents sont au vert.
    # L'URL de sonde est la MÊME que pour le contrôle principal : depuis
    # un conteneur, `meet.globalfeba.com` n'est pas forcément joignable, et
    # `JITSI_INTERNAL_URL` existe précisément pour cela (régression P7).
    # Coder « https://<domaine public> » en dur ici referait ce bug.
    base = url.rstrip("/")
    api_url = f"{base}/external_api.js"
    try:
        request = urllib.request.Request(api_url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            api_status = response.status
            api_type = (response.headers.get("Content-Type") or "").lower()
            api_len = len(response.read(4096))
        servi = api_status == 200 and api_len > 0 and "javascript" in api_type
        record("external_api", servi,
               f"external_api.js servi ({api_status}, {api_type or 'type inconnu'})."
               if servi else
               f"external_api.js répond {api_status} avec le type "
               f"« {api_type or 'inconnu'} » : le navigateur ne pourra pas "
               "ouvrir de conférence.")
        if not servi:
            result["status"] = "degraded"
            result["detail"] = result["checks"][-1]["detail"]
            return result
    except Exception as exc:
        record("external_api", False, f"external_api.js injoignable : {exc}")
        result["status"] = "degraded"
        result["detail"] = result["checks"][-1]["detail"]
        return result

    # 9. Point d'entrée de la signalisation. On ne peut pas établir une
    #    vraie liaison WebSocket ici — cela demande une négociation XMPP
    #    complète — mais on peut vérifier que le chemin EXISTE : un 404
    #    signifie que le reverse proxy n'a pas de règle pour lui, et c'est
    #    la panne classique « tout le monde entre et personne ne se voit ».
    ws_url = f"{base}/xmpp-websocket"
    try:
        request = urllib.request.Request(ws_url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            ws_status = response.status
    except urllib.error.HTTPError as exc:
        ws_status = exc.code
    except Exception as exc:
        ws_status = None
        record("signalisation", False,
               f"Le chemin {ws_url} est injoignable : {exc}")
    if ws_status is not None:
        # 404 = aucune règle de proxy. Tout le reste (101, 200, 400, 426,
        # 501…) prouve qu'une règle existe et répond.
        route = ws_status != 404
        record("signalisation", route,
               f"Le chemin /xmpp-websocket répond ({ws_status}) : le reverse "
               "proxy a bien une règle pour la signalisation."
               if route else
               "Le chemin /xmpp-websocket renvoie 404 : le reverse proxy n'a "
               "aucune règle pour lui. Les participants entreront dans la "
               "salle sans jamais se voir.")
        if not route:
            result["status"] = "degraded"
            result["detail"] = result["checks"][-1]["detail"]
            return result

    result["status"] = "operational" if result["reachable"] else "degraded"
    if result["status"] == "operational":
        result["detail"] = "Instance auto-hébergée opérationnelle."
    return result
